import io
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from dotenv import load_dotenv
from django.utils import timezone

from orders.services.xml_parser import XMLOrderParser


class RemoteTiaknightConfigError(ValueError):
    pass


class RemoteTiaknightFetchError(RuntimeError):
    pass


class RemoteTiaknightParseError(ValueError):
    pass


def import_remote_tiaknight_orders(user=None):
    """Fetch Tiaknight SOAP orders and import them through the XML parser."""
    load_dotenv()

    url = os.environ.get('TIA_URL')
    clientid = os.environ.get('TIA_CLIENTID')
    username = os.environ.get('TIA_USERNAME')
    password = os.environ.get('TIA_PASSWORD')
    auto_update = os.environ.get('TIA_AUTO_UPDATE', 'false')
    file_type = os.environ.get('TIA_FILE_TYPE', 'xml')
    audit_log_path = os.environ.get('TIA_AUDIT_LOG_PATH', 'logs/remote_tiaknight_order_refs.log')
    save_raw_payload = _env_bool(os.environ.get('TIA_SAVE_RAW_PAYLOAD', 'false'))
    raw_payload_dir = os.environ.get('TIA_RAW_PAYLOAD_DIR', 'logs/tiaknight_payloads')

    if not all([url, clientid, username, password]):
        raise RemoteTiaknightConfigError(
            'Missing Tiaknight credentials in .env '
            '(TIA_URL, TIA_CLIENTID, TIA_USERNAME, TIA_PASSWORD)'
        )

    try:
        from scripts.soap_client import fetch_soap_response, extract_result_xml
    except Exception as exc:
        raise RemoteTiaknightFetchError(f'Could not import SOAP client: {exc}') from exc

    try:
        soap_bytes, http_status = fetch_soap_response(
            url=url,
            clientid=clientid,
            username=username,
            password=password,
            auto_update=auto_update,
            file_type=file_type,
        )
    except RuntimeError as exc:
        raise RemoteTiaknightFetchError(str(exc)) from exc

    orders_xml_str = extract_result_xml(soap_bytes)
    if orders_xml_str is None:
        raise RemoteTiaknightParseError('Could not find <Result> value in SOAP response')

    order_refs = extract_order_references_from_xml(orders_xml_str)
    request_id = extract_soap_value(soap_bytes, 'RequestID')
    source_datetime = extract_soap_value(soap_bytes, 'DateTime')
    raw_payload_path = None
    if save_raw_payload:
        raw_payload_path = write_raw_payload(
            orders_xml_str,
            raw_payload_dir=raw_payload_dir,
            request_id=request_id,
        )
    write_import_audit(
        audit_log_path=audit_log_path,
        http_status=http_status,
        request_id=request_id,
        source_datetime=source_datetime,
        auto_update=auto_update,
        file_type=file_type,
        order_refs=order_refs,
        raw_payload_path=raw_payload_path,
    )

    parser = XMLOrderParser()
    xml_file = io.BytesIO(orders_xml_str.encode('utf-8'))
    result = parser.parse_and_create_orders(xml_file, user=user)
    result['received_order_refs'] = order_refs
    result['received_order_refs_count'] = len(order_refs)
    result['tiaknight_request_id'] = request_id
    result['tiaknight_source_datetime'] = source_datetime
    result['tiaknight_auto_update'] = auto_update
    result['tiaknight_audit_log_path'] = audit_log_path
    result['tiaknight_raw_payload_path'] = raw_payload_path
    return result


def extract_soap_value(soap_bytes, key):
    """Return a top-level SOAP response value by key."""
    try:
        root = ET.fromstring(soap_bytes)
    except ET.ParseError:
        return None

    for item in root.iter('item'):
        key_el = item.find('key')
        val_el = item.find('value')
        if key_el is not None and (key_el.text or '').strip() == key:
            return (val_el.text or '').strip() if val_el is not None and val_el.text else None
    return None


def extract_order_references_from_xml(orders_xml_str):
    """Extract all order references from the embedded Tiaknight order XML."""
    try:
        root = ET.fromstring(orders_xml_str)
    except ET.ParseError:
        return []

    root_tag = root.tag.lower()
    order_elements = [root] if root_tag in {'order', 'web_order'} else list(root)
    refs = []
    for order_elem in order_elements:
        order_node = order_elem.find('order')
        if order_node is None:
            order_node = order_elem
        ref = (
            _find_text(order_node, 'order_reference')
            or _find_text(order_node, 'order_id')
            or _find_text(order_elem, 'OrderNumber')
        )
        if ref:
            refs.append(ref)
    return refs


def write_import_audit(
    *,
    audit_log_path,
    http_status,
    request_id,
    source_datetime,
    auto_update,
    file_type,
    order_refs,
    raw_payload_path=None,
):
    """Append received Tiaknight order refs to a dedicated audit log."""
    path = Path(audit_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = timezone.localtime()
    refs = ','.join(order_refs) if order_refs else '-'
    raw_payload_note = f" raw_payload={raw_payload_path}" if raw_payload_path else ''
    line = (
        f"[{now:%Y-%m-%d %H:%M:%S %Z}] "
        f"http_status={http_status} request_id={request_id or '-'} "
        f"source_datetime={source_datetime or '-'} auto_update={auto_update} "
        f"file_type={file_type} orders_received={len(order_refs)} refs={refs}"
        f"{raw_payload_note}\n"
    )
    with path.open('a', encoding='utf-8') as audit_log:
        audit_log.write(line)


def write_raw_payload(orders_xml_str, *, raw_payload_dir, request_id=None):
    """Optionally persist the raw embedded orders XML for deep audit."""
    now = timezone.localtime()
    safe_request_id = ''.join(ch for ch in str(request_id or 'no-request-id') if ch.isalnum() or ch in '-_')
    payload_dir = Path(raw_payload_dir)
    payload_dir.mkdir(parents=True, exist_ok=True)
    path = payload_dir / f"tiaknight_orders_{now:%Y%m%d_%H%M%S}_{safe_request_id}.xml"
    path.write_text(orders_xml_str, encoding='utf-8')
    return str(path)


def _find_text(element, tag):
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return None


def _env_bool(value):
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}

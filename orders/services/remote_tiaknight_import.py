import io
import os
import time
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
    gap_recovery_attempts = _env_int(os.environ.get('TIA_GAP_RECOVERY_ATTEMPTS'), 2)
    gap_recovery_delay_seconds = _env_float(os.environ.get('TIA_GAP_RECOVERY_DELAY_SECONDS'), 0)
    fetch_order_details = _env_bool(os.environ.get('TIA_FETCH_ORDER_DETAILS', 'true'))
    recover_missing_with_get_order = _env_bool(
        os.environ.get('TIA_RECOVER_MISSING_WITH_GET_ORDER', 'true')
    )

    if not all([url, clientid, username, password]):
        raise RemoteTiaknightConfigError(
            'Missing Tiaknight credentials in .env '
            '(TIA_URL, TIA_CLIENTID, TIA_USERNAME, TIA_PASSWORD)'
        )

    try:
        from scripts.soap_client import fetch_soap_response, fetch_order_response, extract_result_xml
    except Exception as exc:
        raise RemoteTiaknightFetchError(f'Could not import SOAP client: {exc}') from exc

    soap_bytes, http_status = _fetch_tiaknight_soap(
        fetch_soap_response,
        url=url,
        clientid=clientid,
        username=username,
        password=password,
        auto_update=auto_update,
        file_type=file_type,
    )
    orders_xml_str = extract_result_xml(soap_bytes)
    if orders_xml_str is None:
        raise RemoteTiaknightParseError('Could not find <Result> value in SOAP response')

    order_refs = extract_order_references_from_xml(orders_xml_str)
    missing_sequence_refs = detect_missing_sequence_refs(order_refs, audit_log_path)
    request_id = extract_soap_value(soap_bytes, 'RequestID')
    source_datetime = extract_soap_value(soap_bytes, 'DateTime')
    recovery_fetches = []

    if missing_sequence_refs and gap_recovery_attempts > 0:
        orders_xml_str, order_refs, missing_sequence_refs, recovery_fetches = recover_missing_sequence_orders(
            fetch_soap_response,
            extract_result_xml,
            orders_xml_str,
            audit_log_path=audit_log_path,
            missing_sequence_refs=missing_sequence_refs,
            attempts=gap_recovery_attempts,
            delay_seconds=gap_recovery_delay_seconds,
            url=url,
            clientid=clientid,
            username=username,
            password=password,
            auto_update=auto_update,
            file_type=file_type,
        )

    missing_order_fetches = []
    if recover_missing_with_get_order and missing_sequence_refs:
        orders_xml_str, order_refs, missing_sequence_refs, missing_order_fetches = (
            recover_missing_sequence_orders_by_get_order(
                fetch_order_response,
                extract_result_xml,
                orders_xml_str,
                audit_log_path=audit_log_path,
                missing_sequence_refs=missing_sequence_refs,
                url=url,
                clientid=clientid,
                username=username,
                password=password,
            )
        )

    detail_fetches = []
    if fetch_order_details and order_refs:
        orders_xml_str, detail_fetches = enrich_orders_with_get_order_details(
            fetch_order_response,
            extract_result_xml,
            orders_xml_str,
            url=url,
            clientid=clientid,
            username=username,
            password=password,
        )
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
        missing_sequence_refs=missing_sequence_refs,
        raw_payload_path=raw_payload_path,
        recovery_fetches=recovery_fetches,
        missing_order_fetches=missing_order_fetches,
        detail_fetches=detail_fetches,
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
    result['missing_sequence_order_refs'] = missing_sequence_refs
    result['tiaknight_gap_recovery_attempts'] = len(recovery_fetches)
    result['tiaknight_gap_recovery_fetches'] = recovery_fetches
    result['tiaknight_recover_missing_with_get_order'] = recover_missing_with_get_order
    result['tiaknight_missing_order_fetches'] = missing_order_fetches
    result['tiaknight_fetch_order_details'] = fetch_order_details
    result['tiaknight_detail_fetches'] = detail_fetches
    return result


def _fetch_tiaknight_soap(fetch_soap_response, **kwargs):
    try:
        return fetch_soap_response(**kwargs)
    except RuntimeError as exc:
        raise RemoteTiaknightFetchError(str(exc)) from exc


def recover_missing_sequence_orders(
    fetch_soap_response,
    extract_result_xml,
    orders_xml_str,
    *,
    audit_log_path,
    missing_sequence_refs,
    attempts,
    delay_seconds,
    **fetch_kwargs,
):
    """Retry GetNewOrders when a sequence gap appears and merge unique orders by reference."""
    current_xml = orders_xml_str
    current_refs = extract_order_references_from_xml(current_xml)
    recovery_fetches = []

    for attempt in range(1, attempts + 1):
        if delay_seconds > 0:
            time.sleep(delay_seconds)

        soap_bytes, http_status = _fetch_tiaknight_soap(fetch_soap_response, **fetch_kwargs)
        retry_xml = extract_result_xml(soap_bytes)
        retry_refs = extract_order_references_from_xml(retry_xml or '')
        current_xml = merge_order_xml_payloads(current_xml, retry_xml)
        current_refs = extract_order_references_from_xml(current_xml)
        missing_sequence_refs = detect_missing_sequence_refs(current_refs, audit_log_path)
        recovery_fetches.append({
            'attempt': attempt,
            'http_status': http_status,
            'received_order_refs': retry_refs,
            'missing_sequence_order_refs_after_attempt': missing_sequence_refs,
        })
        if not missing_sequence_refs:
            break

    return current_xml, current_refs, missing_sequence_refs, recovery_fetches


def recover_missing_sequence_orders_by_get_order(
    fetch_order_response,
    extract_result_xml,
    orders_xml_str,
    *,
    audit_log_path,
    missing_sequence_refs,
    url,
    clientid,
    username,
    password,
):
    """
    Fetch missing sequence refs directly with GetOrder.

    GetNewOrders can omit an order after Tiaknight users manually move it to
    Processing Order, but GetOrder can still return that specific order by ref.
    """
    current_xml = orders_xml_str
    missing_order_fetches = []

    for ref in missing_sequence_refs:
        order_id = _order_id_from_ref(ref)
        try:
            soap_bytes, http_status = fetch_order_response(
                url=url,
                clientid=clientid,
                username=username,
                password=password,
                order_ref=ref,
                order_id=order_id,
            )
            detail_xml = extract_result_xml(soap_bytes)
            detail_order_elem = _first_order_element_from_xml(detail_xml)
            detail_ref = _order_ref_from_element(detail_order_elem) if detail_order_elem is not None else None
            recovered = detail_order_elem is not None and (not detail_ref or detail_ref == ref)
            if recovered:
                current_xml = merge_order_xml_payloads(current_xml, detail_xml)

            missing_order_fetches.append({
                'order_ref': ref,
                'order_id': order_id,
                'http_status': http_status,
                'detail_found': detail_order_elem is not None,
                'recovered': recovered,
            })
        except RuntimeError as exc:
            missing_order_fetches.append({
                'order_ref': ref,
                'order_id': order_id,
                'error': str(exc),
                'detail_found': False,
                'recovered': False,
            })

    current_refs = extract_order_references_from_xml(current_xml)
    remaining_missing_refs = detect_missing_sequence_refs(current_refs, audit_log_path)
    return current_xml, current_refs, remaining_missing_refs, missing_order_fetches


def enrich_orders_with_get_order_details(
    fetch_order_response,
    extract_result_xml,
    orders_xml_str,
    *,
    url,
    clientid,
    username,
    password,
):
    """Replace GetNewOrders rows with full GetOrder detail rows when available."""
    try:
        root = ET.fromstring(orders_xml_str)
    except ET.ParseError:
        return orders_xml_str, []

    order_elements = _order_elements_from_root(root)
    detail_fetches = []
    replacements = {}

    for order_elem in order_elements:
        ref = _order_ref_from_element(order_elem)
        if not ref:
            continue
        order_id = _order_id_from_ref_or_element(ref, order_elem)
        try:
            soap_bytes, http_status = fetch_order_response(
                url=url,
                clientid=clientid,
                username=username,
                password=password,
                order_ref=ref,
                order_id=order_id,
            )
            detail_xml = extract_result_xml(soap_bytes)
            detail_order_elem = _first_order_element_from_xml(detail_xml)
            detail_ref = _order_ref_from_element(detail_order_elem) if detail_order_elem is not None else None
            if detail_order_elem is not None and (not detail_ref or detail_ref == ref):
                replacements[ref] = detail_order_elem
            detail_fetches.append({
                'order_ref': ref,
                'order_id': order_id,
                'http_status': http_status,
                'detail_found': detail_order_elem is not None,
                'replaced': ref in replacements,
            })
        except RuntimeError as exc:
            detail_fetches.append({
                'order_ref': ref,
                'order_id': order_id,
                'error': str(exc),
                'detail_found': False,
                'replaced': False,
            })

    if not replacements:
        return orders_xml_str, detail_fetches

    target_root = ET.Element('web_orders')
    for order_elem in order_elements:
        ref = _order_ref_from_element(order_elem)
        target_root.append(replacements.get(ref, order_elem))

    return ET.tostring(target_root, encoding='unicode'), detail_fetches


def _first_order_element_from_xml(order_xml_str):
    if not order_xml_str:
        return None
    try:
        root = ET.fromstring(order_xml_str)
    except ET.ParseError:
        return None

    order_elements = _order_elements_from_root(root)
    return order_elements[0] if order_elements else None


def extract_soap_value(soap_bytes, key):
    """Return a top-level SOAP response value by key."""
    try:
        root = ET.fromstring(soap_bytes)
    except ET.ParseError:
        return None

    for item in root.iter():
        if _local_name(item.tag).lower() != 'item':
            continue
        key_el = _first_direct_child(item, 'key')
        val_el = _first_direct_child(item, 'value')
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


def merge_order_xml_payloads(primary_xml, secondary_xml):
    """Merge Tiaknight web_order XML payloads without duplicate order references."""
    if not secondary_xml:
        return primary_xml
    try:
        primary_root = ET.fromstring(primary_xml)
        secondary_root = ET.fromstring(secondary_xml)
    except ET.ParseError:
        return primary_xml

    primary_orders = _order_elements_from_root(primary_root)
    secondary_orders = _order_elements_from_root(secondary_root)
    seen_refs = {
        _order_ref_from_element(order_elem)
        for order_elem in primary_orders
        if _order_ref_from_element(order_elem)
    }

    target_root = primary_root
    if primary_root.tag.lower() in {'order', 'web_order'}:
        target_root = ET.Element('web_orders')
        target_root.append(primary_root)

    for order_elem in secondary_orders:
        ref = _order_ref_from_element(order_elem)
        if not ref or ref in seen_refs:
            continue
        target_root.append(order_elem)
        seen_refs.add(ref)

    return ET.tostring(target_root, encoding='unicode')


def _order_elements_from_root(root):
    if root.tag.lower() in {'order', 'web_order'}:
        return [root]
    return list(root)


def _order_ref_from_element(order_elem):
    if order_elem is None:
        return None
    order_node = order_elem.find('order')
    if order_node is None:
        order_node = order_elem
    return (
        _find_text(order_node, 'order_reference')
        or _find_text(order_node, 'order_id')
        or _find_text(order_elem, 'OrderNumber')
    )


def _order_id_from_ref_or_element(ref, order_elem):
    order_node = order_elem.find('order')
    if order_node is None:
        order_node = order_elem
    order_id = _find_text(order_node, 'order_id') or _find_text(order_elem, 'order_id')
    if order_id:
        return order_id

    return _order_id_from_ref(ref)


def _order_id_from_ref(ref):
    prefix, number = _split_order_ref(ref)
    return str(number) if number is not None else ''


def write_import_audit(
    *,
    audit_log_path,
    http_status,
    request_id,
    source_datetime,
    auto_update,
    file_type,
    order_refs,
    missing_sequence_refs=None,
    raw_payload_path=None,
    recovery_fetches=None,
    missing_order_fetches=None,
    detail_fetches=None,
):
    """Append received Tiaknight order refs to a dedicated audit log."""
    path = Path(audit_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = timezone.localtime()
    refs = ','.join(order_refs) if order_refs else '-'
    missing_refs = ','.join(missing_sequence_refs or []) if missing_sequence_refs else '-'
    raw_payload_note = f" raw_payload={raw_payload_path}" if raw_payload_path else ''
    recovery_note = f" recovery_attempts={len(recovery_fetches or [])}"
    missing_order_note = f" missing_get_order_fetches={len(missing_order_fetches or [])}"
    detail_note = f" detail_fetches={len(detail_fetches or [])}"
    line = (
        f"[{now:%Y-%m-%d %H:%M:%S %Z}] "
        f"http_status={http_status} request_id={request_id or '-'} "
        f"source_datetime={source_datetime or '-'} auto_update={auto_update} "
        f"file_type={file_type} orders_received={len(order_refs)} refs={refs}"
        f" missing_sequence_refs={missing_refs}"
        f"{recovery_note}"
        f"{missing_order_note}"
        f"{detail_note}"
        f"{raw_payload_note}\n"
    )
    with path.open('a', encoding='utf-8') as audit_log:
        audit_log.write(line)


def detect_missing_sequence_refs(order_refs, audit_log_path):
    """Detect numeric order-reference gaps against current payload and previous audit max."""
    current = [_split_order_ref(ref) for ref in order_refs]
    current = [(prefix, number) for prefix, number in current if prefix and number is not None]
    if not current:
        return []

    missing = set()
    by_prefix = {}
    for prefix, number in current:
        by_prefix.setdefault(prefix, set()).add(number)

    previous_max = _previous_max_refs_by_prefix(audit_log_path)
    for prefix, numbers in by_prefix.items():
        min_number = min(numbers)
        max_number = max(numbers)
        start = min_number
        if previous_max.get(prefix) and previous_max[prefix] < min_number:
            start = previous_max[prefix] + 1
        for number in range(start, max_number + 1):
            if number not in numbers:
                missing.add(f'{prefix}{number}')

    return sorted(missing, key=lambda ref: (_split_order_ref(ref)[0], _split_order_ref(ref)[1] or 0))


def _previous_max_refs_by_prefix(audit_log_path):
    path = Path(audit_log_path)
    if not path.exists():
        return {}

    max_by_prefix = {}
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return {}

    for line in lines:
        refs_value = _audit_value(line, 'refs')
        if not refs_value or refs_value == '-':
            continue
        for ref in refs_value.split(','):
            prefix, number = _split_order_ref(ref.strip())
            if not prefix or number is None:
                continue
            max_by_prefix[prefix] = max(number, max_by_prefix.get(prefix, number))
    return max_by_prefix


def _audit_value(line, key):
    marker = f'{key}='
    start = line.find(marker)
    if start == -1:
        return None
    start += len(marker)
    end = line.find(' ', start)
    if end == -1:
        end = len(line)
    return line[start:end].strip()


def _split_order_ref(ref):
    ref = str(ref or '').strip()
    if not ref:
        return None, None

    index = len(ref)
    while index > 0 and ref[index - 1].isdigit():
        index -= 1
    if index == len(ref):
        return ref, None
    return ref[:index], int(ref[index:])


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
    target = tag.lower()
    for child in list(element):
        if _local_name(child.tag).lower() == target and child.text:
            return child.text.strip()
    return None


def _first_direct_child(element, local_name):
    target = local_name.lower()
    for child in list(element):
        if _local_name(child.tag).lower() == target:
            return child
    return None


def _local_name(tag):
    return str(tag).rsplit('}', 1)[-1]


def _env_bool(value):
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

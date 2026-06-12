import io
import os

from dotenv import load_dotenv

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
    file_type = os.environ.get('TIA_FILE_TYPE', 'xml')

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
            auto_update='false',
            file_type=file_type,
        )
    except RuntimeError as exc:
        raise RemoteTiaknightFetchError(str(exc)) from exc

    orders_xml_str = extract_result_xml(soap_bytes)
    if orders_xml_str is None:
        raise RemoteTiaknightParseError('Could not find <Result> value in SOAP response')

    parser = XMLOrderParser()
    xml_file = io.BytesIO(orders_xml_str.encode('utf-8'))
    return parser.parse_and_create_orders(xml_file, user=user)

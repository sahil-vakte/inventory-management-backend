import base64
import logging
from decimal import Decimal

import requests
from django.conf import settings

from products.serializers import get_product_weight_kg


logger = logging.getLogger(__name__)


class DPDConfigError(ValueError):
    pass


class DPDAPIError(RuntimeError):
    def __init__(self, message, status_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class DPDShippingClient:
    """Client for DPD Shipping API shipment creation.

    DPD's public shipping docs use Bearer JWT auth for shipment calls. Some
    accounts receive a pre-generated token, while others receive key/secret
    credentials for a token endpoint, so both modes are supported by settings.
    """

    def __init__(self, timeout=30):
        self.enabled = settings.DPD_INTEGRATION_ENABLED
        self.base_url = settings.DPD_API_BASE_URL.rstrip('/')
        self.token_url = settings.DPD_TOKEN_URL
        self.api_key = settings.DPD_API_KEY
        self.api_secret = settings.DPD_API_SECRET
        self.api_token = settings.DPD_API_TOKEN
        self.customer_id = settings.DPD_CUSTOMER_ID
        self.bu_code = settings.DPD_BU_CODE
        self.default_service_code = settings.DPD_DEFAULT_SERVICE_CODE
        self.default_service_element_codes = settings.DPD_DEFAULT_SERVICE_ELEMENT_CODES
        self.default_weight_grams = settings.DPD_DEFAULT_WEIGHT_GRAMS
        self.print_format = settings.DPD_LABEL_FORMAT
        self.label_size = settings.DPD_LABEL_SIZE
        self.timeout = timeout

    def ensure_configured(self):
        missing = []
        if not self.enabled:
            missing.append('DPD_INTEGRATION_ENABLED=true')
        if not self.base_url:
            missing.append('DPD_API_BASE_URL')
        if not self.api_token and not (self.api_key and self.api_secret and self.token_url):
            missing.append('DPD_API_TOKEN or DPD_API_KEY + DPD_API_SECRET + DPD_TOKEN_URL')
        if not self.customer_id:
            missing.append('DPD_CUSTOMER_ID')
        if not self.bu_code:
            missing.append('DPD_BU_CODE')
        if not self.default_service_code:
            missing.append('DPD_DEFAULT_SERVICE_CODE')
        missing.extend(self._missing_sender_settings())
        if missing:
            raise DPDConfigError(f"Missing DPD settings: {', '.join(missing)}")

    def create_shipment(self, order, *, weight_in_grams=None, service_code=None):
        self.ensure_configured()
        payload = self.build_create_shipment_payload(
            order,
            weight_in_grams=weight_in_grams,
            service_code=service_code,
        )
        url = f'{self.base_url}/shipments'
        logger.info('Creating DPD shipment for local order %s', order.order_number)

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise DPDAPIError(f'DPD request failed: {exc}') from exc

        response_data = self._parse_response(response)
        if response.status_code >= 400:
            raise DPDAPIError(
                f'DPD returned HTTP {response.status_code}',
                status_code=response.status_code,
                response_data=response_data,
            )
        self._raise_for_messages(response_data, response.status_code)
        return response_data

    def build_create_shipment_payload(self, order, *, weight_in_grams=None, service_code=None):
        resolved_weight = int(weight_in_grams or self._order_weight_in_grams(order) or self.default_weight_grams)
        resolved_service = service_code or self.default_service_code
        parcel_weight_kg = max(Decimal(resolved_weight) / Decimal('1000'), Decimal('0.001'))

        shipment = {
            'numOrder': 1,
            'sender': self._sender_address(),
            'receiver': self._receiver_address(order),
            'parcels': [{
                'weight': float(parcel_weight_kg),
                'reference1': self._order_reference(order),
                'reference2': order.order_number or '',
                'reference3': order.courier_service_code or '',
            }],
            'service': {
                'mainServiceCode': resolved_service,
            },
            'reference1': self._order_reference(order),
            'reference2': order.order_number or '',
            'reference3': order.courier_service_code or '',
            'saveMode': 'printed',
            'printFormat': self.print_format,
            'labelSize': self.label_size,
            'extendShipmentData': True,
        }
        if self.default_service_element_codes:
            shipment['service']['mainServiceElementCodes'] = self.default_service_element_codes

        return {
            'buCode': self.bu_code,
            'customerId': self.customer_id,
            'shipments': [shipment],
        }

    def get_access_token(self):
        if self.api_token:
            return self.api_token

        try:
            response = requests.post(
                self.token_url,
                data={'grant_type': 'client_credentials'},
                auth=(self.api_key, self.api_secret),
                headers={'Accept': 'application/json'},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise DPDAPIError(f'DPD token request failed: {exc}') from exc

        response_data = self._parse_response(response)
        if response.status_code >= 400:
            raise DPDAPIError(
                f'DPD token endpoint returned HTTP {response.status_code}',
                status_code=response.status_code,
                response_data=response_data,
            )

        token = _find_first_value(response_data, {'access_token', 'token', 'jwt', 'id_token'})
        if not token:
            raise DPDAPIError(
                'DPD token response did not include an access token',
                status_code=response.status_code,
                response_data=response_data,
            )
        return token

    def _headers(self):
        return {
            'Authorization': f'Bearer {self.get_access_token()}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _sender_address(self):
        return {
            'name': settings.DPD_SENDER_NAME,
            'companyName': settings.DPD_SENDER_COMPANY,
            'countryCode': settings.DPD_SENDER_COUNTRY_CODE,
            'zipCode': settings.DPD_SENDER_POSTCODE,
            'city': settings.DPD_SENDER_CITY,
            'street': settings.DPD_SENDER_STREET,
            'address2': settings.DPD_SENDER_ADDRESS2,
            'contactName': settings.DPD_SENDER_CONTACT_NAME,
            'contactPhone': settings.DPD_SENDER_PHONE,
            'contactEmail': settings.DPD_SENDER_EMAIL,
        }

    def _receiver_address(self, order):
        return {
            'name': order.customer_name or 'Customer',
            'companyName': order.customer_company or '',
            'countryCode': self._country_code(order.shipping_country),
            'zipCode': order.shipping_postal_code or '',
            'city': order.shipping_city or '',
            'street': order.shipping_address_line1 or '',
            'address2': order.shipping_address_line2 or '',
            'contactName': order.customer_name or '',
            'contactPhone': order.customer_phone or '',
            'contactEmail': order.customer_email or '',
        }

    def _missing_sender_settings(self):
        required_pairs = [
            ('DPD_SENDER_NAME', settings.DPD_SENDER_NAME),
            ('DPD_SENDER_COUNTRY_CODE', settings.DPD_SENDER_COUNTRY_CODE),
            ('DPD_SENDER_POSTCODE', settings.DPD_SENDER_POSTCODE),
            ('DPD_SENDER_CITY', settings.DPD_SENDER_CITY),
            ('DPD_SENDER_STREET', settings.DPD_SENDER_STREET),
        ]
        return [name for name, value in required_pairs if not value]

    def _order_reference(self, order):
        return (order.external_order_id or order.order_number or str(order.id)).strip()

    def _order_weight_in_grams(self, order):
        total = Decimal('0.000')
        for item in order.items.select_related('stock_item__product').prefetch_related('stock_item__product__extended_data'):
            product = getattr(getattr(item, 'stock_item', None), 'product', None)
            total += get_product_weight_kg(product) * Decimal(item.quantity or 0)
        return int((total * Decimal('1000')).quantize(Decimal('1'))) if total > 0 else 0

    def _country_code(self, country):
        normalized = (country or '').strip().upper()
        if normalized in {'UK', 'GB', 'GREAT BRITAIN', 'UNITED KINGDOM', 'ENGLAND', 'SCOTLAND', 'WALES'}:
            return 'GB'
        if len(normalized) == 2:
            return normalized
        if len(normalized) == 3:
            return normalized[:2]
        return 'GB'

    def _parse_response(self, response):
        try:
            return response.json()
        except ValueError:
            return {'raw': response.text}

    def _raise_for_messages(self, response_data, status_code):
        messages = response_data.get('messages') if isinstance(response_data, dict) else None
        if isinstance(messages, list):
            errors = [
                message for message in messages
                if str(message.get('messageType', '')).upper() == 'ERROR'
            ]
            if errors:
                raise DPDAPIError(
                    'DPD did not create the shipment',
                    status_code=status_code,
                    response_data=response_data,
                )


def extract_dpd_label_pdf(response_data):
    label_value = _find_first_value(response_data, {'labelFile', 'label_file', 'label'})
    if not label_value:
        return None

    if isinstance(label_value, str) and ',' in label_value and 'base64' in label_value[:80].lower():
        label_value = label_value.split(',', 1)[1]

    try:
        return base64.b64decode(label_value, validate=True)
    except (ValueError, TypeError):
        return None


def extract_dpd_tracking_number(response_data):
    return _find_first_value(
        response_data,
        ('parcelNumber', 'parcelNo', 'trackingNumber', 'tracking_number', 'barcodeId', 'mpsidCckey'),
    )


def extract_dpd_shipment_identifier(response_data):
    shipment_results = response_data.get('shipmentResults') if isinstance(response_data, dict) else None
    if isinstance(shipment_results, list):
        found = _find_first_value(shipment_results, ('shipmentId', 'shipment_id'))
        if found:
            return found

    return _find_first_value(
        response_data,
        ('shipmentId', 'shipment_id', 'transactionId', 'transaction_id'),
    )


def _find_first_value(data, keys):
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if value:
                return str(value)
        for value in data.values():
            found = _find_first_value(value, keys)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_first_value(item, keys)
            if found:
                return found
    return None

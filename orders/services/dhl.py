import base64
import binascii
import re
from datetime import datetime, timezone
from decimal import Decimal

import requests
from django.conf import settings

from orders.services.courier import courier_service_code
from products.serializers import get_product_weight_kg


class DHLConfigError(ValueError):
    pass


class DHLAPIError(RuntimeError):
    def __init__(self, message, status_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class DHLShippingClient:
    """Client for DHL Express MyDHL shipment creation and inline labels."""

    def __init__(self, timeout=30):
        self.enabled = settings.DHL_INTEGRATION_ENABLED
        self.base_url = settings.DHL_API_BASE_URL.rstrip('/')
        self.client_id = settings.DHL_CLIENT_ID
        self.client_secret = settings.DHL_CLIENT_SECRET
        self.account_number = settings.DHL_ACCOUNT_NUMBER
        self.secondary_account_number = settings.DHL_SECONDARY_ACCOUNT_NUMBER
        self.default_product_code = settings.DHL_DEFAULT_PRODUCT_CODE
        self.default_weight_grams = settings.DHL_DEFAULT_WEIGHT_GRAMS
        self.default_length_cm = settings.DHL_DEFAULT_LENGTH_CM
        self.default_width_cm = settings.DHL_DEFAULT_WIDTH_CM
        self.default_height_cm = settings.DHL_DEFAULT_HEIGHT_CM
        self.label_template = settings.DHL_LABEL_TEMPLATE
        self.allow_international = settings.DHL_ALLOW_INTERNATIONAL
        self.timeout = timeout

    def ensure_configured(self):
        missing = []
        if not self.enabled:
            missing.append('DHL_INTEGRATION_ENABLED=true')
        if not self.base_url:
            missing.append('DHL_API_BASE_URL')
        if not self.client_id:
            missing.append('DHL_CLIENT_ID')
        if not self.client_secret:
            missing.append('DHL_CLIENT_SECRET')
        if not self.account_number:
            missing.append('DHL_ACCOUNT_NUMBER')
        missing.extend(self._missing_sender_settings())
        if missing:
            raise DHLConfigError(f"Missing DHL settings: {', '.join(missing)}")

    def resolve_shipping_options(self, order, *, weight_in_grams=None, service_code=None):
        resolved_weight = int(
            weight_in_grams or self._order_weight_in_grams(order) or self.default_weight_grams
        )
        delivery_method = self._delivery_method(order)
        route = get_dhl_route(order, resolved_weight, delivery_method=delivery_method)
        if not route:
            raise ValueError(
                'No DHL routing rule matched this order. DHL requires a qualifying item '
                'longer than 20 metres, a 6000-30000g order weight, and NEXT DAY delivery.'
            )

        product_code = (service_code or self.default_product_code or '').strip().upper()
        if not product_code:
            raise ValueError(
                'DHL product code is required. Set DHL_DEFAULT_PRODUCT_CODE or pass service_code.'
            )

        return {
            'weight_in_grams': resolved_weight,
            'shipment_type': 'PARCEL',
            'service_code': product_code,
            'delivery_method': delivery_method,
            'routing_reason': route['routing_reason'],
            'matched_item_skus': route['matched_item_skus'],
        }

    def create_shipment(
        self,
        order,
        *,
        weight_in_grams=None,
        service_code=None,
        account_number=None,
    ):
        self.ensure_configured()
        shipping_options = self.resolve_shipping_options(
            order,
            weight_in_grams=weight_in_grams,
            service_code=service_code,
        )
        resolved_account_number = self._resolve_account_number(account_number)
        payload = self.build_create_shipment_payload(
            order,
            weight_in_grams=shipping_options['weight_in_grams'],
            service_code=shipping_options['service_code'],
            account_number=resolved_account_number,
        )

        try:
            response = requests.post(
                f'{self.base_url}/shipments',
                json=payload,
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
                auth=(self.client_id, self.client_secret),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise DHLAPIError(f'DHL request failed: {exc}') from exc

        response_data = self._parse_response(response)
        if response.status_code >= 400:
            raise DHLAPIError(
                f'DHL returned HTTP {response.status_code}',
                status_code=response.status_code,
                response_data=response_data,
            )
        return response_data

    def build_create_shipment_payload(
        self,
        order,
        *,
        weight_in_grams,
        service_code,
        account_number,
    ):
        destination_country = self._country_code(order.shipping_country)
        is_customs_declarable = destination_country != 'GB'
        if is_customs_declarable and not self.allow_international:
            raise ValueError(
                'DHL international booking is disabled until customs data is configured. '
                'Set DHL_ALLOW_INTERNATIONAL=true only after confirming customs requirements.'
            )

        payload = {
            'plannedShippingDateAndTime': _dhl_planned_shipping_datetime(),
            'pickup': {'isRequested': False},
            'productCode': service_code,
            'accounts': [{'typeCode': 'shipper', 'number': account_number}],
            'customerReferences': [{
                'value': self._order_reference(order),
                'typeCode': 'CU',
            }],
            'customerDetails': {
                'shipperDetails': self._shipper_details(),
                'receiverDetails': self._receiver_details(order),
            },
            'content': {
                'packages': [{
                    'weight': self._weight_kg(weight_in_grams),
                    'dimensions': {
                        'length': self.default_length_cm,
                        'width': self.default_width_cm,
                        'height': self.default_height_cm,
                    },
                }],
                'isCustomsDeclarable': is_customs_declarable,
                'description': self._content_description(order),
                'unitOfMeasurement': 'metric',
            },
            'outputImageProperties': {
                'printerDPI': 300,
                'encodingFormat': 'pdf',
                'imageOptions': [{
                    'typeCode': 'label',
                    'templateName': self.label_template,
                    'isRequested': True,
                }],
            },
            'getAdditionalInformation': [{'typeCode': 'allCheck'}],
        }
        if is_customs_declarable:
            payload['content']['exportDeclaration'] = self._export_declaration(order)
        return payload

    def _resolve_account_number(self, requested_account_number):
        requested = (requested_account_number or self.account_number).strip()
        permitted = {
            value for value in (self.account_number, self.secondary_account_number) if value
        }
        if requested not in permitted:
            raise ValueError('The requested DHL account number is not configured for WIMS.')
        return requested

    def _shipper_details(self):
        return {
            'postalAddress': {
                'postalCode': settings.DHL_SENDER_POSTCODE,
                'cityName': settings.DHL_SENDER_CITY,
                'countryCode': settings.DHL_SENDER_COUNTRY_CODE,
                'addressLine1': settings.DHL_SENDER_STREET,
                **(
                    {'addressLine2': settings.DHL_SENDER_ADDRESS2}
                    if settings.DHL_SENDER_ADDRESS2 else {}
                ),
            },
            'contactInformation': {
                'fullName': settings.DHL_SENDER_CONTACT_NAME or settings.DHL_SENDER_NAME,
                'companyName': settings.DHL_SENDER_COMPANY or settings.DHL_SENDER_NAME,
                'phone': _dhl_phone(settings.DHL_SENDER_PHONE),
                'email': settings.DHL_SENDER_EMAIL,
            },
        }

    def _receiver_details(self, order):
        if not all([order.customer_name, order.shipping_address_line1, order.shipping_city, order.shipping_postal_code]):
            raise ValueError(
                'DHL requires customer name, shipping address line 1, city, and postcode.'
            )
        address = {
            'postalCode': order.shipping_postal_code,
            'cityName': order.shipping_city,
            'countryCode': self._country_code(order.shipping_country),
            'addressLine1': order.shipping_address_line1,
        }
        if order.shipping_address_line2:
            address['addressLine2'] = order.shipping_address_line2
        if order.shipping_state:
            address['countyName'] = order.shipping_state

        contact = {
            'fullName': order.customer_name,
            'companyName': order.customer_company or order.customer_name,
        }
        if order.customer_phone:
            contact['phone'] = _dhl_phone(order.customer_phone)
        if order.customer_email:
            contact['email'] = order.customer_email
        return {'postalAddress': address, 'contactInformation': contact}

    def _export_declaration(self, order):
        line_items = []
        for number, item in enumerate(order.items.all(), start=1):
            product = getattr(getattr(item, 'stock_item', None), 'product', None)
            extended = product.extended_data.first() if product else None
            commodity_code = (getattr(extended, 'child_commodity_code', '') or '').strip()
            if not commodity_code:
                raise ValueError(
                    f'DHL international booking requires a commodity code for item {item.sku}.'
                )
            unit_weight = get_product_weight_kg(product)
            line_items.append({
                'number': number,
                'description': (
                    getattr(extended, 'child_customs_description', '')
                    or item.product_name
                )[:75],
                'price': float(item.unit_price),
                'quantity': item.quantity,
                'commodityCodes': [{'typeCode': 'outbound', 'value': commodity_code}],
                'exportReasonType': 'permanent',
                'manufacturerCountry': {'countryCode': (
                    getattr(extended, 'child_country_of_origin', '') or 'GB'
                ).upper()},
                'weight': {'netValue': float(unit_weight * Decimal(item.quantity)), 'grossValue': float(unit_weight * Decimal(item.quantity))},
            })
        return {
            'invoice': {
                'number': self._order_reference(order),
                'date': datetime.now(timezone.utc).date().isoformat(),
                'signatureName': settings.DHL_SENDER_CONTACT_NAME or settings.DHL_SENDER_NAME,
            },
            'lineItems': line_items,
        }

    def _missing_sender_settings(self):
        required = {
            'DHL_SENDER_NAME': settings.DHL_SENDER_NAME,
            'DHL_SENDER_POSTCODE': settings.DHL_SENDER_POSTCODE,
            'DHL_SENDER_CITY': settings.DHL_SENDER_CITY,
            'DHL_SENDER_STREET': settings.DHL_SENDER_STREET,
            'DHL_SENDER_PHONE': settings.DHL_SENDER_PHONE,
            'DHL_SENDER_EMAIL': settings.DHL_SENDER_EMAIL,
        }
        return [name for name, value in required.items() if not value]

    def _order_weight_in_grams(self, order):
        total = Decimal('0')
        for item in order.items.all():
            product = getattr(getattr(item, 'stock_item', None), 'product', None)
            total += get_product_weight_kg(product) * Decimal(item.quantity or 0)
        return int((total * Decimal('1000')).quantize(Decimal('1')))

    def _delivery_method(self, order):
        return (
            order.courier_service_code
            or courier_service_code(order.courier_service_name)
            or courier_service_code(order.shipping_method)
            or order.shipping_method
            or ''
        ).strip().upper()

    def _content_description(self, order):
        item = order.items.first()
        return (item.product_name if item else 'Textile goods')[:75]

    def _order_reference(self, order):
        return order.external_order_id or order.order_number or f'ORDER-{order.id}'

    @staticmethod
    def _weight_kg(weight_in_grams):
        return float(max(Decimal(weight_in_grams) / Decimal('1000'), Decimal('0.001')))

    @staticmethod
    def _country_code(value):
        normalized = (value or 'GB').strip().upper()
        return {
            'UK': 'GB',
            'UNITED KINGDOM': 'GB',
            'ENGLAND': 'GB',
            'SCOTLAND': 'GB',
            'WALES': 'GB',
            'NORTHERN IRELAND': 'GB',
        }.get(normalized, normalized[:2])

    @staticmethod
    def _parse_response(response):
        try:
            return response.json()
        except ValueError:
            return {'raw': response.text[:10000]}


def get_dhl_route(order, weight_in_grams, *, delivery_method=None):
    delivery_method = (delivery_method or '').upper().strip()
    if not (6000 <= int(weight_in_grams or 0) <= 30000):
        return None
    if delivery_method != 'NEXT DAY':
        return None

    matched_item_skus = []
    for item in order.items.all():
        if _item_has_qualifying_length(item):
            matched_item_skus.append(item.sku)
    if not matched_item_skus:
        return None

    return {
        'routing_reason': 'Qualifying item longer than 20m, 6000-30000g order weight, and NEXT DAY delivery.',
        'matched_item_skus': matched_item_skus,
    }


def extract_dhl_label_pdf(data):
    for document in _dhl_documents(data):
        if str(document.get('typeCode', '')).lower() != 'label':
            continue
        content = document.get('content') or document.get('image') or document.get('documentImage')
        decoded = _decode_base64(content)
        if decoded and decoded.startswith(b'%PDF'):
            return decoded
    return None


def extract_dhl_shipment_identifier(data):
    return _find_first_value(data, {'shipmenttrackingnumber', 'shipmentid', 'shipmentnumber'})


def extract_dhl_tracking_number(data):
    return _find_first_value(data, {'shipmenttrackingnumber', 'trackingnumber', 'waybillnumber'})


def _dhl_documents(data):
    if not isinstance(data, dict):
        return []
    documents = data.get('documents') or data.get('documentImages') or []
    return documents if isinstance(documents, list) else []


def _decode_base64(value):
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().split(',', 1)[-1]
    try:
        return base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error):
        return None


def _find_first_value(data, keys):
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in keys and value:
                return str(value)
            result = _find_first_value(value, keys)
            if result:
                return result
    elif isinstance(data, list):
        for value in data:
            result = _find_first_value(value, keys)
            if result:
                return result
    return None


def _item_has_qualifying_length(item):
    product_name = item.product_name or ''
    normalized_name = product_name.lower()
    if any(value in normalized_name for value in ('fleece', 'lace', 'trimming', 'elastic tape')):
        return False

    product = getattr(getattr(item, 'stock_item', None), 'product', None)
    values = [product_name, getattr(product, 'attribute_length', '') if product else '']
    if product:
        values.extend(
            data.attribute_1_length or ''
            for data in product.extended_data.all()
        )
    return any(_length_in_metres(value) > Decimal('20') for value in values)


def _length_in_metres(value):
    if not value:
        return Decimal('0')
    matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:mtr|mtrs|metre|metres|meter|meters|m)\b', str(value), re.IGNORECASE)
    return max((Decimal(match) for match in matches), default=Decimal('0'))


def _dhl_planned_shipping_datetime():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S GMT+00:00')


def _dhl_phone(value):
    cleaned = re.sub(r'[^0-9+]', '', value or '')
    if cleaned.startswith('00'):
        cleaned = '+' + cleaned[2:]
    return cleaned

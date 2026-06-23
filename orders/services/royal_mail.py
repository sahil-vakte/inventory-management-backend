import logging
from decimal import Decimal

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


class RoyalMailConfigError(ValueError):
    pass


class RoyalMailAPIError(RuntimeError):
    def __init__(self, message, status_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class RoyalMailClickDropClient:
    """Client for Royal Mail Click & Drop API order creation."""

    def __init__(self, api_key=None, base_url=None, timeout=30):
        self.api_key = api_key if api_key is not None else settings.ROYAL_MAIL_API_KEY
        self.base_url = (base_url or settings.ROYAL_MAIL_API_BASE_URL).rstrip('/')
        self.timeout = timeout

    def ensure_configured(self):
        if not self.api_key:
            raise RoyalMailConfigError('ROYAL_MAIL_API_KEY is not configured')
        if not self.base_url:
            raise RoyalMailConfigError('ROYAL_MAIL_API_BASE_URL is not configured')

    def create_order(self, order, *, weight_in_grams=None, package_format_identifier=None, service_code=None):
        self.ensure_configured()
        payload = self.build_create_order_payload(
            order,
            weight_in_grams=weight_in_grams,
            package_format_identifier=package_format_identifier,
            service_code=service_code,
        )
        url = f'{self.base_url}/Orders'
        logger.info('Creating Royal Mail order for local order %s', order.order_number)

        try:
            response = requests.post(
                url,
                json=payload,
                headers={
                    'Authorization': self.api_key,
                    'Content-Type': 'application/json',
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RoyalMailAPIError(f'Royal Mail request failed: {exc}') from exc

        response_data = self._parse_response(response)
        if response.status_code >= 400:
            raise RoyalMailAPIError(
                f'Royal Mail returned HTTP {response.status_code}',
                status_code=response.status_code,
                response_data=response_data,
            )

        return response_data

    def build_create_order_payload(self, order, *, weight_in_grams=None, package_format_identifier=None, service_code=None):
        weight_in_grams = weight_in_grams or settings.ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS
        package_format_identifier = package_format_identifier or settings.ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT

        package = {
            'weightInGrams': int(weight_in_grams),
            'packageFormatIdentifier': package_format_identifier,
            'contents': [self._content_from_item(item) for item in order.items.all()],
        }

        royal_mail_order = {
            'orderReference': order.order_number,
            'recipient': {
                'address': {
                    'fullName': order.customer_name,
                    'companyName': order.customer_company or '',
                    'addressLine1': order.shipping_address_line1 or '',
                    'addressLine2': order.shipping_address_line2 or '',
                    'city': order.shipping_city or '',
                    'county': order.shipping_state or '',
                    'postcode': order.shipping_postal_code or '',
                    'countryCode': self._country_code(order.shipping_country),
                },
                'phoneNumber': order.customer_phone or '',
                'emailAddress': order.customer_email or '',
            },
            'orderDate': order.order_date.isoformat() if order.order_date else None,
            'subtotal': self._money(order.subtotal),
            'shippingCostCharged': self._money(order.shipping_cost),
            'total': self._money(order.total_amount),
            'currencyCode': 'GBP',
            'packages': [package],
        }
        if service_code:
            royal_mail_order['postageDetails'] = {'serviceCode': service_code}

        return {'items': [royal_mail_order]}

    def _content_from_item(self, item):
        unit_value = item.unit_price or Decimal('0.00')
        return {
            'name': item.product_name,
            'SKU': item.sku,
            'quantity': item.quantity,
            'unitValue': self._money(unit_value),
            'unitWeightInGrams': 0,
        }

    def _country_code(self, country):
        normalized = (country or '').strip().upper()
        if normalized in {'UK', 'GB', 'GREAT BRITAIN', 'UNITED KINGDOM', 'ENGLAND', 'SCOTLAND', 'WALES'}:
            return 'GBR'
        if len(normalized) == 3:
            return normalized
        if len(normalized) == 2:
            return normalized
        return 'GBR'

    def _money(self, value):
        if value is None:
            return 0
        return float(value)

    def _parse_response(self, response):
        try:
            return response.json()
        except ValueError:
            return {'raw': response.text}


def extract_royal_mail_reference(response_data):
    return _find_first_value(
        response_data,
        {'orderIdentifier', 'orderId', 'identifier', 'royalMailOrderId', 'orderReference'},
    )


def extract_tracking_number(response_data):
    return _find_first_value(response_data, {'trackingNumber', 'tracking_number'})


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

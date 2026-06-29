import logging
from decimal import Decimal
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from orders.models import RoyalMailOAuthToken


logger = logging.getLogger(__name__)


class RoyalMailConfigError(ValueError):
    pass


class RoyalMailAPIError(RuntimeError):
    def __init__(self, message, status_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class RoyalMailOAuthError(RuntimeError):
    def __init__(self, message, status_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class RoyalMailOAuthClient:
    """OAuth helper for connecting WIMS to Royal Mail Click & Drop."""

    def __init__(self, timeout=30):
        self.client_id = settings.ROYAL_MAIL_CLIENT_ID
        self.client_secret = settings.ROYAL_MAIL_CLIENT_SECRET
        self.callback_url = settings.ROYAL_MAIL_OAUTH_CALLBACK_URL
        self.authorization_url = settings.ROYAL_MAIL_OAUTH_AUTHORIZATION_URL
        self.token_url = settings.ROYAL_MAIL_OAUTH_TOKEN_URL
        self.scope = settings.ROYAL_MAIL_OAUTH_SCOPE
        self.timeout = timeout

    def ensure_configured(self):
        missing = []
        if not self.client_id:
            missing.append('ROYAL_MAIL_CLIENT_ID')
        if not self.client_secret:
            missing.append('ROYAL_MAIL_CLIENT_SECRET')
        if not self.callback_url:
            missing.append('ROYAL_MAIL_OAUTH_CALLBACK_URL')
        if not self.authorization_url:
            missing.append('ROYAL_MAIL_OAUTH_AUTHORIZATION_URL')
        if not self.token_url:
            missing.append('ROYAL_MAIL_OAUTH_TOKEN_URL')
        if missing:
            raise RoyalMailConfigError(f"Missing Royal Mail OAuth settings: {', '.join(missing)}")

    def build_authorization_url(self, state=None):
        self.ensure_configured()
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.callback_url,
        }
        if self.scope:
            params['scope'] = self.scope
        if state:
            params['state'] = state
        return f"{self.authorization_url}?{urlencode(params)}"

    def exchange_code(self, code):
        self.ensure_configured()
        if not code:
            raise RoyalMailOAuthError('Royal Mail callback code is required')
        return self._request_token({
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.callback_url,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        })

    def refresh_token(self, token=None):
        self.ensure_configured()
        token = token or RoyalMailOAuthToken.get_active()
        if not token or not token.refresh_token:
            raise RoyalMailOAuthError('Royal Mail refresh token is not available')
        return self._request_token({
            'grant_type': 'refresh_token',
            'refresh_token': token.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        })

    def get_valid_access_token(self):
        token = RoyalMailOAuthToken.get_active()
        if not token:
            raise RoyalMailConfigError('Royal Mail OAuth is not connected')
        if token.needs_refresh and token.refresh_token:
            token = self.refresh_token(token)
        if token.is_expired:
            raise RoyalMailConfigError('Royal Mail OAuth token is expired; reconnect Royal Mail')
        return token.access_token

    def _request_token(self, data):
        try:
            response = requests.post(
                self.token_url,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RoyalMailOAuthError(f'Royal Mail OAuth request failed: {exc}') from exc

        response_data = self._parse_response(response)
        if response.status_code >= 400:
            raise RoyalMailOAuthError(
                f'Royal Mail OAuth returned HTTP {response.status_code}',
                status_code=response.status_code,
                response_data=response_data,
            )

        access_token = response_data.get('access_token')
        if not access_token:
            raise RoyalMailOAuthError(
                'Royal Mail OAuth response did not include an access token',
                status_code=response.status_code,
                response_data=response_data,
            )

        expires_at = None
        expires_in = response_data.get('expires_in')
        if expires_in:
            try:
                expires_at = timezone.now() + timezone.timedelta(seconds=int(expires_in))
            except (TypeError, ValueError):
                expires_at = None

        RoyalMailOAuthToken.objects.filter(is_active=True).update(is_active=False)
        return RoyalMailOAuthToken.objects.create(
            access_token=access_token,
            refresh_token=response_data.get('refresh_token'),
            token_type=response_data.get('token_type'),
            scope=response_data.get('scope'),
            expires_at=expires_at,
            raw_response=response_data,
            is_active=True,
        )

    def _parse_response(self, response):
        try:
            return response.json()
        except ValueError:
            return {'raw': response.text}


class RoyalMailClickDropClient:
    """Client for Royal Mail Click & Drop API order creation."""

    def __init__(self, api_key=None, base_url=None, timeout=30):
        self.api_key = api_key if api_key is not None else settings.ROYAL_MAIL_API_KEY
        self.base_url = (base_url or settings.ROYAL_MAIL_API_BASE_URL).rstrip('/')
        self.timeout = timeout

    def ensure_configured(self):
        if not self.base_url:
            raise RoyalMailConfigError('ROYAL_MAIL_API_BASE_URL is not configured')
        if not self.api_key:
            raise RoyalMailConfigError('ROYAL_MAIL_API_KEY is not configured')

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
                headers=self._headers(),
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
        self._raise_for_order_errors(response_data, response.status_code)

        return response_data

    def _headers(self):
        return {
            'Authorization': self.api_key.strip(),
            'Content-Type': 'application/json',
        }

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
            'billing': self._billing_from_order(order),
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

    def _billing_from_order(self, order):
        address_line1 = order.billing_address_line1 or order.shipping_address_line1 or ''
        address_line2 = order.billing_address_line2 or order.shipping_address_line2 or ''
        city = order.billing_city or order.shipping_city or ''
        county = order.billing_state or order.shipping_state or ''
        postcode = order.billing_postal_code or order.shipping_postal_code or ''
        country = order.billing_country or order.shipping_country

        return {
            'address': {
                'fullName': order.customer_name,
                'companyName': order.customer_company or '',
                'addressLine1': address_line1,
                'addressLine2': address_line2,
                'city': city,
                'county': county,
                'postcode': postcode,
                'countryCode': self._country_code(country),
            },
            'phoneNumber': order.customer_phone or '',
            'emailAddress': order.customer_email or '',
        }

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

    def _raise_for_order_errors(self, response_data, status_code):
        if not isinstance(response_data, dict):
            return

        failed_orders = response_data.get('failedOrders') or []
        errors_count = response_data.get('errorsCount')
        success_count = response_data.get('successCount')
        created_orders = response_data.get('createdOrders')

        has_failed_orders = bool(failed_orders)
        has_errors = False
        if errors_count is not None:
            try:
                has_errors = int(errors_count) > 0
            except (TypeError, ValueError):
                has_errors = bool(errors_count)

        parsed_success_count = None
        if success_count is not None:
            try:
                parsed_success_count = int(success_count or 0)
            except (TypeError, ValueError):
                parsed_success_count = None

        no_created_orders = (
            parsed_success_count == 0
            and created_orders is not None
            and len(created_orders) == 0
        )

        if has_failed_orders or has_errors or no_created_orders:
            raise RoyalMailAPIError(
                'Royal Mail did not create the shipment',
                status_code=status_code,
                response_data=response_data,
            )


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

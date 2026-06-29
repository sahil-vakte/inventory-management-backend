# Tests for Order Management with Employee Assignment
import io
import os
import tempfile
from django.test import TestCase
from django.test import override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from xml.sax.saxutils import escape
from rest_framework.test import APIClient
from .models import Order, OrderItem, RoyalMailOAuthToken
from .services.xml_parser import XMLOrderParser
from colors.models import Color
from products.models import Product
from stock.models import StockItem


class EmployeeOrderAssignmentTest(TestCase):
    """Test employee assignment functionality and manual stock management"""
    
    def setUp(self):
        """Set up test users"""
        self.admin = User.objects.create_user(
            username='admin_test',
            password='test123',
            is_staff=True
        )
        self.employee = User.objects.create_user(
            username='employee_test',
            password='test123'
        )
    
    def test_order_has_assigned_to_field(self):
        """Test that Order model has assigned_to field"""
        order = Order.objects.create(
            customer_name="Test Customer",
            customer_email="test@example.com",
            total_amount=Decimal('100.00'),
            created_by=self.admin
        )
        self.assertIsNone(order.assigned_to)
        self.assertIn('assigned_to', [f.name for f in Order._meta.get_fields()])
    
    def test_employee_assignment(self):
        """Test assigning employee to order"""
        order = Order.objects.create(
            customer_name="Test Customer",
            total_amount=Decimal('100.00'),
            created_by=self.admin
        )
        
        order.assigned_to = self.employee
        order.save()
        order.refresh_from_db()
        
        self.assertEqual(order.assigned_to, self.employee)
    
    def test_employee_unassignment(self):
        """Test removing employee assignment"""
        order = Order.objects.create(
            customer_name="Test Customer",
            total_amount=Decimal('100.00'),
            created_by=self.admin,
            assigned_to=self.employee
        )
        
        order.assigned_to = None
        order.save()
        order.refresh_from_db()
        
        self.assertIsNone(order.assigned_to)
    
    def test_filter_by_assigned_employee(self):
        """Test filtering orders by assigned employee"""
        order1 = Order.objects.create(
            customer_name="Customer 1",
            total_amount=Decimal('100.00'),
            created_by=self.admin,
            assigned_to=self.employee
        )
        order2 = Order.objects.create(
            customer_name="Customer 2",
            total_amount=Decimal('200.00'),
            created_by=self.admin
        )
        
        assigned_orders = Order.objects.filter(assigned_to=self.employee)
        
        self.assertEqual(assigned_orders.count(), 1)
        self.assertIn(order1, assigned_orders)
        self.assertNotIn(order2, assigned_orders)
    
    def test_orderitem_removed_stock_fields(self):
        """Test that OrderItem no longer has stock tracking fields"""
        item_fields = [f.name for f in OrderItem._meta.get_fields()]
        
        self.assertNotIn('stock_reserved', item_fields)
        self.assertNotIn('stock_fulfilled', item_fields)
    
    def test_orderitem_removed_stock_methods(self):
        """Test that OrderItem removed stock management methods"""
        self.assertFalse(hasattr(OrderItem, 'reserve_stock'))
        self.assertFalse(hasattr(OrderItem, 'release_stock'))
    
    def test_order_cancel_no_auto_stock_release(self):
        """Test that cancelling order doesn't automatically release stock"""
        order = Order.objects.create(
            customer_name="Test Customer",
            total_amount=Decimal('100.00'),
            created_by=self.admin,
            order_status=Order.STATUS_LABEL_PRINTED
        )
        
        # Cancel order - should not raise any stock-related errors
        order.cancel(reason="Test cancellation", user=self.admin)
        
        self.assertEqual(order.order_status, Order.STATUS_CANCELLED)
    
    def test_order_soft_delete_no_auto_stock_release(self):
        """Test that soft deleting order doesn't automatically release stock"""
        order = Order.objects.create(
            customer_name="Test Customer",
            total_amount=Decimal('100.00'),
            created_by=self.admin
        )
        
        # Soft delete - should not raise any stock-related errors
        order.soft_delete(user=self.admin)
        
        self.assertTrue(order.is_deleted)
        self.assertIsNotNone(order.deleted_at)


class StockManagementTest(TestCase):
    """Test manual stock management methods"""
    
    def test_stock_item_has_reserve_method(self):
        """Test that StockItem still has reserve_stock method"""
        self.assertTrue(hasattr(StockItem, 'reserve_stock'))
    
    def test_stock_item_has_release_method(self):
        """Test that StockItem still has release_stock method"""
        self.assertTrue(hasattr(StockItem, 'release_stock'))
    
    def test_stock_item_has_adjust_method(self):
        """Test that StockItem still has adjust_stock method"""
        self.assertTrue(hasattr(StockItem, 'adjust_stock'))


class RemoteTiaknightImportAuditTest(TestCase):
    @patch('orders.services.remote_tiaknight_import.XMLOrderParser.parse_and_create_orders')
    @patch('scripts.soap_client.fetch_soap_response')
    def test_import_reads_auto_update_and_writes_received_refs_audit(self, mock_fetch, mock_parse):
        from orders.services.remote_tiaknight_import import import_remote_tiaknight_orders

        orders_xml = (
            '<web_orders>'
            '<web_order><order><order_reference>WEB100001</order_reference></order></web_order>'
            '<web_order><order><order_reference>WEB100002</order_reference></order></web_order>'
            '</web_orders>'
        )
        soap_response = (
            '<Envelope><Body>'
            '<item><key>RequestID</key><value>REQ-1</value></item>'
            '<item><key>DateTime</key><value>2026-06-27 16:50:45</value></item>'
            f'<item><key>Result</key><value>{escape(orders_xml)}</value></item>'
            '</Body></Envelope>'
        ).encode('utf-8')
        mock_fetch.return_value = (soap_response, 200)
        mock_parse.return_value = {
            'created_count': 2,
            'failed_count': 0,
            'orders': [],
            'errors': [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = os.path.join(tmpdir, 'tiaknight_refs.log')
            with patch.dict(os.environ, {
                'TIA_URL': 'https://www.tiaknightfabrics.co.uk/api/soap/service',
                'TIA_CLIENTID': 'Tiaknightfabrics',
                'TIA_USERNAME': 'UserTiaknightfabrics341',
                'TIA_PASSWORD': 'secret',
                'TIA_AUTO_UPDATE': 'true',
                'TIA_FILE_TYPE': 'xml',
                'TIA_AUDIT_LOG_PATH': audit_path,
                'TIA_SAVE_RAW_PAYLOAD': 'false',
            }, clear=False):
                result = import_remote_tiaknight_orders(user=None)

            self.assertEqual(mock_fetch.call_args.kwargs['auto_update'], 'true')
            self.assertEqual(result['received_order_refs_count'], 2)
            self.assertEqual(result['received_order_refs'], ['WEB100001', 'WEB100002'])
            self.assertEqual(result['tiaknight_request_id'], 'REQ-1')

            with open(audit_path, encoding='utf-8') as audit_file:
                audit_line = audit_file.read()
            self.assertIn('request_id=REQ-1', audit_line)
            self.assertIn('auto_update=true', audit_line)
            self.assertIn('orders_received=2', audit_line)
            self.assertIn('refs=WEB100001,WEB100002', audit_line)


class OrderWithItemsAPITest(TestCase):
    """Test order list endpoint with nested order items"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='api_user',
            password='test123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_with_items_returns_orders_with_nested_items(self):
        order = Order.objects.create(
            customer_name='Test Customer',
            customer_email='test@example.com',
            total_amount=Decimal('25.00'),
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SKU-001',
            product_name='Test Product',
            quantity=2,
            quantity_ordered=2,
            unit_price=Decimal('12.50'),
        )

        response = self.client.get('/api/v1/orders/with-items/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], order.id)
        self.assertEqual(len(response.data['results'][0]['items']), 1)
        self.assertEqual(response.data['results'][0]['items'][0]['sku'], 'SKU-001')
        self.assertFalse(response.data['results'][0]['items'][0]['lable_printed'])

    def test_order_detail_returns_item_lable_printed(self):
        order = Order.objects.create(
            customer_name='Detail Customer',
            customer_email='detail@example.com',
            total_amount=Decimal('25.00'),
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SKU-001',
            product_name='Test Product',
            quantity=2,
            quantity_ordered=2,
            unit_price=Decimal('12.50'),
            lable_printed=True,
        )

        response = self.client.get(f'/api/v1/orders/{order.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['items']), 1)
        self.assertTrue(response.data['items'][0]['lable_printed'])

    def test_order_items_list_returns_available_stock_in_mtr(self):
        color = Color.objects.create(
            color_code='TST',
            color_name='Test Color',
        )
        product = Product.objects.create(
            vs_parent_id=10101,
            vs_child_id=10101,
            parent_reference='STOCK',
            parent_product_title='Stock Product',
            child_reference='STOCK SKU',
            child_product_title='Stock Product',
        )
        stock_item = StockItem.objects.create(
            sku='STOCK SKU',
            product_type='STOCK',
            product=product,
            color=color,
            available_stock_in_mtr=42,
        )
        order = Order.objects.create(
            customer_name='Stock Customer',
            customer_email='stock@example.com',
            total_amount=Decimal('10.00'),
            created_by=self.user,
        )
        item = OrderItem.objects.create(
            order=order,
            stock_item=stock_item,
            sku='STOCK SKU',
            product_name='Stock Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.get('/api/v1/order-items/')

        self.assertEqual(response.status_code, 200)
        result = next(row for row in response.data['results'] if row['id'] == item.id)
        self.assertEqual(result['available_stock_in_mtr'], 42)

    def test_xml_import_saves_tiaknight_courier_fields(self):
        xml_data = b'''
        <web_orders>
          <web_order>
            <order>
              <order_reference>WEB-C001</order_reference>
              <order_state>Payment Received</order_state>
              <order_date>2026-06-29 10:00:00</order_date>
              <courier_name>Next Day By 12pm (next working day if ordered before 1pm)</courier_name>
              <grand_total_inc>12.50</grand_total_inc>
            </order>
            <customer>
              <billing_firstname>Courier</billing_firstname>
              <billing_lastname>Customer</billing_lastname>
              <billing_email>courier@example.com</billing_email>
              <delivery_address1>1 Delivery Street</delivery_address1>
              <delivery_town>London</delivery_town>
              <delivery_postcode>SW1A 1AA</delivery_postcode>
            </customer>
            <payment>
              <payment_type>Card</payment_type>
            </payment>
            <products>
              <product>
                <product_reference>SKU-C001</product_reference>
                <title>Courier Product</title>
                <quantity>1</quantity>
                <price_inc>12.50</price_inc>
              </product>
            </products>
          </web_order>
        </web_orders>
        '''

        result = XMLOrderParser().parse_and_create_orders(io.BytesIO(xml_data), user=self.user)

        self.assertEqual(result['created_count'], 1)
        order = Order.objects.get(external_order_id='WEB-C001')
        self.assertEqual(order.courier_service_name, 'Next Day By 12pm (next working day if ordered before 1pm)')
        self.assertEqual(order.courier_service_code, 'NEXT DAY 12')
        self.assertEqual(order.shipping_method, order.courier_service_name)
        self.assertEqual(order.carrier, order.courier_service_name)

        detail_response = self.client.get(f'/api/v1/orders/{order.id}/')
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data['courier_service_code'], 'NEXT DAY 12')

    def test_label_excel_exports_courier_code_per_order_item(self):
        order = Order.objects.create(
            customer_name='Excel Customer',
            customer_email='excel@example.com',
            external_order_id='WEB-EXCEL',
            courier_service_name='Standard Delivery',
            courier_service_code='STD',
            shipping_method='Standard Delivery',
            carrier='Standard Delivery',
            total_amount=Decimal('20.00'),
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SKU-EXCEL',
            product_name='Excel Product',
            quantity=2,
            quantity_ordered=2,
            unit_price=Decimal('10.00'),
        )

        response = self.client.get('/api/v1/orders/label-excel/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(response.content))
        worksheet = workbook.active
        headers = [cell.value for cell in worksheet[1]]
        values = [cell.value for cell in worksheet[2]]
        row = dict(zip(headers, values))

        self.assertEqual(row['Order Number'], order.order_number)
        self.assertEqual(row['SKU'], 'SKU-EXCEL')
        self.assertEqual(row['Courier Service'], 'Standard Delivery')
        self.assertEqual(row['Courier Code'], 'STD')

    def test_with_items_keeps_order_filters(self):
        pending_order = Order.objects.create(
            customer_name='Pending Customer',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_NEW,
            created_by=self.user,
        )
        Order.objects.create(
            customer_name='Shipped Customer',
            total_amount=Decimal('20.00'),
            order_status=Order.STATUS_SHIPPED,
            created_by=self.user,
        )

        response = self.client.get('/api/v1/orders/with-items/?order_status=NEW')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], pending_order.id)

    def test_label_printed_endpoint_updates_order_status(self):
        order = Order.objects.create(
            customer_name='Label Customer',
            total_amount=Decimal('10.00'),
            created_by=self.user,
        )

        response = self.client.post(f'/api/v1/orders/{order.id}/label-printed/', {})

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.STATUS_LABEL_PRINTED)

    def test_label_printed_endpoint_marks_items_lable_printed(self):
        order = Order.objects.create(
            customer_name='Label Customer',
            total_amount=Decimal('10.00'),
            created_by=self.user,
        )
        item = OrderItem.objects.create(
            order=order,
            sku='SKU-001',
            product_name='Test Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.post(f'/api/v1/orders/{order.id}/label-printed/', {})

        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertTrue(item.lable_printed)
        self.assertTrue(response.data['order']['items'][0]['lable_printed'])

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Parcel',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=100,
    )
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_creates_remote_order_and_marks_shipped(self, mock_post):
        royal_mail_response = {
            'items': [
                {
                    'orderIdentifier': 'RM-ORDER-1',
                    'trackingNumber': 'RMTRACK123',
                }
            ]
        }
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = royal_mail_response
        mock_post.return_value = mock_response

        order = Order.objects.create(
            customer_name='Royal Mail Customer',
            customer_email='rm@example.com',
            customer_phone='07123456789',
            shipping_address_line1='1 Test Street',
            shipping_city='London',
            shipping_postal_code='SW1A 1AA',
            shipping_country='UK',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_COMPLETED,
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SKU-001',
            product_name='Royal Mail Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {
                'weight_in_grams': 250,
                'package_format_identifier': 'Parcel',
                'service_code': 'TPLN',
                'notes': 'Booked from API test',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.STATUS_SHIPPED)
        self.assertEqual(order.tracking_number, 'RMTRACK123')
        self.assertEqual(order.carrier, 'Royal Mail')
        self.assertEqual(order.shipping_method, 'TPLN')
        self.assertIn('RM-ORDER-1', order.internal_notes)
        self.assertIn('Booked from API test', order.internal_notes)

        request_payload = mock_post.call_args.kwargs['json']
        request_headers = mock_post.call_args.kwargs['headers']
        self.assertEqual(request_headers['Authorization'], 'test-api-key')
        self.assertEqual(request_payload['items'][0]['orderReference'], order.order_number)
        self.assertEqual(request_payload['items'][0]['billing']['address']['city'], 'London')
        self.assertEqual(request_payload['items'][0]['billing']['address']['postcode'], 'SW1A 1AA')
        self.assertEqual(request_payload['items'][0]['packages'][0]['weightInGrams'], 250)
        self.assertEqual(request_payload['items'][0]['packages'][0]['contents'][0]['SKU'], 'SKU-001')

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Letter',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=50,
    )
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_does_not_ship_when_royal_mail_returns_failed_orders(self, mock_post):
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            'successCount': 0,
            'errorsCount': 1,
            'createdOrders': [],
            'failedOrders': [
                {
                    'order': {'orderReference': 'ORD-FAILED'},
                    'errors': [{'errorMessage': 'Billing address postcode is required'}],
                }
            ],
        }
        mock_post.return_value = mock_response

        order = Order.objects.create(
            customer_name='Royal Mail Failed Customer',
            customer_email='failed@example.com',
            shipping_address_line1='1 Test Street',
            shipping_city='London',
            shipping_postal_code='SW1A 1AA',
            shipping_country='UK',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_COMPLETED,
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SKU-FAILED',
            product_name='Royal Mail Failed Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {
                'weight_in_grams': 50,
                'package_format_identifier': 'Letter',
                'service_code': 'STL2',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data['error'], 'Royal Mail did not create the shipment')
        self.assertEqual(response.data['royal_mail_response']['successCount'], 0)
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.STATUS_COMPLETED)
        self.assertIsNone(order.tracking_number)

    @override_settings(
        ROYAL_MAIL_API_KEY='',
        ROYAL_MAIL_AUTH_URL='https://auth.parcel.royalmail.com',
        ROYAL_MAIL_USERNAME='info@civani.co.uk',
        ROYAL_MAIL_PASSWORD='available-but-not-api-key',
    )
    def test_book_royal_mail_shipping_requires_api_key(self):
        order = Order.objects.create(
            customer_name='Royal Mail Customer',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_COMPLETED,
            created_by=self.user,
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {'weight_in_grams': 250},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('ROYAL_MAIL_API_KEY', response.data['error'])
        self.assertEqual(response.data['auth_url'], 'https://auth.parcel.royalmail.com')
        self.assertEqual(response.data['username'], 'info@civani.co.uk')
        self.assertIn('ROYAL_MAIL_API_KEY', response.data['message'])

    @override_settings(
        ROYAL_MAIL_API_KEY='',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Parcel',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=100,
    )
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_requires_api_key_even_if_oauth_token_exists(self, mock_post):
        RoyalMailOAuthToken.objects.create(
            access_token='oauth-access-token',
            token_type='Bearer',
            expires_at=timezone.now() + timedelta(hours=1),
            is_active=True,
        )

        order = Order.objects.create(
            customer_name='Royal Mail OAuth Customer',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_COMPLETED,
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SKU-OAUTH',
            product_name='Royal Mail OAuth Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {'weight_in_grams': 250},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('ROYAL_MAIL_API_KEY', response.data['error'])
        mock_post.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.STATUS_COMPLETED)

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_AUTH_URL='https://auth.parcel.royalmail.com',
        ROYAL_MAIL_USERNAME='info@civani.co.uk',
        ROYAL_MAIL_PASSWORD='test-password',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Parcel',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=100,
    )
    def test_royal_mail_config_does_not_expose_api_key(self):
        response = self.client.get('/api/v1/orders/royal-mail/config/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['configured'])
        self.assertTrue(response.data['booking_enabled'])
        self.assertTrue(response.data['api_key_present'])
        self.assertTrue(response.data['login_credentials_present'])
        self.assertEqual(response.data['username'], 'info@civani.co.uk')
        self.assertNotIn('test-api-key', str(response.data))
        self.assertNotIn('test-password', str(response.data))

    @override_settings(
        ROYAL_MAIL_API_KEY='',
        ROYAL_MAIL_CLIENT_ID='client-id',
        ROYAL_MAIL_CLIENT_SECRET='client-secret',
        ROYAL_MAIL_OAUTH_CALLBACK_URL='https://www.wims.cloud/auth/royalmail/callback',
        ROYAL_MAIL_OAUTH_AUTHORIZATION_URL='https://auth.parcel.royalmail.com/oauth2/authorize',
        ROYAL_MAIL_OAUTH_TOKEN_URL='https://auth.parcel.royalmail.com/oauth2/token',
        ROYAL_MAIL_OAUTH_SCOPE='orders',
    )
    def test_royal_mail_oauth_start_returns_authorization_url_without_secret(self):
        response = self.client.get('/api/v1/orders/royal-mail/oauth/start/?state=test-state')

        self.assertEqual(response.status_code, 200)
        self.assertIn('authorization_url', response.data)
        self.assertIn('client_id=client-id', response.data['authorization_url'])
        self.assertIn('redirect_uri=https%3A%2F%2Fwww.wims.cloud%2Fauth%2Froyalmail%2Fcallback', response.data['authorization_url'])
        self.assertIn('state=test-state', response.data['authorization_url'])
        self.assertNotIn('client-secret', str(response.data))

    @override_settings(
        ROYAL_MAIL_OAUTH_AUTHORIZATION_URL='',
        ROYAL_MAIL_OAUTH_TOKEN_URL='',
    )
    def test_royal_mail_oauth_start_explains_api_key_option_when_disabled(self):
        response = self.client.get('/api/v1/orders/royal-mail/oauth/start/')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['required_setting'], 'ROYAL_MAIL_API_KEY')
        self.assertIn('Click & Drop API key', response.data['message'])

    def test_royal_mail_oauth_callback_requires_code(self):
        response = self.client.get('/auth/royalmail/callback')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['connected'])

    @override_settings(
        ROYAL_MAIL_CLIENT_ID='client-id',
        ROYAL_MAIL_CLIENT_SECRET='client-secret',
        ROYAL_MAIL_OAUTH_CALLBACK_URL='https://www.wims.cloud/auth/royalmail/callback',
        ROYAL_MAIL_OAUTH_AUTHORIZATION_URL='https://auth.parcel.royalmail.com/oauth2/authorize',
        ROYAL_MAIL_OAUTH_TOKEN_URL='https://auth.parcel.royalmail.com/oauth2/token',
        ROYAL_MAIL_OAUTH_SCOPE='orders',
    )
    @patch('orders.services.royal_mail.requests.post')
    def test_royal_mail_oauth_callback_exchanges_code_and_masks_token(self, mock_post):
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            'access_token': 'new-access-token',
            'refresh_token': 'new-refresh-token',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': 'orders',
        }
        mock_post.return_value = mock_response

        response = self.client.get('/auth/royalmail/callback?code=abc123&state=connect')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['connected'])
        self.assertEqual(RoyalMailOAuthToken.objects.filter(is_active=True).count(), 1)
        self.assertNotIn('new-access-token', str(response.data))
        self.assertNotIn('new-refresh-token', str(response.data))

    @override_settings(ROYAL_MAIL_API_KEY='')
    def test_royal_mail_config_does_not_enable_booking_from_oauth_token(self):
        RoyalMailOAuthToken.objects.create(
            access_token='active-token',
            token_type='Bearer',
            expires_at=timezone.now() + timedelta(hours=1),
            is_active=True,
        )

        response = self.client.get('/api/v1/orders/royal-mail/config/')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['configured'])
        self.assertFalse(response.data['booking_enabled'])
        self.assertTrue(response.data['oauth_connected'])
        self.assertFalse(response.data['oauth_used_for_booking'])
        self.assertEqual(response.data['auth_mode'], 'not_configured')
        self.assertNotIn('active-token', str(response.data))

    def test_item_lable_printed_endpoint_updates_only_selected_item(self):
        order = Order.objects.create(
            customer_name='Item Label Customer',
            total_amount=Decimal('20.00'),
            created_by=self.user,
        )
        first_item = OrderItem.objects.create(
            order=order,
            sku='SKU-001',
            product_name='First Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )
        second_item = OrderItem.objects.create(
            order=order,
            sku='SKU-002',
            product_name='Second Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.patch(
            f'/api/v1/orders/{order.id}/items/{first_item.id}/lable-printed/',
            {'lable_printed': True},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        first_item.refresh_from_db()
        second_item.refresh_from_db()
        self.assertTrue(first_item.lable_printed)
        self.assertFalse(second_item.lable_printed)
        self.assertTrue(response.data['item']['lable_printed'])

    def test_item_lable_printed_endpoint_updates_multiple_items(self):
        order = Order.objects.create(
            customer_name='Bulk Item Label Customer',
            total_amount=Decimal('30.00'),
            created_by=self.user,
        )
        first_item = OrderItem.objects.create(
            order=order,
            sku='SKU-001',
            product_name='First Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )
        second_item = OrderItem.objects.create(
            order=order,
            sku='SKU-002',
            product_name='Second Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )
        third_item = OrderItem.objects.create(
            order=order,
            sku='SKU-003',
            product_name='Third Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.patch(
            f'/api/v1/orders/{order.id}/items/{first_item.id},{second_item.id}/lable-printed/',
            {'lable_printed': True},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        first_item.refresh_from_db()
        second_item.refresh_from_db()
        third_item.refresh_from_db()
        self.assertTrue(first_item.lable_printed)
        self.assertTrue(second_item.lable_printed)
        self.assertFalse(third_item.lable_printed)
        self.assertEqual(response.data['updated_count'], 2)
        self.assertEqual(len(response.data['items']), 2)

    def test_item_lable_printed_endpoint_accepts_body_item_ids(self):
        order = Order.objects.create(
            customer_name='Body Item Label Customer',
            total_amount=Decimal('20.00'),
            created_by=self.user,
        )
        first_item = OrderItem.objects.create(
            order=order,
            sku='SKU-001',
            product_name='First Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )
        second_item = OrderItem.objects.create(
            order=order,
            sku='SKU-002',
            product_name='Second Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.patch(
            f'/api/v1/orders/{order.id}/items/{first_item.id}/lable-printed/',
            {'order_item_ids': [first_item.id, second_item.id], 'lable_printed': True},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        first_item.refresh_from_db()
        second_item.refresh_from_db()
        self.assertTrue(first_item.lable_printed)
        self.assertTrue(second_item.lable_printed)
        self.assertEqual(response.data['updated_count'], 2)

    def test_bulk_item_lable_printed_endpoint_uses_body_item_ids(self):
        order = Order.objects.create(
            customer_name='Clean Bulk Item Label Customer',
            total_amount=Decimal('20.00'),
            created_by=self.user,
        )
        first_item = OrderItem.objects.create(
            order=order,
            sku='SKU-001',
            product_name='First Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )
        second_item = OrderItem.objects.create(
            order=order,
            sku='SKU-002',
            product_name='Second Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.patch(
            '/api/v1/orders/items/lable-printed/',
            {'order_item_ids': [first_item.id, second_item.id], 'lable_printed': True},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        first_item.refresh_from_db()
        second_item.refresh_from_db()
        self.assertTrue(first_item.lable_printed)
        self.assertTrue(second_item.lable_printed)
        self.assertEqual(response.data['updated_count'], 2)
        self.assertEqual(response.data['order_ids'], [order.id])

    def test_bulk_item_lable_printed_endpoint_rejects_missing_item_ids(self):
        response = self.client.patch(
            '/api/v1/orders/items/lable-printed/',
            {'order_item_ids': [999999], 'lable_printed': True},
            format='json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['missing_order_item_ids'], [999999])

    def test_item_lable_printed_endpoint_rejects_item_from_other_order(self):
        order = Order.objects.create(
            customer_name='Correct Order',
            total_amount=Decimal('10.00'),
            created_by=self.user,
        )
        other_order = Order.objects.create(
            customer_name='Other Order',
            total_amount=Decimal('10.00'),
            created_by=self.user,
        )
        other_item = OrderItem.objects.create(
            order=other_order,
            sku='SKU-OTHER',
            product_name='Other Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.patch(
            f'/api/v1/orders/{order.id}/items/{other_item.id}/lable-printed/',
            {'lable_printed': True},
            format='json',
        )

        self.assertEqual(response.status_code, 404)
        other_item.refresh_from_db()
        self.assertFalse(other_item.lable_printed)

    def test_item_status_updates_parent_order_progress_status(self):
        order = Order.objects.create(
            customer_name='Progress Customer',
            total_amount=Decimal('25.00'),
            created_by=self.user,
            order_status=Order.STATUS_LABEL_PRINTED,
        )
        first_item = OrderItem.objects.create(
            order=order,
            sku='SKU-001',
            product_name='First Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )
        second_item = OrderItem.objects.create(
            order=order,
            sku='SKU-002',
            product_name='Second Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('15.00'),
        )

        first_response = self.client.patch(
            f'/api/v1/order-items/{first_item.id}/update-status/',
            {'processing_status': OrderItem.ITEM_STATUS_PICKED},
            format='json',
        )
        self.assertEqual(first_response.status_code, 200)
        order.refresh_from_db()
        first_item.refresh_from_db()
        self.assertEqual(first_item.quantity_processed, first_item.quantity)
        self.assertEqual(order.order_status, Order.STATUS_IN_PROGRESS)

        second_response = self.client.patch(
            f'/api/v1/order-items/{second_item.id}/update-status/',
            {'processing_status': OrderItem.ITEM_STATUS_PICKED},
            format='json',
        )
        self.assertEqual(second_response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.STATUS_COMPLETED)


class DashboardStatsAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dashboard_user', password='test123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.color = Color.objects.create(color_code='BLK', color_name='Black')
        self.product = Product.objects.create(
            vs_parent_id=900,
            vs_child_id=900,
            parent_reference='DASH SKU',
            child_reference='DASH SKU',
            parent_product_title='Dashboard Product',
            child_product_title='Dashboard Product',
        )

    def test_dashboard_stats_returns_order_and_stock_counts(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        new_order = Order.objects.create(
            customer_name='New Customer',
            order_status=Order.STATUS_NEW,
            total_amount=Decimal('1.00'),
        )
        progress_order = Order.objects.create(
            customer_name='Progress Customer',
            order_status=Order.STATUS_IN_PROGRESS,
            total_amount=Decimal('1.00'),
        )
        completed_order = Order.objects.create(
            customer_name='Completed Customer',
            order_status=Order.STATUS_COMPLETED,
            total_amount=Decimal('1.00'),
        )
        Order.objects.filter(pk=new_order.pk).update(order_date=timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time())
        ))
        Order.objects.filter(pk=progress_order.pk).update(order_date=timezone.make_aware(
            timezone.datetime.combine(yesterday, timezone.datetime.min.time())
        ))
        Order.objects.filter(pk=completed_order.pk).update(order_date=timezone.make_aware(
            timezone.datetime.combine(two_days_ago, timezone.datetime.min.time())
        ))

        StockItem.objects.create(
            sku='DASH IN',
            product_type='DASH',
            product=self.product,
            color=self.color,
            available_stock_in_mtr=20,
            minimum_stock_level=5,
            is_active=True,
        )
        StockItem.objects.create(
            sku='DASH LOW',
            product_type='DASH',
            product=self.product,
            color=self.color,
            available_stock_in_mtr=3,
            minimum_stock_level=5,
            is_active=True,
        )
        StockItem.objects.create(
            sku='DASH OUT',
            product_type='DASH',
            product=self.product,
            color=self.color,
            available_stock_in_mtr=0,
            minimum_stock_level=5,
            is_active=True,
        )

        response = self.client.get('/api/v1/dashboard/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['orders']['total'], 3)
        self.assertEqual(response.data['orders']['in_progress'], 1)
        self.assertEqual(response.data['orders']['completed'], 1)
        self.assertEqual(response.data['stock']['in_stock'], 1)
        self.assertEqual(response.data['stock']['low_stock'], 1)
        self.assertEqual(response.data['stock']['out_of_stock'], 1)

    def test_dashboard_stats_supports_today_yesterday_and_date_range(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)

        today_order = Order.objects.create(
            customer_name='Today Customer',
            order_status=Order.STATUS_COMPLETED,
            total_amount=Decimal('1.00'),
        )
        yesterday_order = Order.objects.create(
            customer_name='Yesterday Customer',
            order_status=Order.STATUS_IN_PROGRESS,
            total_amount=Decimal('1.00'),
        )
        Order.objects.filter(pk=today_order.pk).update(order_date=timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time())
        ))
        Order.objects.filter(pk=yesterday_order.pk).update(order_date=timezone.make_aware(
            timezone.datetime.combine(yesterday, timezone.datetime.min.time())
        ))

        today_response = self.client.get('/api/v1/dashboard/stats/?period=today')
        yesterday_response = self.client.get('/api/v1/dashboard/stats/?period=yesterday')
        range_response = self.client.get(
            f'/api/v1/dashboard/stats/?date_from={yesterday.isoformat()}&date_to={yesterday.isoformat()}'
        )

        self.assertEqual(today_response.status_code, 200)
        self.assertEqual(today_response.data['orders']['total'], 1)
        self.assertEqual(today_response.data['orders']['completed'], 1)
        self.assertEqual(yesterday_response.status_code, 200)
        self.assertEqual(yesterday_response.data['orders']['total'], 1)
        self.assertEqual(yesterday_response.data['orders']['in_progress'], 1)
        self.assertEqual(range_response.status_code, 200)
        self.assertEqual(range_response.data['orders']['total'], 1)
        self.assertEqual(range_response.data['filters']['date_from'], yesterday.isoformat())


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
from zoneinfo import ZoneInfo
from rest_framework.test import APIClient
from .models import Order, OrderItem, OrderBatch, RoyalMailOAuthToken
from .services.xml_parser import XMLOrderParser
from colors.models import Color
from products.models import Product, ProductExtendedData
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
            '<web_order><order><order_reference>WEB100003</order_reference></order></web_order>'
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
                'TIA_GAP_RECOVERY_ATTEMPTS': '0',
            }, clear=False):
                result = import_remote_tiaknight_orders(user=None)

            self.assertEqual(mock_fetch.call_args.kwargs['auto_update'], 'true')
            self.assertEqual(result['received_order_refs_count'], 2)
            self.assertEqual(result['received_order_refs'], ['WEB100001', 'WEB100003'])
            self.assertEqual(result['tiaknight_request_id'], 'REQ-1')
            self.assertEqual(result['missing_sequence_order_refs'], ['WEB100002'])

            with open(audit_path, encoding='utf-8') as audit_file:
                audit_line = audit_file.read()
            self.assertIn('request_id=REQ-1', audit_line)
            self.assertIn('auto_update=true', audit_line)
            self.assertIn('orders_received=2', audit_line)
            self.assertIn('refs=WEB100001,WEB100003', audit_line)
            self.assertIn('missing_sequence_refs=WEB100002', audit_line)

    @patch('orders.services.remote_tiaknight_import.XMLOrderParser.parse_and_create_orders')
    @patch('scripts.soap_client.fetch_soap_response')
    def test_import_retries_and_merges_when_sequence_gap_is_recovered(self, mock_fetch, mock_parse):
        from orders.services.remote_tiaknight_import import import_remote_tiaknight_orders

        first_orders_xml = (
            '<web_orders>'
            '<web_order><order><order_reference>WEB100001</order_reference></order></web_order>'
            '<web_order><order><order_reference>WEB100003</order_reference></order></web_order>'
            '</web_orders>'
        )
        second_orders_xml = (
            '<web_orders>'
            '<web_order><order><order_reference>WEB100001</order_reference></order></web_order>'
            '<web_order><order><order_reference>WEB100002</order_reference></order></web_order>'
            '<web_order><order><order_reference>WEB100003</order_reference></order></web_order>'
            '</web_orders>'
        )
        first_response = (
            '<Envelope><Body>'
            '<item><key>RequestID</key><value>REQ-1</value></item>'
            f'<item><key>Result</key><value>{escape(first_orders_xml)}</value></item>'
            '</Body></Envelope>'
        ).encode('utf-8')
        second_response = (
            '<Envelope><Body>'
            '<item><key>RequestID</key><value>REQ-2</value></item>'
            f'<item><key>Result</key><value>{escape(second_orders_xml)}</value></item>'
            '</Body></Envelope>'
        ).encode('utf-8')
        mock_fetch.side_effect = [(first_response, 200), (second_response, 200)]
        mock_parse.return_value = {
            'created_count': 3,
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
                'TIA_AUTO_UPDATE': 'false',
                'TIA_FILE_TYPE': 'xml',
                'TIA_AUDIT_LOG_PATH': audit_path,
                'TIA_SAVE_RAW_PAYLOAD': 'false',
                'TIA_GAP_RECOVERY_ATTEMPTS': '2',
                'TIA_GAP_RECOVERY_DELAY_SECONDS': '0',
            }, clear=False):
                result = import_remote_tiaknight_orders(user=None)

            self.assertEqual(mock_fetch.call_count, 2)
            self.assertEqual(result['missing_sequence_order_refs'], [])
            self.assertEqual(result['tiaknight_gap_recovery_attempts'], 1)
            self.assertEqual(set(result['received_order_refs']), {'WEB100001', 'WEB100002', 'WEB100003'})

            imported_xml = mock_parse.call_args.args[0].getvalue().decode('utf-8')
            self.assertEqual(imported_xml.count('WEB100001'), 1)
            self.assertEqual(imported_xml.count('WEB100002'), 1)
            self.assertEqual(imported_xml.count('WEB100003'), 1)

            with open(audit_path, encoding='utf-8') as audit_file:
                audit_line = audit_file.read()
            self.assertIn('orders_received=3', audit_line)
            self.assertIn('missing_sequence_refs=-', audit_line)
            self.assertIn('recovery_attempts=1', audit_line)

    def test_missing_sequence_detection_uses_previous_audit_max(self):
        from orders.services.remote_tiaknight_import import detect_missing_sequence_refs

        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = os.path.join(tmpdir, 'tiaknight_refs.log')
            with open(audit_path, 'w', encoding='utf-8') as audit_file:
                audit_file.write(
                    '[2026-07-08 09:00:06 UTC] orders_received=1 refs=WEB236577 '
                    'missing_sequence_refs=-\n'
                )

            missing = detect_missing_sequence_refs(
                ['WEB236582', 'WEB236584', 'WEB236585', 'WEB236586', 'WEB236587'],
                audit_path,
            )

        self.assertEqual(
            missing,
            ['WEB236578', 'WEB236579', 'WEB236580', 'WEB236581', 'WEB236583'],
        )


class OrderWithItemsAPITest(TestCase):
    """Test order list endpoint with nested order items"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='api_user',
            password='test123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _mock_royal_mail_label_response(self, mock_get, content=b'%PDF-1.4 test label pdf'):
        mock_response = Mock(status_code=200)
        mock_response.headers = {'Content-Type': 'application/pdf'}
        mock_response.content = content
        mock_get.return_value = mock_response

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

    def test_order_type_filter_returns_retail_and_wholesale_orders(self):
        retail_order = Order.objects.create(
            customer_name='Retail Customer',
            total_amount=Decimal('10.00'),
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=retail_order,
            sku='RET-001',
            product_name='Retail Product',
            quantity=19,
            quantity_ordered=19,
            unit_price=Decimal('1.00'),
        )
        wholesale_order = Order.objects.create(
            customer_name='Wholesale Customer',
            total_amount=Decimal('25.00'),
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=wholesale_order,
            sku='WHO-001',
            product_name='Wholesale Product',
            quantity=20,
            quantity_ordered=20,
            unit_price=Decimal('1.00'),
        )

        retail_response = self.client.get('/api/v1/orders/?order_type=retail')
        wholesale_response = self.client.get('/api/v1/orders/?order_type=wholesale')

        self.assertEqual(retail_response.status_code, 200)
        self.assertEqual(wholesale_response.status_code, 200)
        retail_ids = {row['id'] for row in retail_response.data['results']}
        wholesale_ids = {row['id'] for row in wholesale_response.data['results']}
        self.assertIn(retail_order.id, retail_ids)
        self.assertNotIn(wholesale_order.id, retail_ids)
        self.assertIn(wholesale_order.id, wholesale_ids)
        self.assertNotIn(retail_order.id, wholesale_ids)
        self.assertEqual(retail_response.data['results'][0]['order_type'], 'retail')

    def test_web_platform_filter_includes_existing_xml_source_orders(self):
        xml_order = Order.objects.create(
            customer_name='XML Customer',
            total_amount=Decimal('10.00'),
            order_source=Order.SOURCE_XML,
            created_by=self.user,
        )
        website_order = Order.objects.create(
            customer_name='Website Customer',
            total_amount=Decimal('10.00'),
            order_source=Order.SOURCE_WEBSITE,
            created_by=self.user,
        )
        manual_order = Order.objects.create(
            customer_name='Manual Customer',
            total_amount=Decimal('10.00'),
            order_source=Order.SOURCE_MANUAL,
            created_by=self.user,
        )

        response = self.client.get('/api/v1/orders/?platform=web')

        self.assertEqual(response.status_code, 200)
        order_rows = {row['id']: row for row in response.data['results']}
        self.assertIn(xml_order.id, order_rows)
        self.assertIn(website_order.id, order_rows)
        self.assertNotIn(manual_order.id, order_rows)
        self.assertEqual(order_rows[xml_order.id]['source_display'], 'WEB')
        self.assertEqual(order_rows[website_order.id]['source_display'], 'WEB')

    def test_order_batch_create_detail_and_label_printed_flow(self):
        first_order = Order.objects.create(
            customer_name='Batch Customer 1',
            total_amount=Decimal('10.00'),
            order_source=Order.SOURCE_WEBSITE,
            courier_service_code='STD',
            courier_service_name='Standard Delivery',
            created_by=self.user,
        )
        first_item = OrderItem.objects.create(
            order=first_order,
            sku='BATCH-001',
            product_name='Batch Product 1',
            quantity=2,
            quantity_ordered=2,
            unit_price=Decimal('5.00'),
        )
        second_order = Order.objects.create(
            customer_name='Batch Customer 2',
            total_amount=Decimal('20.00'),
            order_source=Order.SOURCE_WEBSITE,
            courier_service_code='STD',
            courier_service_name='Standard Delivery',
            created_by=self.user,
        )
        second_item = OrderItem.objects.create(
            order=second_order,
            sku='BATCH-002',
            product_name='Batch Product 2',
            quantity=4,
            quantity_ordered=4,
            unit_price=Decimal('5.00'),
        )

        response = self.client.post(
            '/api/v1/order-batches/',
            {
                'batch_number': 1,
                'batch_date': '2026-08-11',
                'order_ids': [first_order.id, second_order.id],
                'filters_snapshot': {
                    'platform': 'web',
                    'courier_service_code': 'STD',
                    'order_type': 'retail',
                },
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['batch_name'], '11082026-B1')
        self.assertEqual(response.data['orders_count'], 2)
        self.assertEqual(len(response.data['orders']), 2)
        self.assertEqual(len(response.data['labels']), 2)
        self.assertEqual(response.data['details']['retail_orders_count'], 2)
        self.assertEqual(response.data['details']['wholesale_orders_count'], 0)

        batch_id = response.data['id']
        detail_response = self.client.get(f'/api/v1/order-batches/{batch_id}/')
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn('orders', detail_response.data)
        self.assertIn('labels', detail_response.data)
        self.assertIn('details', detail_response.data)

        orders_response = self.client.get('/api/v1/orders/')
        with_items_response = self.client.get('/api/v1/orders/with-items/?page=1')
        order_detail_response = self.client.get(f'/api/v1/orders/{first_order.id}/')

        self.assertEqual(orders_response.status_code, 200)
        self.assertEqual(with_items_response.status_code, 200)
        self.assertEqual(order_detail_response.status_code, 200)
        order_row = next(row for row in orders_response.data['results'] if row['id'] == first_order.id)
        with_items_row = next(row for row in with_items_response.data['results'] if row['id'] == first_order.id)
        self.assertTrue(order_row['batch_assigned'])
        self.assertEqual(order_row['batch_id'], batch_id)
        self.assertEqual(order_row['batch_name'], '11082026-B1')
        self.assertTrue(with_items_row['batch_assigned'])
        self.assertEqual(with_items_row['batch_id'], batch_id)
        self.assertEqual(with_items_row['batch_name'], '11082026-B1')
        self.assertTrue(order_detail_response.data['batch_assigned'])
        self.assertEqual(order_detail_response.data['batch_id'], batch_id)
        self.assertEqual(order_detail_response.data['batch_name'], '11082026-B1')

        printed_response = self.client.patch(
            f'/api/v1/order-batches/{batch_id}/labels/printed/',
            {'lable_printed': True, 'order_item_ids': [first_item.id, second_item.id]},
            format='json',
        )

        self.assertEqual(printed_response.status_code, 200)
        self.assertEqual(printed_response.data['updated_count'], 2)
        first_item.refresh_from_db()
        second_item.refresh_from_db()
        self.assertTrue(first_item.lable_printed)
        self.assertTrue(second_item.lable_printed)

    def test_order_batch_rejects_order_already_in_active_batch(self):
        first_order = Order.objects.create(
            customer_name='Duplicate Batch Customer',
            total_amount=Decimal('10.00'),
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=first_order,
            sku='DUP-001',
            product_name='Duplicate Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        first_response = self.client.post(
            '/api/v1/order-batches/',
            {
                'batch_number': 1,
                'batch_date': '2026-08-11',
                'order_ids': [first_order.id],
            },
            format='json',
        )
        second_response = self.client.post(
            '/api/v1/order-batches/',
            {
                'batch_number': 2,
                'batch_date': '2026-08-11',
                'order_ids': [first_order.id],
            },
            format='json',
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(OrderBatch.objects.count(), 1)

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
            weight_kg=Decimal('0.250'),
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
            quantity=3,
            quantity_ordered=3,
            unit_price=Decimal('10.00'),
        )

        response = self.client.get('/api/v1/order-items/')
        detail_response = self.client.get(f'/api/v1/orders/{order.id}/')
        list_response = self.client.get('/api/v1/orders/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(list_response.status_code, 200)
        result = next(row for row in response.data['results'] if row['id'] == item.id)
        self.assertEqual(result['available_stock_in_mtr'], 42)
        self.assertEqual(result['unit_weight_gm'], 250)
        self.assertEqual(result['total_weight_gm'], 750)
        self.assertEqual(detail_response.data['items'][0]['unit_weight_gm'], 250)
        self.assertEqual(detail_response.data['items'][0]['total_weight_gm'], 750)
        self.assertEqual(detail_response.data['total_weight_gm'], 750)
        order_row = next(row for row in list_response.data['results'] if row['id'] == order.id)
        self.assertEqual(order_row['total_weight_gm'], 750)

    def test_order_detail_returns_child_product_url_from_stock_product_extended_data(self):
        color = Color.objects.create(
            color_code='URL',
            color_name='URL Color',
        )
        product = Product.objects.create(
            vs_parent_id=10102,
            vs_child_id=10102,
            parent_reference='URL SKU',
            child_reference='URL SKU',
            parent_product_title='URL Product',
            child_product_title='URL Product',
        )
        ProductExtendedData.objects.create(
            product=product,
            source_file_name='backup.csv',
            row_number=2,
            row_hash='order-url-row',
            import_batch_id='order-url-batch',
            child_product_url='https://example.com/products/url-sku',
            weight_in_kgs='0.125',
        )
        stock_item = StockItem.objects.create(
            sku='URL SKU',
            product_type='URL',
            product=product,
            color=color,
            available_stock_in_mtr=12,
        )
        order = Order.objects.create(
            customer_name='URL Customer',
            customer_email='url@example.com',
            total_amount=Decimal('10.00'),
            created_by=self.user,
        )
        item = OrderItem.objects.create(
            order=order,
            stock_item=stock_item,
            sku='URL SKU',
            product_name='URL Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        detail_response = self.client.get(f'/api/v1/orders/{order.id}/')
        item_response = self.client.get('/api/v1/order-items/')

        self.assertEqual(detail_response.status_code, 200)
        order_item = detail_response.data['items'][0]
        self.assertEqual(order_item['child_product_url'], 'https://example.com/products/url-sku')
        self.assertEqual(order_item['unit_weight_gm'], 125)
        self.assertEqual(order_item['total_weight_gm'], 125)
        self.assertEqual(order_item['stock_detail']['child_product_url'], 'https://example.com/products/url-sku')
        self.assertEqual(order_item['stock_detail']['product']['child_product_url'], 'https://example.com/products/url-sku')

        item_row = next(row for row in item_response.data['results'] if row['id'] == item.id)
        self.assertEqual(item_row['child_product_url'], 'https://example.com/products/url-sku')
        self.assertEqual(item_row['unit_weight_gm'], 125)

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
        self.assertEqual(order.order_source, Order.SOURCE_WEBSITE)
        self.assertEqual(order.courier_service_name, 'Next Day By 12pm (next working day if ordered before 1pm)')
        self.assertEqual(order.courier_service_code, 'NEXT DAY 12')
        self.assertEqual(order.shipping_method, order.courier_service_name)
        self.assertEqual(order.carrier, order.courier_service_name)

        detail_response = self.client.get(f'/api/v1/orders/{order.id}/')
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data['courier_service_code'], 'NEXT DAY 12')

    def test_xml_import_keeps_tiaknight_local_order_time_and_raw_value(self):
        xml_data = b'''
        <web_orders>
          <web_order>
            <order>
              <order_reference>WEB-TIME-001</order_reference>
              <order_state>Payment Received</order_state>
              <order_date>2026-07-06 12:43:42</order_date>
              <grand_total_inc>12.50</grand_total_inc>
            </order>
            <customer>
              <billing_firstname>Time</billing_firstname>
              <billing_lastname>Customer</billing_lastname>
              <billing_email>time@example.com</billing_email>
            </customer>
            <payment>
              <payment_type>Card</payment_type>
            </payment>
            <products>
              <product>
                <product_reference>SKU-TIME</product_reference>
                <title>Time Product</title>
                <quantity>1</quantity>
                <price_inc>12.50</price_inc>
              </product>
            </products>
          </web_order>
        </web_orders>
        '''

        XMLOrderParser().parse_and_create_orders(io.BytesIO(xml_data), user=self.user)

        order = Order.objects.get(external_order_id='WEB-TIME-001')
        tiaknight_local = timezone.localtime(order.order_date, ZoneInfo('Europe/London'))
        self.assertEqual(tiaknight_local.strftime('%Y-%m-%d %H:%M:%S'), '2026-07-06 12:43:42')
        self.assertEqual(order.tiaknight_order_date_raw, '2026-07-06 12:43:42')
        self.assertIsNotNone(order.tiaknight_fetched_at)

    def test_xml_import_extracts_sample_personalization_from_product_title(self):
        xml_data = b'''
        <web_orders>
          <web_order>
            <order>
              <order_reference>WEB-SAMPLE-001</order_reference>
              <order_state>Payment Received</order_state>
              <order_date>2026-07-06 12:43:42</order_date>
              <grand_total_inc>3.50</grand_total_inc>
            </order>
            <customer>
              <billing_firstname>Sample</billing_firstname>
              <billing_lastname>Customer</billing_lastname>
              <billing_email>sample@example.com</billing_email>
            </customer>
            <payment>
              <payment_type>Card</payment_type>
            </payment>
            <products>
              <product>
                <product_reference>SQ1011 GLD</product_reference>
                <title>P4P Polar Fleece Material (SQ1011 GLD) (Design: Gold Animal Sample Request)</title>
                <quantity>1</quantity>
                <price_inc>3.50</price_inc>
              </product>
            </products>
          </web_order>
        </web_orders>
        '''

        XMLOrderParser().parse_and_create_orders(io.BytesIO(xml_data), user=self.user)

        item = OrderItem.objects.get(order__external_order_id='WEB-SAMPLE-001')
        self.assertTrue(item.is_sample)
        self.assertEqual(item.sample_name, 'Gold Animal Sample Request')
        self.assertIsNone(item.personalization)
        self.assertIsNone(item.summary)

        detail_response = self.client.get(f'/api/v1/orders/{item.order_id}/')
        self.assertEqual(detail_response.status_code, 200)
        response_item = detail_response.data['items'][0]
        self.assertTrue(response_item['is_sample'])
        self.assertEqual(response_item['sample_name'], 'Gold Animal Sample Request')
        self.assertIsNone(response_item['personalization'])

    def test_xml_import_saves_tiaknight_summary_and_personalization_fields(self):
        xml_data = b'''
        <web_orders>
          <web_order>
            <order>
              <order_reference>WEB-PERSONAL-001</order_reference>
              <order_state>Payment Received</order_state>
              <order_date>2026-07-06 12:43:42</order_date>
              <grand_total_inc>3.50</grand_total_inc>
            </order>
            <customer>
              <billing_firstname>Personal</billing_firstname>
              <billing_lastname>Customer</billing_lastname>
              <billing_email>personal@example.com</billing_email>
            </customer>
            <payment>
              <payment_type>Card</payment_type>
            </payment>
            <products>
              <product>
                <product_reference>SQ1011 GLD</product_reference>
                <title>P4P Polar Fleece Material (SQ1011 GLD) (Design: Gold Animal Sample Request)</title>
                <summary>Tiaknight Summary Text</summary>
                <personalisation>Tiaknight Personalisation Text</personalisation>
                <quantity>1</quantity>
                <price_inc>3.50</price_inc>
              </product>
            </products>
          </web_order>
        </web_orders>
        '''

        XMLOrderParser().parse_and_create_orders(io.BytesIO(xml_data), user=self.user)

        item = OrderItem.objects.get(order__external_order_id='WEB-PERSONAL-001')
        self.assertTrue(item.is_sample)
        self.assertEqual(item.sample_name, 'Gold Animal Sample Request')
        self.assertEqual(item.summary, 'Tiaknight Summary Text')
        self.assertEqual(item.personalization, 'Tiaknight Personalisation Text')

    def test_xml_reimport_updates_existing_item_summary_and_personalization_without_duplicates(self):
        order = Order.objects.create(
            customer_name='Existing Customer',
            external_order_id='WEB-EXISTING-PERSONAL',
            total_amount=Decimal('3.50'),
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SQ1011 GLD',
            product_name='Existing Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('3.50'),
        )
        xml_data = b'''
        <web_orders>
          <web_order>
            <order>
              <order_reference>WEB-EXISTING-PERSONAL</order_reference>
              <order_state>Payment Received</order_state>
              <order_date>2026-07-06 12:43:42</order_date>
              <grand_total_inc>3.50</grand_total_inc>
            </order>
            <customer>
              <billing_firstname>Existing</billing_firstname>
              <billing_lastname>Customer</billing_lastname>
              <billing_email>existing-personal@example.com</billing_email>
            </customer>
            <payment>
              <payment_type>Card</payment_type>
            </payment>
            <products>
              <product>
                <product_reference>SQ1011 GLD</product_reference>
                <title>P4P Polar Fleece Material (SQ1011 GLD)</title>
                <summary>Updated Tiaknight Summary</summary>
                <personalization>Updated Tiaknight Personalization</personalization>
                <quantity>1</quantity>
                <price_inc>3.50</price_inc>
              </product>
            </products>
          </web_order>
        </web_orders>
        '''

        result = XMLOrderParser().parse_and_create_orders(io.BytesIO(xml_data), user=self.user)

        self.assertEqual(result['created_count'], 0)
        self.assertEqual(order.items.count(), 1)
        item = order.items.get()
        self.assertEqual(item.summary, 'Updated Tiaknight Summary')
        self.assertEqual(item.personalization, 'Updated Tiaknight Personalization')

    def test_xml_reimport_updates_existing_order_payment_status_from_order_state(self):
        order = Order.objects.create(
            customer_name='Existing Payment Customer',
            external_order_id='WEB-EXISTING-PAYMENT',
            payment_status=Order.PAYMENT_UNPAID,
            total_amount=Decimal('3.50'),
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SQ1011 GLD',
            product_name='Existing Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('3.50'),
        )
        xml_data = b'''
        <web_orders>
          <web_order>
            <order>
              <order_reference>WEB-EXISTING-PAYMENT</order_reference>
              <order_state>Processing Order</order_state>
              <order_date>2026-07-06 12:43:42</order_date>
              <grand_total_inc>3.50</grand_total_inc>
            </order>
            <customer>
              <billing_firstname>Existing</billing_firstname>
              <billing_lastname>Payment</billing_lastname>
              <billing_email>existing-payment@example.com</billing_email>
            </customer>
            <payment>
              <payment_type>PayPal Express</payment_type>
              <transaction_reference>PAYMENT-123</transaction_reference>
            </payment>
            <products>
              <product>
                <product_reference>SQ1011 GLD</product_reference>
                <title>P4P Polar Fleece Material (SQ1011 GLD)</title>
                <quantity>1</quantity>
                <price_inc>3.50</price_inc>
              </product>
            </products>
          </web_order>
        </web_orders>
        '''

        result = XMLOrderParser().parse_and_create_orders(io.BytesIO(xml_data), user=self.user)

        self.assertEqual(result['created_count'], 0)
        self.assertEqual(Order.objects.filter(external_order_id='WEB-EXISTING-PAYMENT').count(), 1)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PAYMENT_PAID)
        self.assertEqual(order.payment_method, 'PayPal Express')
        self.assertEqual(order.payment_reference, 'PAYMENT-123')
        self.assertEqual(order.items.count(), 1)

    def test_xml_import_extracts_length_sample_items(self):
        xml_data = b'''
        <web_orders>
          <web_order>
            <order>
              <order_reference>WEB-SAMPLE-LENGTH-001</order_reference>
              <order_state>Payment Received</order_state>
              <order_date>2026-07-06 12:43:42</order_date>
              <grand_total_inc>0.50</grand_total_inc>
            </order>
            <customer>
              <billing_firstname>Length</billing_firstname>
              <billing_lastname>Sample</billing_lastname>
              <billing_email>length-sample@example.com</billing_email>
            </customer>
            <payment>
              <payment_type>Card</payment_type>
            </payment>
            <products>
              <product>
                <product_reference>SAMPLE-SQ209 RBL</product_reference>
                <title>Cotton Fine Rib 1x1 Elastane Stretch T-Shirt Fabric- SQ209 Colour: Royal Blue, Length: Sample (6 x 6")</title>
                <quantity>1</quantity>
                <price_inc>0.50</price_inc>
              </product>
            </products>
          </web_order>
        </web_orders>
        '''

        XMLOrderParser().parse_and_create_orders(io.BytesIO(xml_data), user=self.user)

        item = OrderItem.objects.get(order__external_order_id='WEB-SAMPLE-LENGTH-001')
        self.assertTrue(item.is_sample)
        self.assertEqual(item.sample_name, 'Sample (6 x 6")')
        self.assertIsNone(item.personalization)
        self.assertIsNone(item.summary)

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
            summary='Excel Summary',
            personalization='Design: Blue Sample Request',
            sample_name='Blue Sample Request',
            is_sample=True,
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
        self.assertEqual(row['Summary'], 'Excel Summary')
        self.assertEqual(row['Personalization'], 'Design: Blue Sample Request')
        self.assertEqual(row['Sample Name'], 'Blue Sample Request')
        self.assertTrue(row['Is Sample'])

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

    def test_with_items_defaults_to_last_three_days_plus_older_unprinted_items(self):
        tiaknight_tz = ZoneInfo('Europe/London')
        today = timezone.localtime(timezone.now(), tiaknight_tz).date()

        recent_order = Order.objects.create(
            customer_name='Recent Customer',
            total_amount=Decimal('10.00'),
            created_by=self.user,
        )
        old_unprinted_order = Order.objects.create(
            customer_name='Old Unprinted Customer',
            total_amount=Decimal('10.00'),
            created_by=self.user,
        )
        old_printed_order = Order.objects.create(
            customer_name='Old Printed Customer',
            total_amount=Decimal('10.00'),
            created_by=self.user,
        )
        Order.objects.filter(pk=recent_order.pk).update(order_date=timezone.make_aware(
            timezone.datetime.combine(today - timedelta(days=2), timezone.datetime.min.time()),
            tiaknight_tz,
        ))
        Order.objects.filter(pk=old_unprinted_order.pk).update(order_date=timezone.make_aware(
            timezone.datetime.combine(today - timedelta(days=5), timezone.datetime.min.time()),
            tiaknight_tz,
        ))
        Order.objects.filter(pk=old_printed_order.pk).update(order_date=timezone.make_aware(
            timezone.datetime.combine(today - timedelta(days=5), timezone.datetime.min.time()),
            tiaknight_tz,
        ))
        OrderItem.objects.create(
            order=recent_order,
            sku='RECENT',
            product_name='Recent Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
            lable_printed=True,
        )
        OrderItem.objects.create(
            order=old_unprinted_order,
            sku='OLD-UNPRINTED',
            product_name='Old Unprinted Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
            lable_printed=False,
        )
        OrderItem.objects.create(
            order=old_printed_order,
            sku='OLD-PRINTED',
            product_name='Old Printed Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
            lable_printed=True,
        )

        response = self.client.get('/api/v1/orders/with-items/')

        self.assertEqual(response.status_code, 200)
        returned_ids = {row['id'] for row in response.data['results']}
        self.assertIn(recent_order.id, returned_ids)
        self.assertIn(old_unprinted_order.id, returned_ids)
        self.assertNotIn(old_printed_order.id, returned_ids)

    def test_with_items_filters_by_sample_items(self):
        sample_order = Order.objects.create(
            customer_name='Sample Customer',
            total_amount=Decimal('0.50'),
            created_by=self.user,
        )
        regular_order = Order.objects.create(
            customer_name='Regular Customer',
            total_amount=Decimal('10.00'),
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=sample_order,
            sku='SAMPLE-SQ209 RBL',
            product_name='Cotton Fine Rib, Length: Sample (6 x 6")',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('0.50'),
            is_sample=True,
        )
        OrderItem.objects.create(
            order=regular_order,
            sku='SQ209 RBL',
            product_name='Cotton Fine Rib',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
            is_sample=False,
        )

        sample_response = self.client.get('/api/v1/orders/with-items/?is_sample=true')
        regular_response = self.client.get('/api/v1/orders/with-items/?is_sample=false')

        self.assertEqual(sample_response.status_code, 200)
        self.assertEqual(regular_response.status_code, 200)
        self.assertEqual({row['id'] for row in sample_response.data['results']}, {sample_order.id})
        self.assertEqual({row['id'] for row in regular_response.data['results']}, {regular_order.id})

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
    @patch('orders.services.royal_mail.requests.get')
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_creates_remote_order_and_marks_shipped(self, mock_post, mock_get):
        self._mock_royal_mail_label_response(mock_get)
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
            external_order_id='WEB-RM-001',
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
        self.assertEqual(response.data['royal_mail_reference'], 'WEB-RM-001')
        self.assertEqual(order.tracking_number, 'RMTRACK123')
        self.assertEqual(order.carrier, 'Royal Mail')
        self.assertEqual(order.shipping_method, 'TPLN')
        self.assertEqual(order.royal_mail_order_identifier, 'RM-ORDER-1')
        self.assertTrue(order.shipping_label_file)
        self.assertTrue(response.data['label_url'].endswith(f'/api/v1/orders/{order.id}/shipping-label/'))
        self.assertIn('WEB-RM-001', order.internal_notes)
        self.assertIn('Booked from API test', order.internal_notes)

        request_payload = mock_post.call_args.kwargs['json']
        request_headers = mock_post.call_args.kwargs['headers']
        self.assertEqual(request_headers['Authorization'], 'test-api-key')
        self.assertEqual(request_payload['items'][0]['orderReference'], 'WEB-RM-001')
        self.assertEqual(request_payload['items'][0]['billing']['address']['city'], 'London')
        self.assertEqual(request_payload['items'][0]['billing']['address']['postcode'], 'SW1A 1AA')
        self.assertEqual(request_payload['items'][0]['packages'][0]['weightInGrams'], 250)
        self.assertEqual(request_payload['items'][0]['packages'][0]['contents'][0]['SKU'], 'SKU-001')
        self.assertEqual(request_payload['items'][0]['label']['includeLabelInResponse'], True)
        self.assertEqual(request_payload['items'][0]['label']['includeReturnsLabel'], False)
        self.assertEqual(request_payload['items'][0]['label']['includeCN'], False)
        self.assertEqual(
            mock_get.call_args.args[0],
            'https://api.parcel.royalmail.com/api/v1/orders/RM-ORDER-1/label',
        )
        self.assertEqual(mock_get.call_args.kwargs['params']['documentType'], 'postageLabel')
        self.assertEqual(mock_get.call_args.kwargs['params']['includeReturnsLabel'], 'false')

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Parcel',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=100,
    )
    @patch('orders.services.royal_mail.requests.get')
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_can_return_pdf_directly(self, mock_post, mock_get):
        self._mock_royal_mail_label_response(mock_get, content=b'%PDF-1.4 direct label')
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            'items': [{'orderIdentifier': 'RM-ORDER-PDF', 'trackingNumber': 'RMPDF'}]
        }
        mock_post.return_value = mock_response

        order = Order.objects.create(
            customer_name='Direct PDF Customer',
            external_order_id='WEB-RM-PDF',
            customer_email='pdf@example.com',
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
            sku='SKU-PDF',
            product_name='Direct PDF Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {'weight_in_grams': 100, 'service_code': 'STD', 'return_label_pdf': True},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4 direct label')
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.STATUS_SHIPPED)
        self.assertTrue(order.shipping_label_file)

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
    )
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_blocks_duplicate_booking_for_shipped_order(self, mock_post):
        order = Order.objects.create(
            customer_name='Already Shipped Customer',
            external_order_id='WEB-RM-SHIPPED',
            customer_email='shipped@example.com',
            shipping_address_line1='1 Test Street',
            shipping_city='London',
            shipping_postal_code='SW1A 1AA',
            shipping_country='UK',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_SHIPPED,
            tracking_number='RMTRACK-EXISTING',
            carrier='Royal Mail',
            created_by=self.user,
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {'weight_in_grams': 100},
            format='json',
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['order_status'], Order.STATUS_SHIPPED)
        self.assertEqual(response.data['tracking_number'], 'RMTRACK-EXISTING')
        mock_post.assert_not_called()

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
    )
    @patch('orders.services.royal_mail.requests.get')
    def test_shipping_label_fetches_and_returns_pdf_from_royal_mail(self, mock_get):
        self._mock_royal_mail_label_response(mock_get, content=b'%PDF-1.4 fetched label')
        order = Order.objects.create(
            customer_name='Label Customer',
            external_order_id='WEB-LABEL-001',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_SHIPPED,
            royal_mail_order_identifier='RM-LABEL-1',
            created_by=self.user,
        )

        response = self.client.get(f'/api/v1/orders/{order.id}/shipping-label/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4 fetched label')
        order.refresh_from_db()
        self.assertTrue(order.shipping_label_file)
        self.assertIsNotNone(order.shipping_label_downloaded_at)
        self.assertEqual(
            mock_get.call_args.args[0],
            'https://api.parcel.royalmail.com/api/v1/orders/RM-LABEL-1/label',
        )
        self.assertEqual(mock_get.call_args.kwargs['params']['documentType'], 'postageLabel')
        self.assertEqual(mock_get.call_args.kwargs['params']['includeReturnsLabel'], 'false')

    def test_shipping_label_requires_saved_royal_mail_identifier(self):
        order = Order.objects.create(
            customer_name='No Label Customer',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_SHIPPED,
            created_by=self.user,
        )

        response = self.client.get(f'/api/v1/orders/{order.id}/shipping-label/')

        self.assertEqual(response.status_code, 400)
        self.assertIn('No Royal Mail order identifier', response.data['error'])

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
    )
    @patch('orders.services.royal_mail.requests.get')
    def test_shipping_label_returns_clear_postage_not_applied_error(self, mock_get):
        mock_response = Mock(status_code=400)
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.json.return_value = [
            {
                'accountOrderNumber': 157272,
                'channelOrderReference': 'WEB238404',
                'code': 'OrderValidationError',
                'message': 'Label generation only available for orders with postage applied status',
            }
        ]
        mock_get.return_value = mock_response

        order = Order.objects.create(
            customer_name='Postage Pending Customer',
            external_order_id='WEB238404',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_COMPLETED,
            royal_mail_order_identifier='157272',
            created_by=self.user,
        )

        response = self.client.get(f'/api/v1/orders/{order.id}/shipping-label/')

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'ROYAL_MAIL_POSTAGE_NOT_APPLIED')
        self.assertIn('postage has not been applied', response.data['message'])
        self.assertEqual(response.data['royal_mail_response'][0]['channelOrderReference'], 'WEB238404')

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Parcel',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=100,
    )
    @patch('orders.services.royal_mail.requests.get')
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_does_not_mark_shipped_when_postage_not_applied(self, mock_post, mock_get):
        create_response = Mock(status_code=200)
        create_response.json.return_value = {
            'items': [{'orderIdentifier': '157272', 'orderReference': 'WEB238404'}],
        }
        mock_post.return_value = create_response

        label_response = Mock(status_code=400)
        label_response.headers = {'Content-Type': 'application/json'}
        label_response.json.return_value = [
            {
                'accountOrderNumber': 157272,
                'channelOrderReference': 'WEB238404',
                'code': 'OrderValidationError',
                'message': 'Label generation only available for orders with postage applied status',
            }
        ]
        mock_get.return_value = label_response

        order = Order.objects.create(
            customer_name='Postage Pending Booking Customer',
            external_order_id='WEB238404',
            customer_email='pending@example.com',
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
            sku='SKU-PENDING',
            product_name='Postage Pending Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {'weight_in_grams': 100, 'service_code': 'STD'},
            format='json',
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data['label_download_error']['code'], 'ROYAL_MAIL_POSTAGE_NOT_APPLIED')
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.STATUS_COMPLETED)
        self.assertEqual(order.royal_mail_order_identifier, '157272')
        self.assertFalse(order.shipping_label_file)

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Parcel',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=100,
    )
    @patch('orders.services.royal_mail.requests.delete')
    @patch('orders.services.royal_mail.requests.get')
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_replaces_unpostaged_draft_order(self, mock_post, mock_get, mock_delete):
        delete_response = Mock(status_code=200)
        delete_response.json.return_value = {'deletedOrders': [{'orderIdentifier': '157272'}]}
        mock_delete.return_value = delete_response
        self._mock_royal_mail_label_response(mock_get)

        create_response = Mock(status_code=200)
        create_response.json.return_value = {
            'items': [{'orderIdentifier': '157300', 'trackingNumber': 'RMREBOOKED'}],
        }
        mock_post.return_value = create_response

        order = Order.objects.create(
            customer_name='Draft Replacement Customer',
            external_order_id='WEB238404',
            customer_email='draft@example.com',
            shipping_address_line1='1 Test Street',
            shipping_city='London',
            shipping_postal_code='SW1A 1AA',
            shipping_country='UK',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_COMPLETED,
            royal_mail_order_identifier='157272',
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SKU-DRAFT',
            product_name='Draft Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {'weight_in_grams': 100, 'service_code': 'STD'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['replaced_royal_mail_order_identifier'], '157272')
        self.assertEqual(mock_delete.call_args.args[0], 'https://api.parcel.royalmail.com/api/v1/orders/157272')
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.STATUS_SHIPPED)
        self.assertEqual(order.royal_mail_order_identifier, '157300')
        self.assertEqual(order.tracking_number, 'RMREBOOKED')
        self.assertTrue(order.shipping_label_file)

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Parcel',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=100,
        ROYAL_MAIL_REPLACE_UNPOSTAGED_ORDERS=False,
    )
    @patch('orders.services.royal_mail.requests.delete')
    @patch('orders.services.royal_mail.requests.get')
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_blocks_existing_draft_when_replacement_disabled(
        self,
        mock_post,
        mock_get,
        mock_delete,
    ):
        order = Order.objects.create(
            customer_name='No Replacement Customer',
            external_order_id='WEB238405',
            customer_email='no-replace@example.com',
            shipping_address_line1='1 Test Street',
            shipping_city='London',
            shipping_postal_code='SW1A 1AA',
            shipping_country='UK',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_COMPLETED,
            royal_mail_order_identifier='157272',
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SKU-NO-REPLACE',
            product_name='No Replace Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {'weight_in_grams': 100, 'service_code': 'STD'},
            format='json',
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn('replacing unpostaged', response.data['message'])
        mock_post.assert_not_called()
        mock_get.assert_not_called()
        mock_delete.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.royal_mail_order_identifier, '157272')

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Parcel',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=100,
    )
    @patch('orders.services.royal_mail.requests.get')
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_auto_selects_letter_stl2_for_std_up_to_100g(self, mock_post, mock_get):
        self._mock_royal_mail_label_response(mock_get)
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            'items': [{'orderIdentifier': 'RM-ORDER-STD-100', 'trackingNumber': 'RMSTD100'}]
        }
        mock_post.return_value = mock_response

        order = Order.objects.create(
            customer_name='Royal Mail Rule Customer',
            external_order_id='WEB-RM-RULE-001',
            customer_email='rule@example.com',
            shipping_address_line1='1 Test Street',
            shipping_city='London',
            shipping_postal_code='SW1A 1AA',
            shipping_country='UK',
            courier_service_code='STD',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_COMPLETED,
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SKU-STD-100',
            product_name='Small Standard Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {'weight_in_grams': 100},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.shipping_method, 'STL2')
        request_payload = mock_post.call_args.kwargs['json']
        self.assertEqual(request_payload['items'][0]['packages'][0]['weightInGrams'], 100)
        self.assertEqual(request_payload['items'][0]['packages'][0]['packageFormatIdentifier'], 'Letter')
        self.assertEqual(request_payload['items'][0]['postageDetails']['serviceCode'], 'STL2')
        self.assertEqual(response.data['royal_mail_booking_options']['package_format_identifier'], 'Letter')
        self.assertEqual(response.data['royal_mail_booking_options']['service_code'], 'STL2')

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Parcel',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=100,
    )
    @patch('orders.services.royal_mail.requests.get')
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_converts_payload_std_to_royal_mail_service_code(self, mock_post, mock_get):
        self._mock_royal_mail_label_response(mock_get)
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            'items': [{'orderIdentifier': 'RM-ORDER-STD-PAYLOAD', 'trackingNumber': 'RMSTDPAY'}]
        }
        mock_post.return_value = mock_response

        order = Order.objects.create(
            customer_name='Payload STD Customer',
            external_order_id='WEB-RM-STD-PAYLOAD',
            customer_email='payload-std@example.com',
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
            sku='SKU-STD-PAYLOAD',
            product_name='Small Standard Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {
                'weight_in_grams': 100,
                'package_format_identifier': 'Parcel',
                'service_code': 'STD',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        request_payload = mock_post.call_args.kwargs['json']
        self.assertEqual(request_payload['items'][0]['packages'][0]['packageFormatIdentifier'], 'Letter')
        self.assertEqual(request_payload['items'][0]['postageDetails']['serviceCode'], 'STL2')
        self.assertNotEqual(request_payload['items'][0]['postageDetails']['serviceCode'], 'STD')
        self.assertEqual(response.data['royal_mail_booking_options']['package_format_identifier'], 'Letter')
        self.assertEqual(response.data['royal_mail_booking_options']['service_code'], 'STL2')

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Parcel',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=100,
    )
    @patch('orders.services.royal_mail.requests.get')
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_auto_selects_large_letter_for_std_101_to_500g(self, mock_post, mock_get):
        self._mock_royal_mail_label_response(mock_get)
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            'items': [{'orderIdentifier': 'RM-ORDER-STD-500', 'trackingNumber': 'RMSTD500'}]
        }
        mock_post.return_value = mock_response

        order = Order.objects.create(
            customer_name='Royal Mail Rule Customer',
            external_order_id='WEB-RM-RULE-002',
            customer_email='rule2@example.com',
            shipping_address_line1='1 Test Street',
            shipping_city='London',
            shipping_postal_code='SW1A 1AA',
            shipping_country='UK',
            courier_service_code='STD',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_COMPLETED,
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SKU-STD-500',
            product_name='Medium Standard Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {'weight_in_grams': 250},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        request_payload = mock_post.call_args.kwargs['json']
        self.assertEqual(request_payload['items'][0]['packages'][0]['packageFormatIdentifier'], 'Large Letter')
        self.assertEqual(request_payload['items'][0]['postageDetails']['serviceCode'], 'TRS48')

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Parcel',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=100,
    )
    @patch('orders.services.royal_mail.requests.get')
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_auto_selects_amazon_friday_next_day_service(self, mock_post, mock_get):
        self._mock_royal_mail_label_response(mock_get)
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            'items': [{'orderIdentifier': 'RM-ORDER-AMZ', 'trackingNumber': 'RMAMZ'}]
        }
        mock_post.return_value = mock_response

        order = Order.objects.create(
            customer_name='Amazon Friday Customer',
            external_order_id='AMZ-RM-RULE-001',
            customer_email='amazon@example.com',
            shipping_address_line1='1 Test Street',
            shipping_city='London',
            shipping_postal_code='SW1A 1AA',
            shipping_country='UK',
            order_source='AMAZON',
            courier_service_code='NEXT DAY',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_COMPLETED,
            order_date=timezone.make_aware(timezone.datetime(2026, 8, 14, 10, 0, 0)),
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SKU-AMZ',
            product_name='Amazon Next Day Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {'weight_in_grams': 250},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        request_payload = mock_post.call_args.kwargs['json']
        self.assertEqual(request_payload['items'][0]['packages'][0]['packageFormatIdentifier'], 'Large Letter')
        self.assertEqual(request_payload['items'][0]['postageDetails']['serviceCode'], 'TRN24')

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Parcel',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=100,
    )
    @patch('orders.services.royal_mail.requests.get')
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_auto_selects_web_next_day_parcel_service(self, mock_post, mock_get):
        self._mock_royal_mail_label_response(mock_get)
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            'items': [{'orderIdentifier': 'RM-ORDER-WEB-ND', 'trackingNumber': 'RMWEBND'}]
        }
        mock_post.return_value = mock_response

        order = Order.objects.create(
            customer_name='Web Next Day Customer',
            external_order_id='WEB238423',
            customer_email='web-next-day@example.com',
            shipping_address_line1='42 Hornbeam Way',
            shipping_city='Leeds',
            shipping_postal_code='LS14 2HP',
            shipping_country='UK - Mainland',
            order_source=Order.SOURCE_WEBSITE,
            courier_service_code='NEXT DAY',
            courier_service_name='Next Day Delivery (next working day if ordered before 1pm)',
            total_amount=Decimal('26.48'),
            order_status=Order.STATUS_COMPLETED,
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SQ921 NYWHT',
            product_name='Printed Matte Swimwear Nylon Lycra 4 Way Stretch Fabric',
            quantity=3,
            quantity_ordered=3,
            unit_price=Decimal('8.83'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {'weight_in_grams': 900},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['label_url'].startswith('http://testserver/'))
        self.assertTrue(response.data['order']['shipping_label_url'].startswith('http://testserver/'))
        self.assertEqual(response.data['royal_mail_booking_options']['package_format_identifier'], 'Parcel')
        self.assertEqual(response.data['royal_mail_booking_options']['service_code'], 'TPN24')
        request_payload = mock_post.call_args.kwargs['json']
        self.assertEqual(request_payload['items'][0]['packages'][0]['packageFormatIdentifier'], 'Parcel')
        self.assertEqual(request_payload['items'][0]['postageDetails']['serviceCode'], 'TPN24')

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Parcel',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=100,
    )
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_requires_known_service_mapping(self, mock_post):
        order = Order.objects.create(
            customer_name='Unsupported Delivery Customer',
            external_order_id='WEB-RM-UNSUPPORTED',
            customer_email='unsupported@example.com',
            shipping_address_line1='1 Test Street',
            shipping_city='London',
            shipping_postal_code='SW1A 1AA',
            shipping_country='UK',
            courier_service_code='SATURDAY',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_COMPLETED,
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='SKU-UNSUPPORTED',
            product_name='Unsupported Delivery Product',
            quantity=1,
            quantity_ordered=1,
            unit_price=Decimal('10.00'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {'weight_in_grams': 900},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('No Royal Mail service code mapping found', response.data['error'])
        mock_post.assert_not_called()

    @override_settings(
        ROYAL_MAIL_API_KEY='test-api-key',
        ROYAL_MAIL_API_BASE_URL='https://api.parcel.royalmail.com/api/v1',
        ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT='Letter',
        ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS=50,
    )
    @patch('orders.services.royal_mail.requests.get')
    @patch('orders.services.royal_mail.requests.post')
    def test_book_royal_mail_shipping_auto_selects_fleece_parcel_for_std_up_to_5m(self, mock_post, mock_get):
        self._mock_royal_mail_label_response(mock_get)
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            'items': [{'orderIdentifier': 'RM-ORDER-FLEECE', 'trackingNumber': 'RMFLEECE'}]
        }
        mock_post.return_value = mock_response

        order = Order.objects.create(
            customer_name='Fleece Customer',
            external_order_id='WEB-RM-FLEECE-001',
            customer_email='fleece@example.com',
            shipping_address_line1='1 Test Street',
            shipping_city='London',
            shipping_postal_code='SW1A 1AA',
            shipping_country='UK',
            courier_service_code='STD',
            total_amount=Decimal('10.00'),
            order_status=Order.STATUS_COMPLETED,
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            sku='FLEECE-001',
            product_name='Polar Fleece Fabric',
            quantity=5,
            quantity_ordered=5,
            unit_price=Decimal('2.00'),
        )

        response = self.client.post(
            f'/api/v1/orders/{order.id}/book-royal-mail-shipping/',
            {'weight_in_grams': 250},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        request_payload = mock_post.call_args.kwargs['json']
        self.assertEqual(request_payload['items'][0]['packages'][0]['packageFormatIdentifier'], 'Parcel')
        self.assertEqual(request_payload['items'][0]['postageDetails']['serviceCode'], 'TPS48')

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


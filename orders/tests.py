# Tests for Order Management with Employee Assignment
from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from rest_framework.test import APIClient
from .models import Order, OrderItem
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
        Order.objects.create(
            customer_name='New Customer',
            order_status=Order.STATUS_NEW,
            total_amount=Decimal('1.00'),
        )
        Order.objects.create(
            customer_name='Progress Customer',
            order_status=Order.STATUS_IN_PROGRESS,
            total_amount=Decimal('1.00'),
        )
        Order.objects.create(
            customer_name='Completed Customer',
            order_status=Order.STATUS_COMPLETED,
            total_amount=Decimal('1.00'),
        )

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


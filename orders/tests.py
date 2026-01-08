# Tests for Order Management with Employee Assignment
from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from .models import Order, OrderItem
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
            order_status=Order.STATUS_CONFIRMED
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


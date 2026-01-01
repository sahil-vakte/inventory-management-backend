from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal
from products.models import Product
from stock.models import StockItem


class OrderManager(models.Manager):
    """Custom manager for Order model with soft delete support"""
    
    def get_queryset(self):
        """Return only non-deleted objects by default"""
        return super().get_queryset().filter(is_deleted=False)
    
    def with_deleted(self):
        """Return all objects including deleted ones"""
        return super().get_queryset()
    
    def only_deleted(self):
        """Return only deleted objects"""
        return super().get_queryset().filter(is_deleted=True)


class Order(models.Model):
    """Main order model for managing customer orders"""
    
    # Order Status Choices
    STATUS_PENDING = 'PENDING'
    STATUS_CONFIRMED = 'CONFIRMED'
    STATUS_PROCESSING = 'PROCESSING'
    STATUS_SHIPPED = 'SHIPPED'
    STATUS_DELIVERED = 'DELIVERED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_ON_HOLD = 'ON_HOLD'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_SHIPPED, 'Shipped'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_ON_HOLD, 'On Hold'),
    ]
    
    # Payment Status Choices
    PAYMENT_UNPAID = 'UNPAID'
    PAYMENT_PARTIAL = 'PARTIAL'
    PAYMENT_PAID = 'PAID'
    PAYMENT_REFUNDED = 'REFUNDED'
    PAYMENT_FAILED = 'FAILED'
    
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_UNPAID, 'Unpaid'),
        (PAYMENT_PARTIAL, 'Partially Paid'),
        (PAYMENT_PAID, 'Paid'),
        (PAYMENT_REFUNDED, 'Refunded'),
        (PAYMENT_FAILED, 'Failed'),
    ]
    
    # Primary Fields
    order_number = models.CharField(max_length=50, unique=True, 
                                    help_text="Unique order number")
    external_order_id = models.CharField(max_length=100, blank=True, null=True,
                                        help_text="External system order ID (from XML)")
    
    # Customer Information
    customer_name = models.CharField(max_length=200, help_text="Customer full name")
    customer_email = models.EmailField(blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    customer_company = models.CharField(max_length=200, blank=True, null=True)
    
    # Addresses (stored as text fields for flexibility)
    shipping_address_line1 = models.CharField(max_length=200, blank=True, null=True)
    shipping_address_line2 = models.CharField(max_length=200, blank=True, null=True)
    shipping_city = models.CharField(max_length=100, blank=True, null=True)
    shipping_state = models.CharField(max_length=100, blank=True, null=True)
    shipping_postal_code = models.CharField(max_length=20, blank=True, null=True)
    shipping_country = models.CharField(max_length=100, default='UK')
    
    billing_address_line1 = models.CharField(max_length=200, blank=True, null=True)
    billing_address_line2 = models.CharField(max_length=200, blank=True, null=True)
    billing_city = models.CharField(max_length=100, blank=True, null=True)
    billing_state = models.CharField(max_length=100, blank=True, null=True)
    billing_postal_code = models.CharField(max_length=20, blank=True, null=True)
    billing_country = models.CharField(max_length=100, default='UK')
    
    # Order Status
    order_status = models.CharField(max_length=20, choices=STATUS_CHOICES, 
                                   default=STATUS_PENDING)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES,
                                     default=PAYMENT_UNPAID)
    
    # Dates
    order_date = models.DateTimeField(default=timezone.now)
    confirmed_date = models.DateTimeField(blank=True, null=True)
    shipped_date = models.DateTimeField(blank=True, null=True)
    delivered_date = models.DateTimeField(blank=True, null=True)
    expected_delivery_date = models.DateTimeField(blank=True, null=True)
    
    # Financial Information
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'),
                                  help_text="Sum of all line items before tax and shipping")
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'),
                                  help_text="Tax rate percentage")
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'),
                                      help_text="Final total including tax and shipping")
    
    # Payment Information
    payment_method = models.CharField(max_length=50, blank=True, null=True,
                                     help_text="e.g., Credit Card, PayPal, Bank Transfer")
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    
    # Shipping Information
    shipping_method = models.CharField(max_length=100, blank=True, null=True,
                                      help_text="e.g., Standard, Express, Next Day")
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    carrier = models.CharField(max_length=100, blank=True, null=True,
                              help_text="Shipping carrier/courier")
    
    # Notes and Additional Info
    customer_notes = models.TextField(blank=True, null=True,
                                     help_text="Notes from customer")
    internal_notes = models.TextField(blank=True, null=True,
                                     help_text="Internal notes (not visible to customer)")
    
    # User Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name='orders_created',
                                  help_text="User who created this order")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                  related_name='orders_updated', blank=True,
                                  help_text="User who last updated this order")
    
    # Source tracking
    order_source = models.CharField(max_length=50, default='MANUAL',
                                   help_text="Source of order: MANUAL, XML, API, WEBSITE")
    
    # Soft Delete Fields
    is_deleted = models.BooleanField(default=False, help_text="Soft delete flag")
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="When the record was deleted")
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='orders_deleted')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Managers
    objects = OrderManager()
    all_objects = models.Manager()
    
    class Meta:
        db_table = 'orders'
        ordering = ['-order_date', '-created_at']
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['order_status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['customer_email']),
            models.Index(fields=['order_date']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.order_number} - {self.customer_name} - {self.get_order_status_display()}"
    
    def save(self, *args, **kwargs):
        """Auto-generate order number if not provided"""
        if not self.order_number:
            # Generate order number: ORD-YYYYMMDD-XXXX
            from django.db.models import Max
            today = timezone.now().date()
            prefix = f"ORD-{today.strftime('%Y%m%d')}"
            
            # Get last order number for today
            last_order = Order.all_objects.filter(
                order_number__startswith=prefix
            ).aggregate(Max('order_number'))
            
            if last_order['order_number__max']:
                last_num = int(last_order['order_number__max'].split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.order_number = f"{prefix}-{new_num:04d}"
        
        # Calculate total if not set
        if not self.total_amount or self.total_amount == 0:
            self.calculate_totals()
        
        super().save(*args, **kwargs)
    
    def calculate_totals(self):
        """Calculate order totals from order items"""
        items = self.items.all()
        self.subtotal = sum(item.line_total for item in items)
        
        # Calculate tax
        if self.tax_rate and self.tax_rate > 0:
            self.tax_amount = (self.subtotal * self.tax_rate) / Decimal('100.00')
        else:
            self.tax_amount = Decimal('0.00')
        
        # Calculate total
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_cost - self.discount_amount
    
    def soft_delete(self, user=None):
        """Soft delete the order"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user:
            self.deleted_by = user
        self.save()
        
        # Also release any reserved stock
        for item in self.items.all():
            if item.stock_item and item.stock_item.reserved_stock >= item.quantity:
                item.stock_item.release_stock(item.quantity)
    
    def restore(self):
        """Restore soft deleted order"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()
    
    def hard_delete(self):
        """Permanently delete the order"""
        super().delete()
    
    def confirm(self, user=None):
        """Confirm the order"""
        if self.order_status != self.STATUS_PENDING:
            raise ValueError(f"Cannot confirm order in {self.order_status} status")
        
        self.order_status = self.STATUS_CONFIRMED
        self.confirmed_date = timezone.now()
        if user:
            self.updated_by = user
        self.save()
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=self,
            from_status=self.STATUS_PENDING,
            to_status=self.STATUS_CONFIRMED,
            changed_by=user,
            change_reason="Order confirmed"
        )
    
    def start_processing(self, user=None):
        """Mark order as processing"""
        if self.order_status not in [self.STATUS_PENDING, self.STATUS_CONFIRMED]:
            raise ValueError(f"Cannot process order in {self.order_status} status")
        
        old_status = self.order_status
        self.order_status = self.STATUS_PROCESSING
        if user:
            self.updated_by = user
        self.save()
        
        OrderStatusHistory.objects.create(
            order=self,
            from_status=old_status,
            to_status=self.STATUS_PROCESSING,
            changed_by=user,
            change_reason="Order processing started"
        )
    
    def mark_shipped(self, tracking_number=None, carrier=None, user=None):
        """Mark order as shipped"""
        if self.order_status not in [self.STATUS_CONFIRMED, self.STATUS_PROCESSING]:
            raise ValueError(f"Cannot ship order in {self.order_status} status")
        
        old_status = self.order_status
        self.order_status = self.STATUS_SHIPPED
        self.shipped_date = timezone.now()
        
        if tracking_number:
            self.tracking_number = tracking_number
        if carrier:
            self.carrier = carrier
        if user:
            self.updated_by = user
        
        self.save()
        
        OrderStatusHistory.objects.create(
            order=self,
            from_status=old_status,
            to_status=self.STATUS_SHIPPED,
            changed_by=user,
            change_reason=f"Order shipped{f' via {carrier}' if carrier else ''}"
        )
    
    def mark_delivered(self, user=None):
        """Mark order as delivered"""
        if self.order_status != self.STATUS_SHIPPED:
            raise ValueError(f"Cannot deliver order in {self.order_status} status")
        
        self.order_status = self.STATUS_DELIVERED
        self.delivered_date = timezone.now()
        if user:
            self.updated_by = user
        self.save()
        
        OrderStatusHistory.objects.create(
            order=self,
            from_status=self.STATUS_SHIPPED,
            to_status=self.STATUS_DELIVERED,
            changed_by=user,
            change_reason="Order delivered"
        )
    
    def cancel(self, reason=None, user=None):
        """Cancel the order and release stock"""
        if self.order_status in [self.STATUS_DELIVERED, self.STATUS_CANCELLED]:
            raise ValueError(f"Cannot cancel order in {self.order_status} status")
        
        old_status = self.order_status
        self.order_status = self.STATUS_CANCELLED
        if user:
            self.updated_by = user
        self.save()
        
        # Release reserved stock for all items
        for item in self.items.all():
            item.release_stock()
        
        OrderStatusHistory.objects.create(
            order=self,
            from_status=old_status,
            to_status=self.STATUS_CANCELLED,
            changed_by=user,
            change_reason=reason or "Order cancelled"
        )
    
    @property
    def item_count(self):
        """Total number of items in the order"""
        return self.items.count()
    
    @property
    def total_quantity(self):
        """Total quantity of all items"""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def is_paid(self):
        """Check if order is fully paid"""
        return self.payment_status == self.PAYMENT_PAID
    
    @property
    def shipping_address(self):
        """Get formatted shipping address"""
        parts = [
            self.shipping_address_line1,
            self.shipping_address_line2,
            self.shipping_city,
            self.shipping_state,
            self.shipping_postal_code,
            self.shipping_country
        ]
        return ', '.join(filter(None, parts))
    
    @property
    def billing_address(self):
        """Get formatted billing address"""
        parts = [
            self.billing_address_line1,
            self.billing_address_line2,
            self.billing_city,
            self.billing_state,
            self.billing_postal_code,
            self.billing_country
        ]
        return ', '.join(filter(None, parts))


class OrderItem(models.Model):
    """Individual items within an order"""
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    
    # Product References
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True,
                               help_text="Reference to product (optional)")
    stock_item = models.ForeignKey(StockItem, on_delete=models.SET_NULL, null=True, blank=True,
                                  help_text="Reference to stock item (optional)")
    
    # Denormalized fields (stored at time of order for historical accuracy)
    sku = models.CharField(max_length=50, help_text="SKU at time of order")
    product_name = models.CharField(max_length=500, help_text="Product name at time of order")
    product_type = models.CharField(max_length=50, blank=True, null=True)
    color_code = models.CharField(max_length=10, blank=True, null=True)
    
    # Quantity and Pricing
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2,
                                    help_text="Price per unit at time of order")
    line_total = models.DecimalField(max_digits=12, decimal_places=2,
                                    help_text="Total for this line (quantity * unit_price - discount)")
    
    # Tax and Discount
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Additional Info
    notes = models.TextField(blank=True, null=True, help_text="Item-specific notes")
    
    # Stock reservation tracking
    stock_reserved = models.BooleanField(default=False, 
                                        help_text="Whether stock has been reserved for this item")
    stock_fulfilled = models.BooleanField(default=False,
                                         help_text="Whether this item has been fulfilled")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'order_items'
        ordering = ['id']
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
        indexes = [
            models.Index(fields=['order', 'sku']),
            models.Index(fields=['sku']),
        ]
    
    def __str__(self):
        return f"{self.order.order_number} - {self.sku} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        """Calculate line total before saving"""
        if not self.line_total or self.line_total == 0:
            self.line_total = (self.unit_price * self.quantity) - self.discount_amount
        super().save(*args, **kwargs)
    
    def reserve_stock(self):
        """Reserve stock for this order item"""
        if self.stock_item and not self.stock_reserved:
            success = self.stock_item.reserve_stock(self.quantity)
            if success:
                self.stock_reserved = True
                self.save()
            return success
        return False
    
    def release_stock(self):
        """Release reserved stock"""
        if self.stock_item and self.stock_reserved:
            success = self.stock_item.release_stock(self.quantity)
            if success:
                self.stock_reserved = False
                self.save()
            return success
        return False


class OrderStatusHistory(models.Model):
    """Track order status changes for audit trail"""
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    
    from_status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES,
                                  help_text="Previous status")
    to_status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES,
                                help_text="New status")
    
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  help_text="User who made the change")
    change_reason = models.CharField(max_length=200, blank=True, null=True,
                                    help_text="Reason for status change")
    notes = models.TextField(blank=True, null=True, help_text="Additional notes")
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_status_history'
        ordering = ['-timestamp']
        verbose_name = 'Order Status History'
        verbose_name_plural = 'Order Status Histories'
        indexes = [
            models.Index(fields=['order', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.order.order_number}: {self.from_status} → {self.to_status}"

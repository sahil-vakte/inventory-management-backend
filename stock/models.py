from django.db import models
from django.utils import timezone
from colors.models import Color

class StockManager(models.Manager):
    """Custom manager for Stock models with soft delete support"""
    
    def get_queryset(self):
        """Return only non-deleted objects by default"""
        return super().get_queryset().filter(is_deleted=False)
    
    def with_deleted(self):
        """Return all objects including deleted ones"""
        return super().get_queryset()
    
    def only_deleted(self):
        """Return only deleted objects"""
        return super().get_queryset().filter(is_deleted=True)

class StockItem(models.Model):
    primary_location = models.ForeignKey('products.Location', on_delete=models.SET_NULL, blank=True, null=True, related_name='primary_stock_items', help_text="Primary location where the stock item is stored")
    secondary_location = models.ForeignKey('products.Location', on_delete=models.SET_NULL, blank=True, null=True, related_name='secondary_stock_items', help_text="Secondary/backup location for the stock item")
    """Stock management model based on Current Stock Excel sheet"""
    
    # Product identification
    product_type = models.CharField(max_length=20, help_text="Product Type (e.g., 109LT)")
    color = models.ForeignKey(Color, on_delete=models.CASCADE, 
                             to_field='color_code', db_column='color_code')
    sku = models.CharField(max_length=50, unique=True, primary_key=True,
                          help_text="Stock Keeping Unit - unique identifier")
    
    # Stock levels
    available_stock_rolls = models.IntegerField(default=0, 
                                               help_text="Available stock in rolls")
    reserved_stock = models.IntegerField(default=0,
                                        help_text="Stock reserved for orders")
    minimum_stock_level = models.IntegerField(default=0,
                                             help_text="Minimum stock threshold")
    maximum_stock_level = models.IntegerField(default=100,
                                             help_text="Maximum stock capacity")
    
    # Location and tracking
    warehouse_location = models.CharField(max_length=50, blank=True, null=True,
                                         help_text="Physical location in warehouse")
    supplier = models.CharField(max_length=100, blank=True, null=True,
                               help_text="Primary supplier")
    lead_time_days = models.PositiveIntegerField(default=7,
                                                help_text="Supplier lead time in days")
    
    # Cost tracking
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                   help_text="Cost per unit")
    last_purchase_price = models.DecimalField(max_digits=10, decimal_places=2, 
                                             default=0.00,
                                             help_text="Last purchase price")
    last_purchase_date = models.DateTimeField(blank=True, null=True)
    
    # Status and notes
    is_active = models.BooleanField(default=True)
    is_discontinued = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True,
                            help_text="Additional notes about this stock item")
    
    # Soft delete fields
    is_deleted = models.BooleanField(default=False, help_text="Soft delete flag")
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="When the record was deleted")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_stock_update = models.DateTimeField(auto_now=True)
    
    # Managers
    objects = StockManager()
    all_objects = models.Manager()
    
    class Meta:
        db_table = 'stock'
        ordering = ['sku']
        verbose_name = 'Stock Item'
        verbose_name_plural = 'Stock Items'
        indexes = [
            models.Index(fields=['product_type']),
            models.Index(fields=['color']),
            models.Index(fields=['is_active']),
            models.Index(fields=['available_stock_rolls']),
        ]
    
    def __str__(self):
        return f"{self.sku} - {self.available_stock_rolls} rolls"
    
    @property
    def total_available_stock(self):
        """Returns available stock minus reserved stock"""
        return max(0, self.available_stock_rolls - self.reserved_stock)
    
    @property
    def is_low_stock(self):
        """Returns True if stock is below minimum level"""
        return self.available_stock_rolls <= self.minimum_stock_level
    
    @property
    def stock_status(self):
        """Returns stock status string"""
        if self.is_discontinued:
            return "Discontinued"
        elif not self.is_active:
            return "Inactive"
        elif self.available_stock_rolls == 0:
            return "Out of Stock"
        elif self.is_low_stock:
            return "Low Stock"
        else:
            return "In Stock"
    
    @property
    def stock_value(self):
        """Calculate total value of stock"""
        return self.available_stock_rolls * self.unit_cost
    
    def reserve_stock(self, quantity):
        """Reserve stock for an order"""
        if self.total_available_stock >= quantity:
            self.reserved_stock += quantity
            self.save()
            return True
        return False
    
    def release_stock(self, quantity):
        """Release reserved stock"""
        if self.reserved_stock >= quantity:
            self.reserved_stock -= quantity
            self.save()
            return True
        return False
    
    def adjust_stock(self, quantity, reason="Manual Adjustment"):
        """Adjust stock levels with reason tracking"""
        old_stock = self.available_stock_rolls
        self.available_stock_rolls = max(0, self.available_stock_rolls + quantity)
        self.last_stock_update = timezone.now()
        self.save()
        
        # Create stock movement record
        StockMovement.objects.create(
            stock_item=self,
            movement_type='ADJUSTMENT',
            quantity=quantity,
            old_stock_level=old_stock,
            new_stock_level=self.available_stock_rolls,
            reason=reason
        )
    
    def soft_delete(self):
        """Soft delete the stock item"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore soft deleted stock item"""
        self.is_deleted = False
        self.deleted_at = None
        self.save()
    
    def hard_delete(self):
        """Permanently delete the stock item"""
        super().delete()

class StockMovement(models.Model):
    """Track all stock movements for audit trail"""
    
    MOVEMENT_TYPES = [
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
        ('TRANSFER', 'Transfer'),
        ('ADJUSTMENT', 'Adjustment'),
        ('RESERVED', 'Reserved'),
        ('RELEASED', 'Released'),
        ('DAMAGED', 'Damaged'),
        ('RETURNED', 'Returned'),
    ]
    
    stock_item = models.ForeignKey(StockItem, on_delete=models.CASCADE,
                                  related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(help_text="Positive for IN, negative for OUT")
    old_stock_level = models.IntegerField()
    new_stock_level = models.IntegerField()
    
    # References
    reference_number = models.CharField(max_length=100, blank=True, null=True,
                                       help_text="Order number, transfer ID, etc.")
    reason = models.CharField(max_length=200, blank=True, null=True)
    
    # User tracking
    created_by = models.CharField(max_length=100, blank=True, null=True,
                                 help_text="User who made this movement")
    
    # Soft delete fields
    is_deleted = models.BooleanField(default=False, help_text="Soft delete flag")
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="When the record was deleted")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Managers
    objects = StockManager()
    all_objects = models.Manager()
    
    class Meta:
        db_table = 'stock_movements'
        ordering = ['-created_at']
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'
    
    def __str__(self):
        return f"{self.stock_item.sku} - {self.movement_type} ({self.quantity})"
    
    def soft_delete(self):
        """Soft delete the stock movement"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore soft deleted stock movement"""
        self.is_deleted = False
        self.deleted_at = None
        self.save()
    
    def hard_delete(self):
        """Permanently delete the stock movement"""
        super().delete()

from django.db import models
from django.conf import settings
from django.utils import timezone
from colors.models import Color
from stock.sku_utils import normalize_sku_reference

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
    # Optional relation to Product model. Nullable to avoid immediate mandatory migrations
    product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT,
        related_name='stock_items', help_text="Linked Product (required)"
    )
    color = models.ForeignKey(Color, on_delete=models.CASCADE, 
                             to_field='color_code', db_column='color_code')
    sku = models.CharField(max_length=50, unique=True, primary_key=True,
                          help_text="Stock Keeping Unit - unique identifier")
    
    # Stock levels
    available_stock_in_mtr = models.IntegerField(
        default=0,
        help_text="Available stock in metres",
    )
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
            models.Index(fields=['available_stock_in_mtr'], name='stock_availab_95624e_idx'),
        ]
    
    def __str__(self):
        return f"{self.sku} - {self.available_stock_in_mtr} mtr"

    def save(self, *args, **kwargs):
        self.sku = normalize_sku_reference(self.sku)[:50]
        self.product_type = normalize_sku_reference(self.product_type)[:20]
        super().save(*args, **kwargs)
    
    @property
    def total_available_stock(self):
        """Returns available stock minus reserved stock"""
        return max(0, self.available_stock_in_mtr - self.reserved_stock)
    
    @property
    def is_low_stock(self):
        """Returns True if stock is below minimum level"""
        return self.available_stock_in_mtr <= self.minimum_stock_level
    
    @property
    def stock_status(self):
        """Returns stock status string"""
        if self.is_discontinued:
            return "Discontinued"
        elif not self.is_active:
            return "Inactive"
        elif self.available_stock_in_mtr == 0:
            return "Out of Stock"
        elif self.is_low_stock:
            return "Low Stock"
        else:
            return "In Stock"
    
    @property
    def stock_value(self):
        """Calculate total value of stock"""
        return self.available_stock_in_mtr * self.unit_cost
    
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
        old_stock = self.available_stock_in_mtr
        self.available_stock_in_mtr = max(0, self.available_stock_in_mtr + quantity)
        self.last_stock_update = timezone.now()
        self.save()
        
        # Create stock movement record
        StockMovement.objects.create(
            stock_item=self,
            movement_type='ADJUSTMENT',
            quantity=quantity,
            old_stock_level=old_stock,
            new_stock_level=self.available_stock_in_mtr,
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


class StockBatch(models.Model):
    """Incoming stock batch containing one or more fabric rolls."""

    batch_id = models.CharField(max_length=30, unique=True, editable=False)
    stock_item = models.ForeignKey(
        StockItem, on_delete=models.PROTECT, related_name='incoming_batches'
    )
    sku = models.CharField(max_length=50, db_index=True)
    product_name = models.CharField(max_length=500)
    supplier = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_batches_created',
    )
    batch_date = models.DateField(default=timezone.localdate)
    total_meterage = models.PositiveIntegerField(default=0)
    roll_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, null=True)

    is_deleted = models.BooleanField(default=False, help_text="Soft delete flag")
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="When the record was deleted")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = StockManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'stock_batches'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['batch_id']),
            models.Index(fields=['sku']),
            models.Index(fields=['batch_date']),
            models.Index(fields=['supplier']),
        ]

    def __str__(self):
        return f"{self.batch_id} - {self.sku}"

    def save(self, *args, **kwargs):
        self.sku = normalize_sku_reference(self.sku)[:50]
        if not self.batch_id:
            self.batch_id = self._next_batch_id()
        super().save(*args, **kwargs)

    @classmethod
    def _next_batch_id(cls):
        last_batch = cls.all_objects.order_by('-id').first()
        next_number = (last_batch.id + 1) if last_batch else 1
        return f"BATCH-{next_number:06d}"

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

    def hard_delete(self):
        super().delete()


class StockBatchRoll(models.Model):
    """Individual roll meterage inside an incoming stock batch."""

    batch = models.ForeignKey(StockBatch, on_delete=models.CASCADE, related_name='rolls')
    roll_number = models.PositiveIntegerField()
    meterage = models.PositiveIntegerField()
    label_generated = models.BooleanField(default=False)
    label_generated_at = models.DateTimeField(blank=True, null=True)
    label_generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_roll_labels_generated',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stock_batch_rolls'
        ordering = ['roll_number']
        constraints = [
            models.UniqueConstraint(fields=['batch', 'roll_number'], name='unique_roll_per_stock_batch'),
        ]

    def __str__(self):
        return f"{self.batch.batch_id} - Roll {self.roll_number}: {self.meterage} mtr"

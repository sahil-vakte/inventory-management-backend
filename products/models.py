
from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.db.models import Max
class Location(models.Model):
    """Location model with custom alphanumeric primary key (LOC001, LOC002, ...)"""
    id = models.CharField(primary_key=True, max_length=10, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'locations'
        ordering = ['id']

    def save(self, *args, **kwargs):
        if not self.id:
            last = Location.objects.aggregate(max_id=Max('id'))['max_id']
            if last:
                # Extract numeric part and increment
                try:
                    last_num = int(last.replace('LOC', ''))
                except Exception:
                    last_num = 0
                next_num = last_num + 1
            else:
                next_num = 1
            self.id = f"LOC{next_num:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.id} - {self.name}"

class BaseManager(models.Manager):
    """Base manager with soft delete support"""
    
    def get_queryset(self):
        """Return only non-deleted objects by default"""
        return super().get_queryset().filter(is_deleted=False)
    
    def with_deleted(self):
        """Return all objects including deleted ones"""
        return super().get_queryset()
    
    def only_deleted(self):
        """Return only deleted objects"""
        return super().get_queryset().filter(is_deleted=True)

class Category(models.Model):
    """Product categories for organization"""
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True)
    
    # Soft delete fields
    is_deleted = models.BooleanField(default=False, help_text="Soft delete flag")
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="When the record was deleted")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Managers
    objects = BaseManager()
    all_objects = models.Manager()
    
    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def soft_delete(self):
        """Soft delete the category"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore soft deleted category"""
        self.is_deleted = False
        self.deleted_at = None
        self.save()
    
    def hard_delete(self):
        """Permanently delete the category"""
        super().delete()

class Brand(models.Model):
    """Product brands"""
    name = models.CharField(max_length=100, unique=True)
    
    # Soft delete fields
    is_deleted = models.BooleanField(default=False, help_text="Soft delete flag")
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="When the record was deleted")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Managers
    objects = BaseManager()
    all_objects = models.Manager()
    
    class Meta:
        db_table = 'brands'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def soft_delete(self):
        """Soft delete the brand"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore soft deleted brand"""
        self.is_deleted = False
        self.deleted_at = None
        self.save()
    
    def hard_delete(self):
        """Permanently delete the brand"""
        super().delete()

class Product(models.Model):
    """Main product model based on Product Master Excel sheet"""
    
    # Primary identifiers
    vs_parent_id = models.PositiveIntegerField(help_text="VS Parent ID from Excel")
    vs_child_id = models.PositiveIntegerField(unique=True, primary_key=True,
                                             help_text="VS Child ID from Excel")
    
    # References
    parent_reference = models.CharField(max_length=50, blank=True, null=True)
    child_reference = models.CharField(max_length=50, blank=True, null=True)
    
    # Product Information
    parent_product_title = models.CharField(max_length=500)
    child_product_title = models.CharField(max_length=500)
    product_subtitle = models.CharField(max_length=300, blank=True, null=True)
    product_summary = models.TextField(blank=True, null=True)
    product_description = models.TextField(blank=True, null=True)
    
    # Relations
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, blank=True, null=True)
    categories = models.ManyToManyField(Category, blank=True)
    location = models.ForeignKey('Location', on_delete=models.SET_NULL, blank=True, null=True, related_name='products', help_text="Location where the product is stored")
    
    # Attributes
    attribute_length = models.CharField(max_length=100, blank=True, null=True)
    attribute_colour = models.CharField(max_length=100, blank=True, null=True)
    attribute_top_sizes = models.CharField(max_length=100, blank=True, null=True)
    attribute_dress_sizes = models.CharField(max_length=100, blank=True, null=True)
    attribute_print = models.CharField(max_length=100, blank=True, null=True)
    attribute_weight = models.CharField(max_length=100, blank=True, null=True)
    attribute_width = models.CharField(max_length=100, blank=True, null=True)
    attribute_size = models.CharField(max_length=100, blank=True, null=True)
    attribute_choose_type = models.CharField(max_length=100, blank=True, null=True)
    attribute_design = models.CharField(max_length=100, blank=True, null=True)
    attribute_gift_card_value = models.CharField(max_length=100, blank=True, null=True)
    attribute_colours_pf = models.CharField(max_length=100, blank=True, null=True)
    
    # Tags
    tag_colours = models.CharField(max_length=200, blank=True, null=True)
    tag_matching_lycra_mesh = models.CharField(max_length=200, blank=True, null=True)
    tag_material = models.CharField(max_length=200, blank=True, null=True)
    tag_materials = models.CharField(max_length=200, blank=True, null=True)
    tag_print_texture = models.CharField(max_length=200, blank=True, null=True)
    tag_quantity_box = models.CharField(max_length=200, blank=True, null=True)
    tag_trimmings = models.CharField(max_length=200, blank=True, null=True)
    
    # Dates and Status
    release_date = models.DateTimeField(blank=True, null=True)
    available_now = models.BooleanField(default=False)
    date_added = models.DateTimeField(blank=True, null=True)
    
    # Pricing
    deposit_price_inc_vat = models.DecimalField(max_digits=10, decimal_places=2, 
                                               default=Decimal('0.00'))
    rrp_price_inc_vat = models.DecimalField(max_digits=10, decimal_places=2, 
                                           default=Decimal('0.00'))
    cost_price_inc_vat = models.DecimalField(max_digits=10, decimal_places=2, 
                                            default=Decimal('0.00'))
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'))
    
    # Price Breaks
    price_break_1_quantity = models.PositiveIntegerField(blank=True, null=True)
    price_break_1_price = models.DecimalField(max_digits=10, decimal_places=2, 
                                             blank=True, null=True)
    price_break_1_sale_price = models.DecimalField(max_digits=10, decimal_places=2, 
                                                  blank=True, null=True)
    
    price_break_2_quantity = models.PositiveIntegerField(blank=True, null=True)
    price_break_2_price = models.DecimalField(max_digits=10, decimal_places=2, 
                                             blank=True, null=True)
    price_break_2_sale_price = models.DecimalField(max_digits=10, decimal_places=2, 
                                                  blank=True, null=True)
    
    price_break_3_quantity = models.PositiveIntegerField(blank=True, null=True)
    price_break_3_price = models.DecimalField(max_digits=10, decimal_places=2, 
                                             blank=True, null=True)
    price_break_3_sale_price = models.DecimalField(max_digits=10, decimal_places=2, 
                                                  blank=True, null=True)
    
    # Stock and Purchase
    stock_value = models.DecimalField(max_digits=12, decimal_places=2, 
                                     default=Decimal('0.00'))
    max_purchase_quantity = models.PositiveIntegerField(default=0)
    min_purchase_quantity = models.PositiveIntegerField(default=1)
    minimum_age = models.PositiveIntegerField(default=0)
    
    # Location and Status
    pick_location = models.CharField(max_length=100, blank=True, null=True)
    stock_message = models.CharField(max_length=200, blank=True, null=True)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=3, 
                                   default=Decimal('0.000'))
    
    # Active Status
    child_active = models.BooleanField(default=True)
    parent_active = models.BooleanField(default=True)
    archive_delete = models.BooleanField(default=False)
    archive_redirect_url = models.URLField(blank=True, null=True)
    
    # URLs and Images
    parent_product_url = models.URLField(blank=True, null=True)
    child_product_url = models.URLField(blank=True, null=True)
    parent_product_images = models.URLField(blank=True, null=True)
    child_product_images = models.URLField(blank=True, null=True)
    
    # Additional flags
    display_on_sale_page = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    trade_only_product = models.BooleanField(default=False)
    
    # Soft delete fields
    is_deleted = models.BooleanField(default=False, help_text="Soft delete flag")
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="When the record was deleted")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Managers
    objects = BaseManager()
    all_objects = models.Manager()
    
    class Meta:
        db_table = 'products'
        ordering = ['vs_child_id']
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        indexes = [
            models.Index(fields=['vs_parent_id']),
            models.Index(fields=['parent_reference']),
            models.Index(fields=['child_reference']),
            models.Index(fields=['child_active']),
            models.Index(fields=['parent_active']),
        ]
    
    def __str__(self):
        return f"{self.child_reference} - {self.child_product_title}"
    
    @property
    def is_active(self):
        """Returns True if both parent and child are active"""
        return self.child_active and self.parent_active
    
    @property
    def effective_price(self):
        """Returns the effective selling price"""
        return self.rrp_price_inc_vat if self.rrp_price_inc_vat > 0 else self.cost_price_inc_vat
    
    def soft_delete(self):
        """Soft delete the product"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore soft deleted product"""
        self.is_deleted = False
        self.deleted_at = None
        self.save()
    
    def hard_delete(self):
        """Permanently delete the product"""
        super().delete()

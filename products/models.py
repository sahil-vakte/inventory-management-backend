
from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.db.models import Max
from stock.sku_utils import normalize_sku_reference
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
    available_on_this_website = models.BooleanField(blank=True, null=True)
    
    # Relations
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, blank=True, null=True)
    categories = models.ManyToManyField(Category, blank=True)
    # Location fields moved to StockItem
    
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

    # Sample request fields from the finalized product CSV.
    allow_sample_request = models.BooleanField(blank=True, null=True)
    sample_request_cost = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    
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
    parent_product_sash = models.CharField(max_length=200, blank=True, null=True)
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
    price_break_1_deposit_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    price_break_1_allow_further_discounts = models.BooleanField(blank=True, null=True)
    
    price_break_2_quantity = models.PositiveIntegerField(blank=True, null=True)
    price_break_2_price = models.DecimalField(max_digits=10, decimal_places=2, 
                                             blank=True, null=True)
    price_break_2_sale_price = models.DecimalField(max_digits=10, decimal_places=2, 
                                                  blank=True, null=True)
    price_break_2_deposit_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    price_break_2_allow_further_discounts = models.BooleanField(blank=True, null=True)
    
    price_break_3_quantity = models.PositiveIntegerField(blank=True, null=True)
    price_break_3_price = models.DecimalField(max_digits=10, decimal_places=2, 
                                             blank=True, null=True)
    price_break_3_sale_price = models.DecimalField(max_digits=10, decimal_places=2, 
                                                  blank=True, null=True)
    price_break_3_deposit_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    price_break_3_allow_further_discounts = models.BooleanField(blank=True, null=True)

    price_break_4_quantity = models.PositiveIntegerField(blank=True, null=True)
    price_break_4_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    price_break_4_sale_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    price_break_4_deposit_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    price_break_4_allow_further_discounts = models.BooleanField(blank=True, null=True)

    price_break_5_quantity = models.PositiveIntegerField(blank=True, null=True)
    price_break_5_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    price_break_5_sale_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    price_break_5_deposit_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    price_break_5_allow_further_discounts = models.BooleanField(blank=True, null=True)
    
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
    parent_product_images = models.TextField(blank=True, null=True)
    child_product_images = models.TextField(blank=True, null=True)
    meta_title = models.CharField(max_length=500, blank=True, null=True)
    meta_keywords = models.TextField(blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    
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

    def save(self, *args, **kwargs):
        self.parent_reference = normalize_sku_reference(self.parent_reference)[:50]
        self.child_reference = normalize_sku_reference(self.child_reference)[:50]
        super().save(*args, **kwargs)
    
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


class ProductExtendedData(models.Model):
    """Supplementary storage for every column in the full product backup CSV."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='extended_data',
        blank=True,
        null=True,
    )
    source_file_name = models.CharField(max_length=255)
    source_file_date = models.DateField(blank=True, null=True)
    row_number = models.PositiveIntegerField()
    row_hash = models.CharField(max_length=64, db_index=True)
    import_batch_id = models.CharField(max_length=100, db_index=True)

    vs_parent_id = models.TextField(db_column='VS Parent ID', blank=True, null=True)
    vs_child_id = models.TextField(db_column='VS Child ID', blank=True, null=True)
    blank_column_3 = models.TextField(db_column='blank_column_3', blank=True, null=True)
    parent_reference = models.TextField(db_column='Parent Reference', blank=True, null=True)
    child_reference = models.TextField(db_column='Child Reference', blank=True, null=True)
    blank_column_6 = models.TextField(db_column='blank_column_6', blank=True, null=True)
    available_on_this_website = models.TextField(db_column='Available On This Website', blank=True, null=True)
    blank_column_8 = models.TextField(db_column='blank_column_8', blank=True, null=True)
    parent_product_title = models.TextField(db_column='Parent Product Title', blank=True, null=True)
    child_product_title = models.TextField(db_column='Child Product Title', blank=True, null=True)
    product_subtitle = models.TextField(db_column='Product Subtitle', blank=True, null=True)
    product_summary = models.TextField(db_column='Product Summary', blank=True, null=True)
    product_description = models.TextField(db_column='Product Description', blank=True, null=True)
    blank_column_14 = models.TextField(db_column='blank_column_14', blank=True, null=True)
    brand = models.TextField(db_column='Brand', blank=True, null=True)
    blank_column_16 = models.TextField(db_column='blank_column_16', blank=True, null=True)
    categories = models.TextField(db_column='Categories', blank=True, null=True)
    blank_column_18 = models.TextField(db_column='blank_column_18', blank=True, null=True)
    attribute_1_length = models.TextField(db_column='Attribute 1 (Length)', blank=True, null=True)
    attribute_2_colour = models.TextField(db_column='Attribute 2 (Colour)', blank=True, null=True)
    attribute_3_top_sizes = models.TextField(db_column='Attribute 3 (Top Sizes)', blank=True, null=True)
    attribute_4_dress_sizes = models.TextField(db_column='Attribute 4 (Dress Sizes)', blank=True, null=True)
    attribute_5_design = models.TextField(db_column='Attribute 5 (Design)', blank=True, null=True)
    attribute_6_print = models.TextField(db_column='Attribute 6 (Print)', blank=True, null=True)
    attribute_7_weight = models.TextField(db_column='Attribute 7 (Weight)', blank=True, null=True)
    attribute_8_width = models.TextField(db_column='Attribute 8 (Width)', blank=True, null=True)
    attribute_9_size = models.TextField(db_column='Attribute 9 (Size)', blank=True, null=True)
    attribute_10_choose_type = models.TextField(db_column='Attribute 10 (Choose Type)', blank=True, null=True)
    attribute_11_gift_card_value = models.TextField(db_column='Attribute 11 (Gift Card Value)', blank=True, null=True)
    attribute_12_colours_pf = models.TextField(db_column='Attribute 12 (Colours PF)', blank=True, null=True)
    blank_column_31 = models.TextField(db_column='blank_column_31', blank=True, null=True)
    allow_sample_request = models.TextField(db_column='Allow Sample Request', blank=True, null=True)
    blank_column_33 = models.TextField(db_column='blank_column_33', blank=True, null=True)
    sample_request_cost = models.TextField(db_column='Sample Request Cost', blank=True, null=True)
    blank_column_35 = models.TextField(db_column='blank_column_35', blank=True, null=True)
    tag_13_sale = models.TextField(db_column='Tag 13 (Sale)', blank=True, null=True)
    tag_12_dressmaking_and_fashion = models.TextField(db_column='Tag 12 (Dressmaking & Fashion )', blank=True, null=True)
    tag_2_colours = models.TextField(db_column='Tag 2 (Colours)', blank=True, null=True)
    tag_8_matching_lycra_and_mesh = models.TextField(db_column='Tag 8 (Matching Lycra & Mesh )', blank=True, null=True)
    tag_3_material = models.TextField(db_column='Tag 3 (Material)', blank=True, null=True)
    tag_11_materials = models.TextField(db_column='Tag 11 (Materials)', blank=True, null=True)
    tag_1_print_texture = models.TextField(db_column='Tag 1 (Print/ Texture)', blank=True, null=True)
    tag_6_quantity_box = models.TextField(db_column='Tag 6 (Quantity Box)', blank=True, null=True)
    tag_4_trimmings = models.TextField(db_column='Tag 4 (Trimmings)', blank=True, null=True)
    blank_column_45 = models.TextField(db_column='blank_column_45', blank=True, null=True)
    parent_downloads = models.TextField(db_column='Parent Downloads', blank=True, null=True)
    parent_product_sash = models.TextField(db_column='Parent Product Sash', blank=True, null=True)
    child_product_sash = models.TextField(db_column='Child Product Sash', blank=True, null=True)
    blank_column_49 = models.TextField(db_column='blank_column_49', blank=True, null=True)
    model_number = models.TextField(db_column='Model Number', blank=True, null=True)
    ean = models.TextField(db_column='EAN', blank=True, null=True)
    mpn = models.TextField(db_column='MPN', blank=True, null=True)
    isbn = models.TextField(db_column='ISBN', blank=True, null=True)
    release_date = models.TextField(db_column='Release Date', blank=True, null=True)
    available_now = models.TextField(db_column='Available Now', blank=True, null=True)
    upc = models.TextField(db_column='UPC', blank=True, null=True)
    blank_column_57 = models.TextField(db_column='blank_column_57', blank=True, null=True)
    deposit_price_inc_vat = models.TextField(db_column='Deposit Price (Inc VAT)', blank=True, null=True)
    rrp_price_inc_vat = models.TextField(db_column='RRP Price (Inc VAT)', blank=True, null=True)
    cost_price_inc_vat = models.TextField(db_column='Cost Price (Inc VAT)', blank=True, null=True)
    vat_rate = models.TextField(db_column='VAT Rate', blank=True, null=True)
    display_on_sale_page = models.TextField(db_column='Display On Sale Page', blank=True, null=True)
    blank_column_63 = models.TextField(db_column='blank_column_63', blank=True, null=True)
    price_break_1_quantity = models.TextField(db_column='Price Break 1 (Quantity)', blank=True, null=True)
    price_break_1_price_inc_vat = models.TextField(db_column='Price Break 1 (Price Inc VAT)', blank=True, null=True)
    price_break_1_sale_price_inc_vat = models.TextField(db_column='Price Break 1 (Sale Price Inc VAT)', blank=True, null=True)
    price_break_1_deposit_price_inc_vat = models.TextField(db_column='Price Break 1 (Deposit Price Inc VAT)', blank=True, null=True)
    price_break_1_allow_further_discounts_inc_vat = models.TextField(db_column='Price Break 1 (Allow Further Discounts Inc VAT)', blank=True, null=True)
    price_break_2_quantity = models.TextField(db_column='Price Break 2 (Quantity)', blank=True, null=True)
    price_break_2_price_inc_vat = models.TextField(db_column='Price Break 2 (Price Inc VAT)', blank=True, null=True)
    price_break_2_sale_price_inc_vat = models.TextField(db_column='Price Break 2 (Sale Price Inc VAT)', blank=True, null=True)
    price_break_2_deposit_price_inc_vat = models.TextField(db_column='Price Break 2 (Deposit Price Inc VAT)', blank=True, null=True)
    price_break_2_allow_further_discounts_inc_vat = models.TextField(db_column='Price Break 2 (Allow Further Discounts Inc VAT)', blank=True, null=True)
    price_break_3_quantity = models.TextField(db_column='Price Break 3 (Quantity)', blank=True, null=True)
    price_break_3_price_inc_vat = models.TextField(db_column='Price Break 3 (Price Inc VAT)', blank=True, null=True)
    price_break_3_sale_price_inc_vat = models.TextField(db_column='Price Break 3 (Sale Price Inc VAT)', blank=True, null=True)
    price_break_3_deposit_price_inc_vat = models.TextField(db_column='Price Break 3 (Deposit Price Inc VAT)', blank=True, null=True)
    price_break_3_allow_further_discounts_inc_vat = models.TextField(db_column='Price Break 3 (Allow Further Discounts Inc VAT)', blank=True, null=True)
    price_break_4_quantity = models.TextField(db_column='Price Break 4 (Quantity)', blank=True, null=True)
    price_break_4_price_inc_vat = models.TextField(db_column='Price Break 4 (Price Inc VAT)', blank=True, null=True)
    price_break_4_sale_price_inc_vat = models.TextField(db_column='Price Break 4 (Sale Price Inc VAT)', blank=True, null=True)
    price_break_4_deposit_price_inc_vat = models.TextField(db_column='Price Break 4 (Deposit Price Inc VAT)', blank=True, null=True)
    price_break_4_allow_further_discounts_inc_vat = models.TextField(db_column='Price Break 4 (Allow Further Discounts Inc VAT)', blank=True, null=True)
    price_break_5_quantity = models.TextField(db_column='Price Break 5 (Quantity)', blank=True, null=True)
    price_break_5_price_inc_vat = models.TextField(db_column='Price Break 5 (Price Inc VAT)', blank=True, null=True)
    price_break_5_sale_price_inc_vat = models.TextField(db_column='Price Break 5 (Sale Price Inc VAT)', blank=True, null=True)
    price_break_5_deposit_price_inc_vat = models.TextField(db_column='Price Break 5 (Deposit Price Inc VAT)', blank=True, null=True)
    price_break_5_allow_further_discounts_inc_vat = models.TextField(db_column='Price Break 5 (Allow Further Discounts Inc VAT)', blank=True, null=True)
    blank_column_89 = models.TextField(db_column='blank_column_89', blank=True, null=True)
    stock_value = models.TextField(db_column='Stock Value', blank=True, null=True)
    max_purchase_quantity = models.TextField(db_column='Max Purchase Quantity', blank=True, null=True)
    min_purchase_quantity = models.TextField(db_column='Min Purchase Quantity', blank=True, null=True)
    minimum_age = models.TextField(db_column='Minimum Age', blank=True, null=True)
    pick_location = models.TextField(db_column='Pick Location', blank=True, null=True)
    stock_message = models.TextField(db_column='Stock Message', blank=True, null=True)
    weight_in_kgs = models.TextField(db_column='Weight (in KGs)', blank=True, null=True)
    child_active = models.TextField(db_column='Child Active', blank=True, null=True)
    parent_active = models.TextField(db_column='Parent Active', blank=True, null=True)
    archive_delete = models.TextField(db_column='Archive (Delete)', blank=True, null=True)
    archive_redirect_url = models.TextField(db_column='Archive Redirect URL', blank=True, null=True)
    date_added = models.TextField(db_column='Date Added', blank=True, null=True)
    parent_product_url = models.TextField(db_column='Parent Product Url', blank=True, null=True)
    child_product_url = models.TextField(db_column='Child Product Url', blank=True, null=True)
    blank_column_104 = models.TextField(db_column='blank_column_104', blank=True, null=True)
    parent_product_images = models.TextField(db_column='Parent Product Images', blank=True, null=True)
    child_product_images = models.TextField(db_column='Child Product Images', blank=True, null=True)
    blank_column_107 = models.TextField(db_column='blank_column_107', blank=True, null=True)
    meta_title = models.TextField(db_column='Meta Title', blank=True, null=True)
    meta_keywords = models.TextField(db_column='Meta Keywords', blank=True, null=True)
    meta_description = models.TextField(db_column='Meta Description', blank=True, null=True)
    blank_column_111 = models.TextField(db_column='blank_column_111', blank=True, null=True)
    personalisation_1_custom_cutting = models.TextField(db_column='Personalisation 1 (Custom Cutting)', blank=True, null=True)
    personalisation_2_matching_power_mesh = models.TextField(db_column='Personalisation 2 (Matching Power Mesh )', blank=True, null=True)
    blank_column_114 = models.TextField(db_column='blank_column_114', blank=True, null=True)
    upselling_1_you_may_also_like = models.TextField(db_column='Upselling 1 (You May Also Like)', blank=True, null=True)
    upselling_2_other_colours = models.TextField(db_column='Upselling 2 (Other Colours)', blank=True, null=True)
    upselling_3_related_products = models.TextField(db_column='Upselling 3 (Related Products)', blank=True, null=True)
    blank_column_118 = models.TextField(db_column='blank_column_118', blank=True, null=True)
    amazon_active_uk = models.TextField(db_column='Amazon Active (UK)', blank=True, null=True)
    amazon_sku_uk = models.TextField(db_column='Amazon SKU (UK)', blank=True, null=True)
    amazon_live_uk = models.TextField(db_column='Amazon Live (UK)', blank=True, null=True)
    amazon_title_uk = models.TextField(db_column='Amazon Title (UK)', blank=True, null=True)
    amazon_description_uk = models.TextField(db_column='Amazon Description (UK)', blank=True, null=True)
    amazon_selling_price_uk = models.TextField(db_column='Amazon Selling Price (UK)', blank=True, null=True)
    amazon_price_sync_uk = models.TextField(db_column='Amazon Price Sync (UK)', blank=True, null=True)
    amazon_prime_template_id_uk = models.TextField(db_column='Amazon Prime Template ID (UK)', blank=True, null=True)
    amazon_barcode_uk = models.TextField(db_column='Amazon Barcode (UK)', blank=True, null=True)
    amazon_product_type_uk = models.TextField(db_column='Amazon Product Type (UK)', blank=True, null=True)
    amazon_category_uk = models.TextField(db_column='Amazon Category (UK)', blank=True, null=True)
    amazon_brand_uk = models.TextField(db_column='Amazon Brand (UK)', blank=True, null=True)
    amazon_search_terms_uk = models.TextField(db_column='Amazon Search Terms (UK)', blank=True, null=True)
    amazon_barcode_type_uk = models.TextField(db_column='Amazon Barcode Type (UK)', blank=True, null=True)
    amazon_handling_time_uk = models.TextField(db_column='Amazon Handling Time (UK)', blank=True, null=True)
    amazon_asin_uk = models.TextField(db_column='Amazon ASIN (UK)', blank=True, null=True)
    blank_column_135 = models.TextField(db_column='blank_column_135', blank=True, null=True)
    featured = models.TextField(db_column='Featured', blank=True, null=True)
    blank_column_137 = models.TextField(db_column='blank_column_137', blank=True, null=True)
    courier_blacklist = models.TextField(db_column='Courier Blacklist', blank=True, null=True)
    blank_column_139 = models.TextField(db_column='blank_column_139', blank=True, null=True)
    courier_whitelist = models.TextField(db_column='Courier Whitelist', blank=True, null=True)
    blank_column_141 = models.TextField(db_column='blank_column_141', blank=True, null=True)
    trade_only_product = models.TextField(db_column='Trade Only Product', blank=True, null=True)
    blank_column_143 = models.TextField(db_column='blank_column_143', blank=True, null=True)
    parent_commodity_code = models.TextField(db_column='Parent Commodity Code', blank=True, null=True)
    parent_country_of_origin = models.TextField(db_column='Parent Country Of Origin', blank=True, null=True)
    blank_column_146 = models.TextField(db_column='blank_column_146', blank=True, null=True)
    child_commodity_code = models.TextField(db_column='Child Commodity Code', blank=True, null=True)
    child_country_of_origin = models.TextField(db_column='Child Country Of Origin', blank=True, null=True)
    child_customs_description = models.TextField(db_column='Child Customs Description', blank=True, null=True)
    blank_column_150 = models.TextField(db_column='blank_column_150', blank=True, null=True)

    raw_data = models.JSONField(blank=True, null=True)
    raw_headers = models.JSONField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'product_extended_data'
        ordering = ['source_file_name', 'row_number']
        indexes = [
            models.Index(fields=['source_file_name', 'row_number']),
            models.Index(fields=['import_batch_id']),
            models.Index(fields=['row_hash']),
            models.Index(fields=['product']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['source_file_name', 'row_number', 'import_batch_id'],
                name='unique_product_extended_import_row',
            )
        ]

    def __str__(self):
        return f"{self.source_file_name} row {self.row_number}"

    def save(self, *args, **kwargs):
        self.parent_reference = normalize_sku_reference(self.parent_reference)
        self.child_reference = normalize_sku_reference(self.child_reference)
        self.amazon_sku_uk = normalize_sku_reference(self.amazon_sku_uk)
        super().save(*args, **kwargs)

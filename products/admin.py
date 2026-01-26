from django.contrib import admin
from .models import Product, Category, Brand, Location
@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'description', 'created_at', 'updated_at']
    search_fields = ['id', 'name']
    ordering = ['id']

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_deleted', 'created_at']
    list_filter = ['is_deleted', 'created_at']
    search_fields = ['name']
    ordering = ['name']
    readonly_fields = ['created_at', 'deleted_at']
    
    def get_queryset(self, request):
        """Override to show all objects including deleted ones in admin"""
        return Brand.all_objects.all()
    
    actions = ['soft_delete_selected', 'restore_selected']
    
    def soft_delete_selected(self, request, queryset):
        count = 0
        for obj in queryset.filter(is_deleted=False):
            obj.soft_delete()
            count += 1
        self.message_user(request, f'{count} brands were soft deleted.')
    soft_delete_selected.short_description = "Soft delete selected brands"
    
    def restore_selected(self, request, queryset):
        count = 0
        for obj in queryset.filter(is_deleted=True):
            obj.restore()
            count += 1
        self.message_user(request, f'{count} brands were restored.')
    restore_selected.short_description = "Restore selected brands"

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'is_deleted', 'created_at']
    list_filter = ['parent', 'is_deleted', 'created_at']
    search_fields = ['name']
    ordering = ['name']
    readonly_fields = ['created_at', 'deleted_at']
    
    def get_queryset(self, request):
        """Override to show all objects including deleted ones in admin"""
        return Category.all_objects.all()
    
    actions = ['soft_delete_selected', 'restore_selected']
    
    def soft_delete_selected(self, request, queryset):
        count = 0
        for obj in queryset.filter(is_deleted=False):
            obj.soft_delete()
            count += 1
        self.message_user(request, f'{count} categories were soft deleted.')
    soft_delete_selected.short_description = "Soft delete selected categories"
    
    def restore_selected(self, request, queryset):
        count = 0
        for obj in queryset.filter(is_deleted=True):
            obj.restore()
            count += 1
        self.message_user(request, f'{count} categories were restored.')
    restore_selected.short_description = "Restore selected categories"

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'vs_child_id', 'location','child_reference', 'child_product_title', 
        'brand', 'rrp_price_inc_vat', 'child_active', 'parent_active', 'is_deleted'
    ]
    list_filter = [
        'brand', 'child_active', 'parent_active', 'featured', 
        'display_on_sale_page', 'is_deleted', 'created_at'
    ]
    search_fields = [
        'vs_child_id', 'child_reference', 'parent_reference',
        'child_product_title', 'parent_product_title'
    ]
    filter_horizontal = ['categories']
    ordering = ['vs_child_id']
    readonly_fields = ['created_at', 'updated_at', 'deleted_at']
    
    def get_queryset(self, request):
        """Override to show all objects including deleted ones in admin"""
        return Product.all_objects.all()
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'vs_parent_id', 'vs_child_id', 'parent_reference', 'child_reference'
            )
        }),
        ('Product Location', {
            'fields': (
                'location',
            )
        }),
        ('Product Details', {
            'fields': (
                'parent_product_title', 'child_product_title', 'product_subtitle',
                'product_summary', 'product_description', 'brand', 'categories'
            )
        }),
        ('Attributes', {
            'fields': (
                'attribute_colour', 'attribute_length', 'attribute_size',
                'attribute_weight', 'attribute_width'
            ),
            'classes': ['collapse']
        }),
        ('Pricing', {
            'fields': (
                'rrp_price_inc_vat', 'cost_price_inc_vat', 'deposit_price_inc_vat',
                'vat_rate'
            )
        }),
        ('Stock & Purchase', {
            'fields': (
                'stock_value', 'min_purchase_quantity', 'max_purchase_quantity',
                'weight_kg'
            )
        }),
        ('Status', {
            'fields': (
                'child_active', 'parent_active', 'featured', 'display_on_sale_page',
                'trade_only_product', 'is_deleted'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'deleted_at'),
            'classes': ['collapse']
        })
    )
    
    actions = ['soft_delete_selected', 'restore_selected']
    
    def soft_delete_selected(self, request, queryset):
        count = 0
        for obj in queryset.filter(is_deleted=False):
            obj.soft_delete()
            count += 1
        self.message_user(request, f'{count} products were soft deleted.')
    soft_delete_selected.short_description = "Soft delete selected products"
    
    def restore_selected(self, request, queryset):
        count = 0
        for obj in queryset.filter(is_deleted=True):
            obj.restore()
            count += 1
        self.message_user(request, f'{count} products were restored.')
    restore_selected.short_description = "Restore selected products"

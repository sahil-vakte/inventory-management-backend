from django.contrib import admin
from .models import StockItem, StockMovement

@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = [
        'sku', 'product_type', 'product', 'color', 'available_stock_rolls',
        'reserved_stock', 'stock_status', 'is_active', 'is_deleted'
    ]
    list_filter = [
        'product_type', 'product', 'color', 'is_active', 'is_discontinued',
        'warehouse_location', 'supplier', 'is_deleted'
    ]
    search_fields = ['sku', 'product_type', 'color__color_name', 'supplier']
    ordering = ['sku']
    readonly_fields = ['created_at', 'updated_at', 'deleted_at', 'last_stock_update', 'stock_status']
    raw_id_fields = ('product',)
    
    def get_queryset(self, request):
        """Override to show all objects including deleted ones in admin"""
        return StockItem.all_objects.all()
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('sku', 'product_type', 'product', 'color')
        }),
        ('Stock Levels', {
            'fields': (
                'available_stock_rolls', 'reserved_stock',
                'minimum_stock_level', 'maximum_stock_level'
            )
        }),
        ('Location & Supplier', {
            'fields': ('warehouse_location', 'supplier', 'lead_time_days')
        }),
        ('Costs', {
            'fields': ('unit_cost', 'last_purchase_price', 'last_purchase_date')
        }),
        ('Status', {
            'fields': ('is_active', 'is_discontinued', 'is_deleted', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'last_stock_update'),
            'classes': ['collapse']
        })
    )
    
    actions = ['soft_delete_selected', 'restore_selected', 'hard_delete_selected']
    
    def soft_delete_selected(self, request, queryset):
        count = 0
        for obj in queryset.filter(is_deleted=False):
            obj.soft_delete()
            count += 1
        self.message_user(request, f'{count} stock items were soft deleted.')
    soft_delete_selected.short_description = "Soft delete selected stock items"
    
    def restore_selected(self, request, queryset):
        count = 0
        for obj in queryset.filter(is_deleted=True):
            obj.restore()
            count += 1
        self.message_user(request, f'{count} stock items were restored.')
    restore_selected.short_description = "Restore selected stock items"
    
    def hard_delete_selected(self, request, queryset):
        count = 0
        for obj in queryset.filter(is_deleted=True):
            obj.hard_delete()
            count += 1
        self.message_user(request, f'{count} stock items were permanently deleted.')
    hard_delete_selected.short_description = "Hard delete selected stock items (PERMANENT)"

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        'stock_item', 'movement_type', 'quantity',
        'old_stock_level', 'new_stock_level', 'created_at', 'is_deleted'
    ]
    list_filter = ['movement_type', 'created_at', 'is_deleted']
    search_fields = ['stock_item__sku', 'reference_number', 'reason']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'deleted_at']
    
    def get_queryset(self, request):
        """Override to show all objects including deleted ones in admin"""
        return StockMovement.all_objects.all()
    
    actions = ['soft_delete_selected', 'restore_selected', 'hard_delete_selected']
    
    def soft_delete_selected(self, request, queryset):
        count = 0
        for obj in queryset.filter(is_deleted=False):
            obj.soft_delete()
            count += 1
        self.message_user(request, f'{count} stock movements were soft deleted.')
    soft_delete_selected.short_description = "Soft delete selected stock movements"
    
    def restore_selected(self, request, queryset):
        count = 0
        for obj in queryset.filter(is_deleted=True):
            obj.restore()
            count += 1
        self.message_user(request, f'{count} stock movements were restored.')
    restore_selected.short_description = "Restore selected stock movements"
    
    def hard_delete_selected(self, request, queryset):
        count = 0
        for obj in queryset.filter(is_deleted=True):
            obj.hard_delete()
            count += 1
        self.message_user(request, f'{count} stock movements were permanently deleted.')
    hard_delete_selected.short_description = "Hard delete selected stock movements (PERMANENT)"

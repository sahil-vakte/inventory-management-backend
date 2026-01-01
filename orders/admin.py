from django.contrib import admin
from django.utils.html import format_html
from .models import Order, OrderItem, OrderStatusHistory


class OrderItemInline(admin.TabularInline):
    """Inline admin for order items"""
    model = OrderItem
    extra = 1
    fields = [
        'sku', 'product_name', 'quantity', 'unit_price', 
        'line_total', 'stock_reserved', 'stock_fulfilled'
    ]
    readonly_fields = ['line_total']


class OrderStatusHistoryInline(admin.TabularInline):
    """Inline admin for order status history"""
    model = OrderStatusHistory
    extra = 0
    fields = ['from_status', 'to_status', 'changed_by', 'change_reason', 'timestamp']
    readonly_fields = ['timestamp']
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin interface for Order model"""
    
    list_display = [
        'order_number', 'customer_name', 'order_status_badge', 
        'payment_status_badge', 'total_amount', 'order_date', 
        'item_count', 'is_deleted'
    ]
    list_filter = [
        'order_status', 'payment_status', 'order_source', 
        'is_deleted', 'order_date', 'created_at'
    ]
    search_fields = [
        'order_number', 'external_order_id', 'customer_name', 
        'customer_email', 'customer_phone', 'tracking_number'
    ]
    readonly_fields = [
        'order_number', 'created_at', 'updated_at', 'created_by', 
        'updated_by', 'deleted_at', 'deleted_by', 'item_count', 
        'total_quantity', 'is_paid'
    ]
    
    fieldsets = (
        ('Order Information', {
            'fields': (
                'order_number', 'external_order_id', 'order_status', 
                'payment_status', 'order_source'
            )
        }),
        ('Customer Information', {
            'fields': (
                'customer_name', 'customer_email', 'customer_phone', 'customer_company'
            )
        }),
        ('Shipping Address', {
            'fields': (
                'shipping_address_line1', 'shipping_address_line2', 
                'shipping_city', 'shipping_state', 'shipping_postal_code', 'shipping_country'
            )
        }),
        ('Billing Address', {
            'fields': (
                'billing_address_line1', 'billing_address_line2', 
                'billing_city', 'billing_state', 'billing_postal_code', 'billing_country'
            ),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': (
                'order_date', 'confirmed_date', 'shipped_date', 
                'delivered_date', 'expected_delivery_date'
            )
        }),
        ('Financial Information', {
            'fields': (
                'subtotal', 'tax_amount', 'tax_rate', 'shipping_cost', 
                'discount_amount', 'total_amount'
            )
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'payment_reference')
        }),
        ('Shipping Information', {
            'fields': ('shipping_method', 'tracking_number', 'carrier')
        }),
        ('Notes', {
            'fields': ('customer_notes', 'internal_notes'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': (
                'created_at', 'created_by', 'updated_at', 'updated_by',
                'is_deleted', 'deleted_at', 'deleted_by'
            ),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('item_count', 'total_quantity', 'is_paid'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    
    actions = ['confirm_orders', 'cancel_orders', 'mark_as_shipped', 'soft_delete_orders', 'restore_orders']
    
    def order_status_badge(self, obj):
        """Display order status with color badge"""
        colors = {
            'PENDING': '#FFA500',
            'CONFIRMED': '#4CAF50',
            'PROCESSING': '#2196F3',
            'SHIPPED': '#9C27B0',
            'DELIVERED': '#4CAF50',
            'CANCELLED': '#F44336',
            'ON_HOLD': '#FF9800',
        }
        color = colors.get(obj.order_status, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_order_status_display()
        )
    order_status_badge.short_description = 'Status'
    
    def payment_status_badge(self, obj):
        """Display payment status with color badge"""
        colors = {
            'UNPAID': '#F44336',
            'PARTIAL': '#FF9800',
            'PAID': '#4CAF50',
            'REFUNDED': '#9C27B0',
            'FAILED': '#F44336',
        }
        color = colors.get(obj.payment_status, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Payment'
    
    def confirm_orders(self, request, queryset):
        """Bulk confirm orders"""
        count = 0
        for order in queryset:
            try:
                order.confirm(user=request.user)
                count += 1
            except ValueError:
                pass
        self.message_user(request, f'{count} orders confirmed.')
    confirm_orders.short_description = 'Confirm selected orders'
    
    def cancel_orders(self, request, queryset):
        """Bulk cancel orders"""
        count = 0
        for order in queryset:
            try:
                order.cancel(reason='Bulk cancellation by admin', user=request.user)
                count += 1
            except ValueError:
                pass
        self.message_user(request, f'{count} orders cancelled.')
    cancel_orders.short_description = 'Cancel selected orders'
    
    def mark_as_shipped(self, request, queryset):
        """Bulk mark as shipped"""
        count = 0
        for order in queryset:
            try:
                order.mark_shipped(user=request.user)
                count += 1
            except ValueError:
                pass
        self.message_user(request, f'{count} orders marked as shipped.')
    mark_as_shipped.short_description = 'Mark as shipped'
    
    def soft_delete_orders(self, request, queryset):
        """Soft delete selected orders"""
        count = 0
        for order in queryset.filter(is_deleted=False):
            order.soft_delete(user=request.user)
            count += 1
        self.message_user(request, f'{count} orders soft deleted.')
    soft_delete_orders.short_description = 'Soft delete selected orders'
    
    def restore_orders(self, request, queryset):
        """Restore soft deleted orders"""
        count = 0
        for order in queryset.filter(is_deleted=True):
            order.restore()
            count += 1
        self.message_user(request, f'{count} orders restored.')
    restore_orders.short_description = 'Restore selected orders'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """Admin interface for OrderItem model"""
    
    list_display = [
        'id', 'order_link', 'sku', 'product_name', 'quantity', 
        'unit_price', 'line_total', 'stock_reserved', 'stock_fulfilled'
    ]
    list_filter = ['stock_reserved', 'stock_fulfilled', 'created_at']
    search_fields = ['sku', 'product_name', 'order__order_number']
    readonly_fields = ['line_total', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Order Reference', {
            'fields': ('order',)
        }),
        ('Product Information', {
            'fields': (
                'product', 'stock_item', 'sku', 'product_name', 
                'product_type', 'color_code'
            )
        }),
        ('Pricing', {
            'fields': (
                'quantity', 'unit_price', 'line_total', 
                'tax_rate', 'discount_amount'
            )
        }),
        ('Status', {
            'fields': ('stock_reserved', 'stock_fulfilled', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def order_link(self, obj):
        """Display clickable link to order"""
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = 'Order'


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    """Admin interface for OrderStatusHistory model"""
    
    list_display = [
        'id', 'order_link', 'from_status', 'to_status', 
        'changed_by', 'timestamp'
    ]
    list_filter = ['from_status', 'to_status', 'timestamp']
    search_fields = ['order__order_number', 'change_reason']
    readonly_fields = ['timestamp']
    
    fieldsets = (
        ('Order Reference', {
            'fields': ('order',)
        }),
        ('Status Change', {
            'fields': ('from_status', 'to_status', 'changed_by')
        }),
        ('Details', {
            'fields': ('change_reason', 'notes', 'timestamp')
        }),
    )
    
    def order_link(self, obj):
        """Display clickable link to order"""
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = 'Order'
    
    def has_add_permission(self, request):
        """Prevent manual creation of status history"""
        return False

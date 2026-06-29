from rest_framework import serializers
from django.contrib.auth.models import User
from decimal import Decimal
from .models import Order, OrderItem, OrderStatusHistory
from stock.serializers import StockItemListSerializer
from stock.sku_utils import normalize_sku_reference
from products.serializers import get_product_child_product_url


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for Order Items"""
    
    stock_detail = StockItemListSerializer(source='stock_item', read_only=True)
    assigned_to_username = serializers.SerializerMethodField()
    processing_status_display = serializers.CharField(source='get_processing_status_display', read_only=True)
    parent_product_images = serializers.SerializerMethodField()
    child_product_url = serializers.SerializerMethodField()
    available_stock_in_mtr = serializers.IntegerField(source='stock_item.available_stock_in_mtr', read_only=True)

    def get_assigned_to_username(self, obj):
        if obj.assigned_to_id:
            return obj.assigned_to.username
        return None

    def get_parent_product_images(self, obj):
        stock_item = getattr(obj, 'stock_item', None)
        return getattr(getattr(stock_item, 'product', None), 'parent_product_images', None)

    def get_child_product_url(self, obj):
        stock_item = getattr(obj, 'stock_item', None)
        return get_product_child_product_url(getattr(stock_item, 'product', None))
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'order', 'stock_item', 'stock_detail',
            'sku', 'product_name', 'product_type', 'color_code',
            'parent_product_images', 'child_product_url', 'available_stock_in_mtr',
            'quantity', 'quantity_ordered', 'quantity_processed',
            'unit_price', 'line_total', 'tax_rate', 'discount_amount',
            'lable_printed',
            'assigned_to', 'assigned_to_username',
            'processing_status', 'processing_status_display',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'line_total', 'created_at', 'updated_at']

    # Removed product location methods
    
    def validate_quantity(self, value):
        """Validate quantity is positive"""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value


class OrderItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating order items"""
    
    class Meta:
        model = OrderItem
        fields = [
            'stock_item', 'sku', 'product_name', 
            'product_type', 'color_code', 'quantity', 'unit_price', 
            'tax_rate', 'discount_amount', 'lable_printed', 'notes'
        ]
    
    def validate(self, data):
        """Auto-populate fields from stock_item if not provided"""
        stock_item = data.get('stock_item')
        # Auto-populate from stock_item if provided and fields are missing
        if stock_item:
            if not data.get('sku'):
                data['sku'] = stock_item.sku
            if not data.get('product_type'):
                data['product_type'] = stock_item.product_type
            if not data.get('color_code'):
                data['color_code'] = stock_item.color.color_code
            if not data.get('unit_price'):
                data['unit_price'] = stock_item.unit_cost
            if not data.get('product_name'):
                data['product_name'] = f"{stock_item.product_type} - {stock_item.color.color_name}"
        # Ensure required fields are present
        if not data.get('sku'):
            raise serializers.ValidationError("SKU is required")
        data['sku'] = normalize_sku_reference(data['sku'])[:50]
        if data.get('product_type'):
            data['product_type'] = normalize_sku_reference(data['product_type'])[:50]
        if not data.get('product_name'):
            raise serializers.ValidationError("Product name is required")
        if not data.get('unit_price'):
            raise serializers.ValidationError("Unit price is required")
        
        return data


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    """Serializer for Order Status History"""
    
    changed_by_username = serializers.CharField(source='changed_by.username', read_only=True)
    from_status_display = serializers.CharField(source='get_from_status_display', read_only=True)
    to_status_display = serializers.CharField(source='get_to_status_display', read_only=True)
    
    class Meta:
        model = OrderStatusHistory
        fields = [
            'id', 'order', 'from_status', 'to_status', 
            'from_status_display', 'to_status_display',
            'changed_by', 'changed_by_username', 'change_reason', 'notes', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']


class OrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing orders"""
    
    order_status_display = serializers.CharField(source='get_order_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    total_quantity = serializers.IntegerField(read_only=True)
    completion_percentage = serializers.SerializerMethodField()
    items_total = serializers.SerializerMethodField()
    items_completed = serializers.SerializerMethodField()
    items_assigned = serializers.SerializerMethodField()
    items_pending = serializers.SerializerMethodField()

    def get_completion_percentage(self, obj):
        return obj.get_completion_percentage()

    def get_items_total(self, obj):
        return obj.items.count()

    def get_items_completed(self, obj):
        return obj.items.filter(processing_status__in=[
            OrderItem.ITEM_STATUS_PICKED,
            OrderItem.ITEM_STATUS_COMPLETED,
        ]).count()

    def get_items_assigned(self, obj):
        return obj.items.filter(assigned_to__isnull=False).count()

    def get_items_pending(self, obj):
        return obj.items.filter(processing_status=OrderItem.ITEM_STATUS_PENDING).count()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'external_order_id', 'customer_name', 
            'customer_email', 'order_status', 'order_status_display',
            'payment_status', 'payment_status_display', 'order_date',
            'total_amount', 'item_count', 'total_quantity',
            'shipping_method', 'carrier', 'courier_service_name', 'courier_service_code',
            'created_by_username', 'assigned_to', 'assigned_to_username',
            'order_source', 'created_at',
            'completion_percentage', 'items_total', 'items_completed',
            'items_assigned', 'items_pending',
        ]
        read_only_fields = ['id', 'order_number', 'created_at']


class OrderListWithItemsSerializer(OrderListSerializer):
    """Order list serializer that includes nested order items"""

    items = OrderItemSerializer(many=True, read_only=True)

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + ['items']


class OrderDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for retrieving full order information"""
    
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    
    order_status_display = serializers.CharField(source='get_order_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_username = serializers.CharField(source='updated_by.username', read_only=True)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True)
    
    item_count = serializers.IntegerField(read_only=True)
    total_quantity = serializers.IntegerField(read_only=True)
    is_paid = serializers.BooleanField(read_only=True)
    shipping_address = serializers.CharField(read_only=True)
    billing_address = serializers.CharField(read_only=True)
    completion_percentage = serializers.SerializerMethodField()
    items_total = serializers.SerializerMethodField()
    items_completed = serializers.SerializerMethodField()
    items_assigned = serializers.SerializerMethodField()
    items_pending = serializers.SerializerMethodField()

    def get_completion_percentage(self, obj):
        return obj.get_completion_percentage()

    def get_items_total(self, obj):
        return obj.items.count()

    def get_items_completed(self, obj):
        return obj.items.filter(processing_status__in=[
            OrderItem.ITEM_STATUS_PICKED,
            OrderItem.ITEM_STATUS_COMPLETED,
        ]).count()

    def get_items_assigned(self, obj):
        return obj.items.filter(assigned_to__isnull=False).count()

    def get_items_pending(self, obj):
        return obj.items.filter(processing_status=OrderItem.ITEM_STATUS_PENDING).count()
    
    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = [
            'id', 'order_number', 'created_by', 'updated_by', 'deleted_by',
            'created_at', 'updated_at', 'deleted_at', 'is_deleted'
        ]


class OrderCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating orders"""
    
    items = OrderItemCreateSerializer(many=True, required=False)
    
    class Meta:
        model = Order
        fields = [
            'external_order_id', 'customer_name', 'customer_email', 
            'customer_phone', 'customer_company',
            'shipping_address_line1', 'shipping_address_line2', 
            'shipping_city', 'shipping_state', 'shipping_postal_code', 'shipping_country',
            'billing_address_line1', 'billing_address_line2',
            'billing_city', 'billing_state', 'billing_postal_code', 'billing_country',
            'order_status', 'payment_status', 'order_date', 'expected_delivery_date',
            'subtotal', 'tax_amount', 'tax_rate', 'shipping_cost', 'discount_amount', 'total_amount',
            'payment_method', 'payment_reference', 'shipping_method',
            'carrier', 'courier_service_name', 'courier_service_code',
            'customer_notes', 'internal_notes', 'order_source', 'assigned_to', 'items'
        ]
    
    def validate_customer_name(self, value):
        """Validate customer name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Customer name is required")
        return value
    
    def create(self, validated_data):
        """Create order with items"""
        items_data = validated_data.pop('items', [])
        
        # Get user from context
        user = self.context['request'].user if 'request' in self.context else None
        if user and user.is_authenticated:
            validated_data['created_by'] = user
        
        # Create order
        order = Order.objects.create(**validated_data)
        
        # Create order items
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        
        # Recalculate totals
        order.calculate_totals()
        order.save()
        
        return order
    
    def update(self, instance, validated_data):
        """Update order"""
        items_data = validated_data.pop('items', None)
        
        # Get user from context
        user = self.context['request'].user if 'request' in self.context else None
        if user and user.is_authenticated:
            instance.updated_by = user
        
        # Update order fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Update items if provided
        if items_data is not None:
            # Remove old items
            instance.items.all().delete()
            
            # Create new items
            for item_data in items_data:
                OrderItem.objects.create(order=instance, **item_data)
            
            # Recalculate totals
            instance.calculate_totals()
            instance.save()
        
        return instance


class OrderConfirmSerializer(serializers.Serializer):
    """Serializer for marking an order label as printed"""
    notes = serializers.CharField(required=False, allow_blank=True)


class OrderShipSerializer(serializers.Serializer):
    """Serializer for shipping an order"""
    tracking_number = serializers.CharField(required=False, allow_blank=True)
    carrier = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class RoyalMailShipmentSerializer(serializers.Serializer):
    """Serializer for booking shipment through Royal Mail Click & Drop."""
    weight_in_grams = serializers.IntegerField(required=False, min_value=1)
    package_format_identifier = serializers.CharField(required=False, allow_blank=True)
    service_code = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class OrderCancelSerializer(serializers.Serializer):
    """Serializer for cancelling an order"""
    reason = serializers.CharField(required=True)


class OrderStatsSerializer(serializers.Serializer):
    """Serializer for order statistics"""
    total_orders = serializers.IntegerField()
    new_orders = serializers.IntegerField()
    label_printed_orders = serializers.IntegerField()
    in_progress_orders = serializers.IntegerField()
    completed_orders = serializers.IntegerField()
    shipped_orders = serializers.IntegerField()
    cancelled_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_order_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    unpaid_orders_count = serializers.IntegerField()
    unpaid_orders_value = serializers.DecimalField(max_digits=12, decimal_places=2)

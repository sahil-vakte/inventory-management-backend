from rest_framework import serializers
from django.contrib.auth.models import User
from decimal import Decimal
from .models import Order, OrderItem, OrderStatusHistory
from products.serializers import ProductListSerializer
from stock.serializers import StockItemListSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for Order Items"""
    
    product_detail = ProductListSerializer(source='product', read_only=True)
    product_location = serializers.SerializerMethodField(read_only=True)
    stock_detail = StockItemListSerializer(source='stock_item', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'order', 'product', 'stock_item', 'product_detail', 'stock_detail',
            'sku', 'product_name', 'product_type', 'color_code',
            'quantity', 'unit_price', 'line_total', 'tax_rate', 'discount_amount',
            'notes', 'created_at', 'updated_at',
            'product_location'
        ]
        read_only_fields = ['id', 'line_total', 'created_at', 'updated_at', 'product_location']

    def get_product_location(self, obj):
        # Always fetch location from the related product, even if not set on order item
        product = obj.product
        if product and product.location:
            return {
                'id': product.location.id,
                'name': product.location.name,
                'description': product.location.description,
            }
        # If product is not set, try to find by SKU (child_reference)
        from products.models import Product
        if not product and obj.sku:
            try:
                product = Product.objects.get(child_reference=obj.sku)
                if product.location:
                    return {
                        'id': product.location.id,
                        'name': product.location.name,
                        'description': product.location.description,
                    }
            except Product.DoesNotExist:
                pass
        # If still not found, try to find by product_name (child_product_title)
        if not product and obj.product_name:
            try:
                product = Product.objects.filter(child_product_title=obj.product_name).first()
                if product and product.location:
                    return {
                        'id': product.location.id,
                        'name': product.location.name,
                        'description': product.location.description,
                    }
            except Exception:
                pass
        return None
    
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
            'product', 'stock_item', 'sku', 'product_name', 
            'product_type', 'color_code', 'quantity', 'unit_price', 
            'tax_rate', 'discount_amount', 'notes'
        ]
    
    def validate(self, data):
        """Auto-populate fields from product or stock_item if not provided"""
        product = data.get('product')
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
        
        # Auto-populate from product if provided and fields are missing
        elif product:
            if not data.get('sku'):
                data['sku'] = f"PROD-{product.vs_child_id}"
            if not data.get('product_name'):
                data['product_name'] = product.child_product_title
            if not data.get('unit_price'):
                data['unit_price'] = product.rrp_price_inc_vat
        
        # Ensure required fields are present
        if not data.get('sku'):
            raise serializers.ValidationError("SKU is required")
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
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'external_order_id', 'customer_name', 
            'customer_email', 'order_status', 'order_status_display',
            'payment_status', 'payment_status_display', 'order_date',
            'total_amount', 'item_count', 'total_quantity',
            'created_by_username', 'assigned_to', 'assigned_to_username',
            'order_source', 'created_at'
        ]
        read_only_fields = ['id', 'order_number', 'created_at']


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
    """Serializer for confirming an order"""
    notes = serializers.CharField(required=False, allow_blank=True)


class OrderShipSerializer(serializers.Serializer):
    """Serializer for shipping an order"""
    tracking_number = serializers.CharField(required=False, allow_blank=True)
    carrier = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class OrderCancelSerializer(serializers.Serializer):
    """Serializer for cancelling an order"""
    reason = serializers.CharField(required=True)


class OrderStatsSerializer(serializers.Serializer):
    """Serializer for order statistics"""
    total_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    confirmed_orders = serializers.IntegerField()
    processing_orders = serializers.IntegerField()
    shipped_orders = serializers.IntegerField()
    delivered_orders = serializers.IntegerField()
    cancelled_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_order_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    unpaid_orders_count = serializers.IntegerField()
    unpaid_orders_value = serializers.DecimalField(max_digits=12, decimal_places=2)

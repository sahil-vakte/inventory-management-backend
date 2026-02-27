from rest_framework import serializers
from .models import StockItem, StockMovement
from colors.serializers import ColorListSerializer
from products.serializers import ProductListSerializer, ProductDetailSerializer

class StockMovementSerializer(serializers.ModelSerializer):
    """Serializer for Stock Movement model"""
    
    class Meta:
        model = StockMovement
        fields = [
            'id', 'movement_type', 'quantity', 'old_stock_level', 
            'new_stock_level', 'reference_number', 'reason',
            'created_by', 'is_deleted', 'deleted_at', 'created_at'
        ]
        read_only_fields = ['created_at', 'deleted_at']

class StockItemListSerializer(serializers.ModelSerializer):
    primary_location = serializers.CharField(source='primary_location.id', read_only=True)
    secondary_location = serializers.CharField(source='secondary_location.id', read_only=True)
    """Simplified serializer for stock list views"""
    color = ColorListSerializer(read_only=True)
    product = ProductListSerializer(read_only=True)
    stock_status = serializers.ReadOnlyField()
    total_available_stock = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = StockItem
        fields = [
            'sku', 'product_type', 'color', 'available_stock_rolls',
            'reserved_stock', 'total_available_stock', 'stock_status',
            'is_low_stock', 'is_active', 'is_deleted',
            'primary_location', 'secondary_location', 'product'
        ]

class StockItemDetailSerializer(serializers.ModelSerializer):
    primary_location = serializers.CharField(source='primary_location.id', read_only=True)
    secondary_location = serializers.CharField(source='secondary_location.id', read_only=True)
    """Detailed serializer for single stock item views"""
    color = ColorListSerializer(read_only=True)
    product = ProductDetailSerializer(read_only=True)
    stock_status = serializers.ReadOnlyField()
    total_available_stock = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    stock_value = serializers.ReadOnlyField()
    recent_movements = StockMovementSerializer(many=True, read_only=True, source='movements')
    
    class Meta:
        model = StockItem
        fields = '__all__'
        # primary_location and secondary_location now included
        read_only_fields = ['created_at', 'updated_at', 'last_stock_update', 'deleted_at']

class StockItemCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating stock items"""
    color_code = serializers.CharField(write_only=True, help_text="Color code to associate")
    
    class Meta:
        model = StockItem
        fields = [
            'sku', 'product_type', 'color_code', 'available_stock_rolls',
            'reserved_stock', 'minimum_stock_level', 'maximum_stock_level',
            'warehouse_location', 'supplier', 'lead_time_days',
            'unit_cost', 'last_purchase_price', 'last_purchase_date',
            'is_active', 'is_discontinued', 'notes'
        ]
    
    def validate_color_code(self, value):
        """Validate that the color code exists"""
        from colors.models import Color
        if not Color.objects.filter(color_code=value).exists():
            raise serializers.ValidationError(f"Color with code '{value}' does not exist")
        return value
    
    def validate_sku(self, value):
        """Validate SKU uniqueness among non-deleted records"""
        if self.instance:
            # For updates, exclude current instance
            existing = StockItem.all_objects.filter(
                sku=value, is_deleted=False
            ).exclude(sku=self.instance.sku)
        else:
            # For creation
            existing = StockItem.all_objects.filter(sku=value, is_deleted=False)
        
        if existing.exists():
            raise serializers.ValidationError("Stock item with this SKU already exists.")
        return value
    
    def create(self, validated_data):
        """Create stock item with color association"""
        from colors.models import Color
        color_code = validated_data.pop('color_code')
        color = Color.objects.get(color_code=color_code)
        validated_data['color'] = color
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update stock item with optional color change"""
        if 'color_code' in validated_data:
            from colors.models import Color
            color_code = validated_data.pop('color_code')
            color = Color.objects.get(color_code=color_code)
            validated_data['color'] = color
        return super().update(instance, validated_data)

class StockAdjustmentSerializer(serializers.Serializer):
    """Serializer for stock adjustment operations"""
    quantity = serializers.IntegerField(help_text="Positive for increase, negative for decrease")
    reason = serializers.CharField(max_length=200, default="Manual Adjustment")
    
    def validate_quantity(self, value):
        if value == 0:
            raise serializers.ValidationError("Quantity cannot be zero")
        return value
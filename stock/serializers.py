from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from .models import StockItem, StockMovement, StockBatch, StockBatchRoll
from .sku_utils import normalize_sku_reference
from colors.serializers import ColorListSerializer
from products.models import Product
from products.serializers import ProductDetailSerializer, get_product_child_product_url

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

class StockProductListSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    is_active = serializers.ReadOnlyField()
    primary_location = serializers.CharField(source='primary_location.id', read_only=True)
    secondary_location = serializers.CharField(source='secondary_location.id', read_only=True)
    child_product_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'vs_child_id', 'child_reference', 'child_product_title',
            'parent_product_images', 'child_product_url',
            'brand_name', 'price_break_1_price', 'is_active',
            'child_active', 'parent_active', 'featured', 'is_deleted',
            'primary_location', 'secondary_location'
        ]

    def get_child_product_url(self, obj):
        return get_product_child_product_url(obj)


class StockItemListSerializer(serializers.ModelSerializer):
    primary_location = serializers.SerializerMethodField()
    secondary_location = serializers.SerializerMethodField()
    parent_product_images = serializers.SerializerMethodField()
    child_product_url = serializers.SerializerMethodField()
    """Simplified serializer for stock list views"""
    color = ColorListSerializer(read_only=True)
    product = StockProductListSerializer(read_only=True)
    stock_status = serializers.ReadOnlyField()
    total_available_stock = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = StockItem
        fields = [
            'sku', 'product_type', 'color', 'available_stock_in_mtr',
            'reserved_stock', 'total_available_stock', 'stock_status',
            'is_low_stock', 'is_active', 'is_deleted',
            'primary_location', 'secondary_location',
            'parent_product_images', 'child_product_url', 'product'
        ]

    def get_primary_location(self, obj):
        return getattr(obj.primary_location, 'id', None)

    def get_secondary_location(self, obj):
        return getattr(obj.secondary_location, 'id', None)

    def get_parent_product_images(self, obj):
        return getattr(getattr(obj, 'product', None), 'parent_product_images', None)

    def get_child_product_url(self, obj):
        return get_product_child_product_url(getattr(obj, 'product', None))

class StockItemDetailSerializer(serializers.ModelSerializer):
    primary_location = serializers.SerializerMethodField()
    secondary_location = serializers.SerializerMethodField()
    parent_product_images = serializers.SerializerMethodField()
    child_product_url = serializers.SerializerMethodField()
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

    def get_primary_location(self, obj):
        return getattr(obj.primary_location, 'id', None)

    def get_secondary_location(self, obj):
        return getattr(obj.secondary_location, 'id', None)

    def get_parent_product_images(self, obj):
        return getattr(getattr(obj, 'product', None), 'parent_product_images', None)

    def get_child_product_url(self, obj):
        return get_product_child_product_url(getattr(obj, 'product', None))

class StockItemCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating stock items"""
    color_code = serializers.CharField(write_only=True, help_text="Color code to associate")
    primary_location = serializers.CharField(required=False, allow_null=True, write_only=True)
    secondary_location = serializers.CharField(required=False, allow_null=True, write_only=True)
    
    class Meta:
        model = StockItem
        fields = [
            'sku', 'product_type', 'color_code', 'available_stock_in_mtr',
            'reserved_stock', 'minimum_stock_level', 'maximum_stock_level',
            'warehouse_location', 'supplier', 'lead_time_days',
            'unit_cost', 'last_purchase_price', 'last_purchase_date',
            'is_active', 'is_discontinued', 'notes',
            'primary_location', 'secondary_location'
        ]
    
    def validate_color_code(self, value):
        """Validate that the color code exists"""
        from colors.models import Color
        if not Color.objects.filter(color_code=value).exists():
            raise serializers.ValidationError(f"Color with code '{value}' does not exist")
        return value
    
    def validate_sku(self, value):
        """Validate SKU uniqueness among non-deleted records"""
        value = normalize_sku_reference(value)
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

    def validate_product_type(self, value):
        return normalize_sku_reference(value)[:20]
    
    def create(self, validated_data):
        """Create stock item with color association"""
        from colors.models import Color
        color_code = validated_data.pop('color_code')
        color = Color.objects.get(color_code=color_code)
        validated_data['color'] = color

        # handle locations if provided
        from products.models import Location
        primary = validated_data.pop('primary_location', None)
        secondary = validated_data.pop('secondary_location', None)

        if primary:
            validated_data['primary_location'] = Location.objects.get(id=primary)
        if secondary:
            validated_data['secondary_location'] = Location.objects.get(id=secondary)

        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update stock item with optional color change"""
        if 'color_code' in validated_data:
            from colors.models import Color
            color_code = validated_data.pop('color_code')
            color = Color.objects.get(color_code=color_code)
            validated_data['color'] = color

        # handle location updates
        from products.models import Location
        if 'primary_location' in validated_data:
            primary = validated_data.pop('primary_location')
            if primary in [None, 'null', '']:
                instance.primary_location = None
            else:
                instance.primary_location = Location.objects.get(id=primary)

        if 'secondary_location' in validated_data:
            secondary = validated_data.pop('secondary_location')
            if secondary in [None, 'null', '']:
                instance.secondary_location = None
            else:
                instance.secondary_location = Location.objects.get(id=secondary)

        return super().update(instance, validated_data)

class StockAdjustmentSerializer(serializers.Serializer):
    """Serializer for stock adjustment operations"""
    quantity = serializers.IntegerField(help_text="Positive for increase, negative for decrease")
    reason = serializers.CharField(max_length=200, default="Manual Adjustment")
    
    def validate_quantity(self, value):
        if value == 0:
            raise serializers.ValidationError("Quantity cannot be zero")
        return value


class StockBatchRollSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockBatchRoll
        fields = [
            'id', 'roll_number', 'meterage', 'label_generated',
            'label_generated_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'label_generated', 'label_generated_at', 'created_at', 'updated_at'
        ]


class StockBatchListSerializer(serializers.ModelSerializer):
    rolls = StockBatchRollSerializer(many=True, read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = StockBatch
        fields = [
            'batch_id', 'sku', 'product_name', 'supplier',
            'created_by_username', 'batch_date', 'roll_count',
            'total_meterage', 'rolls', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


class StockBatchDetailSerializer(serializers.ModelSerializer):
    rolls = StockBatchRollSerializer(many=True, read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    stock_movement = serializers.SerializerMethodField()

    class Meta:
        model = StockBatch
        fields = [
            'batch_id', 'stock_item', 'sku', 'product_name', 'supplier',
            'created_by', 'created_by_username', 'batch_date',
            'total_meterage', 'roll_count', 'notes', 'rolls',
            'stock_movement', 'is_deleted', 'deleted_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields

    def get_stock_movement(self, obj):
        movement = StockMovement.all_objects.filter(
            stock_item=obj.stock_item,
            reference_number=obj.batch_id,
            movement_type='IN',
        ).order_by('-created_at').first()
        if not movement:
            return None
        return StockMovementSerializer(movement).data


class IncomingRollInputSerializer(serializers.Serializer):
    roll_number = serializers.IntegerField(min_value=1)
    meterage = serializers.IntegerField(min_value=1)


class StockBatchCreateSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=50)
    supplier = serializers.CharField(max_length=100)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    rolls = IncomingRollInputSerializer(many=True)

    def validate_sku(self, value):
        sku = value.strip()
        if find_stock_item_for_batch_sku(sku) is None:
            raise serializers.ValidationError(f"Stock item with SKU '{sku}' not found.")
        return sku

    def validate_rolls(self, value):
        if not value:
            raise serializers.ValidationError("At least one roll is required.")

        seen_roll_numbers = set()
        duplicate_roll_numbers = set()
        for roll in value:
            roll_number = roll['roll_number']
            if roll_number in seen_roll_numbers:
                duplicate_roll_numbers.add(roll_number)
            seen_roll_numbers.add(roll_number)

        if duplicate_roll_numbers:
            duplicates = ', '.join(str(number) for number in sorted(duplicate_roll_numbers))
            raise serializers.ValidationError(
                f"Duplicate roll numbers in this batch: {duplicates}"
            )
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        rolls = validated_data.pop('rolls')
        sku = validated_data['sku'].strip()
        supplier = validated_data['supplier'].strip()
        notes = validated_data.get('notes')
        incoming_meterage = sum(roll['meterage'] for roll in rolls)

        with transaction.atomic():
            stock_item = find_stock_item_for_batch_sku(
                sku,
                queryset=StockItem.all_objects.select_for_update().select_related('product'),
            )
            if stock_item is None:
                raise serializers.ValidationError({'sku': f"Stock item with SKU '{sku}' not found."})
            old_stock = stock_item.available_stock_in_mtr
            stock_item.available_stock_in_mtr = old_stock + incoming_meterage
            stock_item.supplier = supplier
            stock_item.last_stock_update = timezone.now()
            stock_item.save(update_fields=[
                'available_stock_in_mtr', 'supplier',
                'last_stock_update', 'updated_at'
            ])

            product = getattr(stock_item, 'product', None)
            product_name = (
                getattr(product, 'child_product_title', None)
                or getattr(product, 'parent_product_title', None)
                or stock_item.product_type
                or stock_item.sku
            )
            batch = StockBatch.objects.create(
                stock_item=stock_item,
                sku=normalize_stock_batch_sku(stock_item.sku),
                product_name=product_name,
                supplier=supplier,
                created_by=user,
                total_meterage=incoming_meterage,
                roll_count=len(rolls),
                notes=notes,
            )
            StockBatchRoll.objects.bulk_create([
                StockBatchRoll(
                    batch=batch,
                    roll_number=roll['roll_number'],
                    meterage=roll['meterage'],
                )
                for roll in rolls
            ])
            StockMovement.objects.create(
                stock_item=stock_item,
                movement_type='IN',
                quantity=incoming_meterage,
                old_stock_level=old_stock,
                new_stock_level=stock_item.available_stock_in_mtr,
                reference_number=batch.batch_id,
                reason='Incoming stock batch',
                created_by=getattr(user, 'username', None),
            )

        batch.old_stock_in_mtr = old_stock
        batch.incoming_meterage = incoming_meterage
        batch.new_stock_in_mtr = stock_item.available_stock_in_mtr
        return batch

    def to_representation(self, instance):
        data = StockBatchDetailSerializer(instance, context=self.context).data
        data['old_stock_in_mtr'] = getattr(instance, 'old_stock_in_mtr', None)
        data['incoming_meterage'] = getattr(instance, 'incoming_meterage', instance.total_meterage)
        data['new_stock_in_mtr'] = getattr(instance, 'new_stock_in_mtr', None)
        return data


class StockBatchLabelSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source='batch.sku', read_only=True)
    product_name = serializers.CharField(source='batch.product_name', read_only=True)
    batch_id = serializers.CharField(source='batch.batch_id', read_only=True)
    supplier = serializers.CharField(source='batch.supplier', read_only=True)
    date = serializers.DateField(source='batch.batch_date', read_only=True)

    class Meta:
        model = StockBatchRoll
        fields = [
            'sku', 'product_name', 'meterage', 'batch_id', 'supplier',
            'date', 'roll_number', 'label_generated', 'label_generated_at'
        ]


def normalize_stock_batch_sku(value):
    """Convert display-style SKUs like '(109 LT) DSND' to '109 LT DSND'."""
    return normalize_sku_reference(value)


def find_stock_item_for_batch_sku(value, queryset=None):
    queryset = queryset or StockItem.all_objects.all()
    sku = str(value or '').strip()
    normalized_sku = normalize_stock_batch_sku(sku)

    exact = queryset.filter(sku=sku, is_deleted=False).first()
    if exact:
        return exact

    normalized = queryset.filter(sku=normalized_sku, is_deleted=False).first()
    if normalized:
        return normalized

    for stock_item in queryset.filter(is_deleted=False):
        if normalize_stock_batch_sku(stock_item.sku) == normalized_sku:
            return stock_item
    return None

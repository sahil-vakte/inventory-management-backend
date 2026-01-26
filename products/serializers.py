from rest_framework import serializers
from .models import Product, Category, Brand, Location
class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model"""
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'parent', 'is_deleted', 'deleted_at', 'created_at']
        read_only_fields = ['created_at', 'deleted_at']

class BrandSerializer(serializers.ModelSerializer):
    """Serializer for Brand model"""
    
    class Meta:
        model = Brand
        fields = ['id', 'name', 'is_deleted', 'deleted_at', 'created_at']
        read_only_fields = ['created_at', 'deleted_at']

class ProductListSerializer(serializers.ModelSerializer):
    """Simplified serializer for product list views"""
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    effective_price = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    
    location = serializers.CharField(source='location.id', read_only=True)
    class Meta:
        model = Product
        fields = [
            'vs_child_id', 'child_reference', 'child_product_title',
            'brand_name', 'effective_price', 'is_active',
            'child_active', 'parent_active', 'featured', 'is_deleted',
            'location'
        ]

class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single product views"""
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    effective_price = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    
    location = LocationSerializer(read_only=True)
    location_id = serializers.CharField(source='location.id', read_only=True)
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating products"""
    
    location = serializers.CharField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Product
        exclude = ['is_deleted', 'deleted_at', 'created_at', 'updated_at']

    def validate(self, data):
        # Ensure prices are positive
        if data.get('rrp_price_inc_vat', 0) < 0:
            raise serializers.ValidationError("RRP price cannot be negative")
        if data.get('cost_price_inc_vat', 0) < 0:
            raise serializers.ValidationError("Cost price cannot be negative")

        # Validate location exists if provided
        location_id = data.get('location')
        if location_id:
            try:
                location = Location.objects.get(id=location_id)
                data['location'] = location
            except Location.DoesNotExist:
                raise serializers.ValidationError({"location": "Location does not exist."})
        return data

    def validate_vs_child_id(self, value):
        if self.instance:
            existing = Product.all_objects.filter(
                vs_child_id=value, is_deleted=False
            ).exclude(vs_child_id=self.instance.vs_child_id)
        else:
            existing = Product.all_objects.filter(vs_child_id=value, is_deleted=False)
        if existing.exists():
            raise serializers.ValidationError("Product with this VS Child ID already exists.")
        return value
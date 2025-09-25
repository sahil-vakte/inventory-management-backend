from rest_framework import serializers
from .models import Product, Category, Brand

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
    
    class Meta:
        model = Product
        fields = [
            'vs_child_id', 'child_reference', 'child_product_title',
            'brand_name', 'effective_price', 'is_active',
            'child_active', 'parent_active', 'featured', 'is_deleted'
        ]

class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single product views"""
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    effective_price = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating products"""
    
    class Meta:
        model = Product
        exclude = ['is_deleted', 'deleted_at', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Custom validation for product data"""
        # Ensure prices are positive
        if data.get('rrp_price_inc_vat', 0) < 0:
            raise serializers.ValidationError("RRP price cannot be negative")
        if data.get('cost_price_inc_vat', 0) < 0:
            raise serializers.ValidationError("Cost price cannot be negative")
        
        return data
    
    def validate_vs_child_id(self, value):
        """Validate VS Child ID uniqueness among non-deleted records"""
        if self.instance:
            # For updates, exclude current instance
            existing = Product.all_objects.filter(
                vs_child_id=value, is_deleted=False
            ).exclude(vs_child_id=self.instance.vs_child_id)
        else:
            # For creation
            existing = Product.all_objects.filter(vs_child_id=value, is_deleted=False)
        
        if existing.exists():
            raise serializers.ValidationError("Product with this VS Child ID already exists.")
        return value
from rest_framework import serializers
from .models import Color

class ColorSerializer(serializers.ModelSerializer):
    """Serializer for Color model"""
    display_name = serializers.ReadOnlyField()
    
    class Meta:
        model = Color
        fields = [
            'color_code', 'color_name', 'secondary_code', 
            'display_name', 'is_deleted', 'deleted_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'deleted_at']

class ColorListSerializer(serializers.ModelSerializer):
    """Simplified serializer for color list views"""
    display_name = serializers.ReadOnlyField()
    
    class Meta:
        model = Color
        fields = ['color_code', 'color_name', 'display_name', 'is_deleted']

class ColorCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating colors"""
    
    class Meta:
        model = Color
        fields = ['color_code', 'color_name', 'secondary_code']
    
    def validate_color_code(self, value):
        """Validate color code uniqueness among non-deleted records"""
        if self.instance:
            # For updates, exclude current instance
            existing = Color.all_objects.filter(
                color_code=value, is_deleted=False
            ).exclude(color_code=self.instance.color_code)
        else:
            # For creation
            existing = Color.all_objects.filter(color_code=value, is_deleted=False)
        
        if existing.exists():
            raise serializers.ValidationError("Color code already exists.")
        return value
from django.db import models
from django.utils import timezone

class ColorManager(models.Manager):
    """Custom manager for Color model with soft delete support"""
    
    def get_queryset(self):
        """Return only non-deleted objects by default"""
        return super().get_queryset().filter(is_deleted=False)
    
    def with_deleted(self):
        """Return all objects including deleted ones"""
        return super().get_queryset()
    
    def only_deleted(self):
        """Return only deleted objects"""
        return super().get_queryset().filter(is_deleted=True)

class Color(models.Model):
    """Model for color management based on Excel Colours sheet"""
    
    color_code = models.CharField(max_length=10, unique=True, primary_key=True, 
                                 help_text="Color abbreviation code (e.g., ABRN)")
    color_name = models.CharField(max_length=100, 
                                 help_text="Full color name (e.g., Auburn Brown)")
    
    # Additional color attributes found in Excel
    secondary_code = models.CharField(max_length=10, blank=True, null=True,
                                     help_text="Secondary color code if applicable")
    
    # Soft delete field
    is_deleted = models.BooleanField(default=False, help_text="Soft delete flag")
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="When the record was deleted")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Managers
    objects = ColorManager()
    all_objects = models.Manager()  # Manager to access all objects including deleted
    
    class Meta:
        db_table = 'colors'
        ordering = ['color_code']
        verbose_name = 'Color'
        verbose_name_plural = 'Colors'
    
    def __str__(self):
        return f"{self.color_code} - {self.color_name}"
    
    @property
    def display_name(self):
        """Returns formatted display name"""
        return f"{self.color_name} ({self.color_code})"
    
    def soft_delete(self):
        """Soft delete the color"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore soft deleted color"""
        self.is_deleted = False
        self.deleted_at = None
        self.save()
    
    def hard_delete(self):
        """Permanently delete the color"""
        super().delete()

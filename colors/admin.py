from django.contrib import admin
from .models import Color

@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ['color_code', 'color_name', 'secondary_code', 'is_deleted', 'created_at']
    list_filter = ['is_deleted', 'created_at']
    search_fields = ['color_code', 'color_name']
    ordering = ['color_code']
    readonly_fields = ['created_at', 'updated_at', 'deleted_at']
    
    def get_queryset(self, request):
        """Override to show all objects including deleted ones in admin"""
        return Color.all_objects.all()
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('color_code', 'color_name', 'secondary_code')
        }),
        ('Status', {
            'fields': ('is_deleted', 'deleted_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        })
    )
    
    actions = ['soft_delete_selected', 'restore_selected', 'hard_delete_selected']
    
    def soft_delete_selected(self, request, queryset):
        """Soft delete selected colors"""
        count = 0
        for obj in queryset.filter(is_deleted=False):
            obj.soft_delete()
            count += 1
        self.message_user(request, f'{count} colors were soft deleted.')
    soft_delete_selected.short_description = "Soft delete selected colors"
    
    def restore_selected(self, request, queryset):
        """Restore selected colors"""
        count = 0
        for obj in queryset.filter(is_deleted=True):
            obj.restore()
            count += 1
        self.message_user(request, f'{count} colors were restored.')
    restore_selected.short_description = "Restore selected colors"
    
    def hard_delete_selected(self, request, queryset):
        """Permanently delete selected colors"""
        count = queryset.count()
        for obj in queryset:
            obj.hard_delete()
        self.message_user(request, f'{count} colors were permanently deleted.')
    hard_delete_selected.short_description = "Permanently delete selected colors"

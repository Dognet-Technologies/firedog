from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'description', 'success', 'ip_address', 'created_at']
    list_filter = ['action', 'success', 'created_at']
    search_fields = ['user__username', 'description', 'ip_address']
    readonly_fields = ['created_at', 'old_values', 'new_values']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

from django.contrib import admin
from .models import FirewallRule

@admin.register(FirewallRule)
class FirewallRuleAdmin(admin.ModelAdmin):
    list_display = ['target', 'chain', 'protocol', 'port', 'action', 'is_synced', 'created_at']
    list_filter = ['chain', 'protocol', 'action', 'is_custom', 'is_synced']
    search_fields = ['target__ip_address', 'comment', 'source_ip', 'dest_ip']
    readonly_fields = ['created_at', 'updated_at']

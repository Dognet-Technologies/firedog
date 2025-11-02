from django.contrib import admin
from .models import DiscoveredHost

@admin.register(DiscoveredHost)
class DiscoveredHostAdmin(admin.ModelAdmin):
    list_display = ['ip_address', 'mac_address', 'hostname', 'vendor', 'is_alive', 'is_imported', 'last_seen']
    list_filter = ['is_alive', 'is_imported', 'discovered_at', 'network']
    search_fields = ['ip_address', 'mac_address', 'hostname', 'vendor']
    readonly_fields = ['discovered_at', 'last_seen', 'scan_count']

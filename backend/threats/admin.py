from django.contrib import admin
from .models import ThreatLog

@admin.register(ThreatLog)
class ThreatLogAdmin(admin.ModelAdmin):
    list_display = ['source_ip', 'target', 'threat_score', 'severity', 'is_blocked', 'is_resolved', 'detected_at']
    list_filter = ['severity', 'is_blocked', 'is_resolved', 'detected_at']
    search_fields = ['source_ip', 'target__ip_address', 'description']
    readonly_fields = ['detected_at', 'updated_at', 'resolved_at']

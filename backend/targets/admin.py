"""
Admin configuration per l'app Targets
"""

from django.contrib import admin
from .models import Target


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = [
        "ip_address",
        "hostname",
        "status",
        "firedog_version",
        "last_seen",
        "created_at",
    ]
    list_filter = ["status", "created_at", "last_seen"]
    search_fields = ["ip_address", "hostname", "description"]
    readonly_fields = ["created_at", "updated_at", "last_seen", "last_fetch"]

    fieldsets = (
        ("Identificazione", {"fields": ("ip_address", "hostname", "description")}),
        ("Stato", {"fields": ("status", "firedog_version", "error_message")}),
        ("Configurazione SSH", {"fields": ("ssh_port", "ssh_user")}),
        (
            "Metadata",
            {
                "fields": ("last_seen", "last_fetch", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

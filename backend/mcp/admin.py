from django.contrib import admin

from .models import MCPAPIKey


@admin.register(MCPAPIKey)
class MCPAPIKeyAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "key_prefix",
        "user",
        "is_active",
        "created_at",
        "expires_at",
        "last_used_at",
    ]
    list_filter = ["is_active"]
    search_fields = ["name", "key_prefix", "user__username"]
    readonly_fields = ["key_prefix", "key_hash", "created_at", "last_used_at"]

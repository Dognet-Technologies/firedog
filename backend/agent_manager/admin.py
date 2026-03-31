"""
Admin per agent_manager app
"""

from django.contrib import admin
from .models import (
    AgentAPIKey,
    PairingSession,
    AgentConnection,
    AgentCommand,
    AgentHeartbeat,
)


@admin.register(AgentAPIKey)
class AgentAPIKeyAdmin(admin.ModelAdmin):
    list_display = ["id", "is_active", "created_at", "expires_at", "created_by"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["created_by"]
    readonly_fields = ["key_hash", "created_at"]


@admin.register(PairingSession)
class PairingSessionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "target",
        "status",
        "phase_1_verified",
        "phase_2_verified",
        "created_at",
        "expires_at",
    ]
    list_filter = ["status", "phase_1_verified", "phase_2_verified", "created_at"]
    search_fields = [
        "target__hostname",
        "target__ip_address",
        "agent_ip",
        "agent_hostname",
    ]
    readonly_fields = ["created_at", "completed_at"]


@admin.register(AgentConnection)
class AgentConnectionAdmin(admin.ModelAdmin):
    list_display = ["target", "is_online", "last_heartbeat", "connected_at"]
    list_filter = ["is_online", "connected_at"]
    search_fields = ["target__hostname", "target__ip_address"]
    readonly_fields = ["target", "connected_at", "disconnected_at"]


@admin.register(AgentCommand)
class AgentCommandAdmin(admin.ModelAdmin):
    list_display = [
        "command_id",
        "target",
        "action",
        "status",
        "created_at",
        "completed_at",
    ]
    list_filter = ["status", "action", "created_at"]
    search_fields = ["target__hostname", "target__ip_address", "command_id"]
    readonly_fields = ["command_id", "created_at", "sent_at", "completed_at"]


@admin.register(AgentHeartbeat)
class AgentHeartbeatAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "target",
        "timestamp",
        "cpu_percent",
        "memory_percent",
        "disk_percent",
    ]
    list_filter = ["timestamp"]
    search_fields = ["target__hostname", "target__ip_address"]
    readonly_fields = ["timestamp"]

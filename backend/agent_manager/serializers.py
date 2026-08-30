"""
Serializers per agent_manager app
"""

from rest_framework import serializers
from .models import (
    AgentAPIKey,
    PairingSession,
    AgentConnection,
    AgentCommand,
    AgentHeartbeat,
)


class AgentAPIKeySerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by", read_only=True)

    class Meta:
        model = AgentAPIKey
        fields = [
            "id",
            "key_hash",
            "is_active",
            "created_at",
            "expires_at",
            "created_by",
            "created_by_username",
            "last_used_at",
        ]
        read_only_fields = ["id", "key_hash", "created_at", "last_used_at"]


class PairingSessionSerializer(serializers.ModelSerializer):
    target_hostname = serializers.CharField(source="target.hostname", read_only=True)
    target_ip = serializers.CharField(source="target.ip_address", read_only=True)

    class Meta:
        model = PairingSession
        fields = [
            "id",
            "target",
            "target_hostname",
            "target_ip",
            "status",
            "phase_1_verified",
            "phase_2_verified",
            "agent_ip",
            "agent_hostname",
            "agent_mac",
            "error_message",
            "created_at",
            "expires_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "phase_1_verified",
            "phase_2_verified",
            "agent_ip",
            "agent_hostname",
            "agent_mac",
            "error_message",
            "created_at",
            "expires_at",
            "completed_at",
        ]


class AgentConnectionSerializer(serializers.ModelSerializer):
    target_hostname = serializers.CharField(source="target.hostname", read_only=True)
    target_ip = serializers.CharField(source="target.ip_address", read_only=True)

    class Meta:
        model = AgentConnection
        fields = [
            "target",
            "target_hostname",
            "target_ip",
            "websocket_channel",
            "is_online",
            "last_heartbeat",
            "heartbeat_interval",
            "system_info",
            "connected_at",
            "disconnected_at",
        ]
        read_only_fields = [
            "websocket_channel",
            "is_online",
            "last_heartbeat",
            "system_info",
            "connected_at",
            "disconnected_at",
        ]


class AgentCommandSerializer(serializers.ModelSerializer):
    target_hostname = serializers.CharField(source="target.hostname", read_only=True)
    target_ip = serializers.CharField(source="target.ip_address", read_only=True)

    class Meta:
        model = AgentCommand
        fields = [
            "command_id",
            "target",
            "target_hostname",
            "target_ip",
            "action",
            "payload",
            "status",
            "result",
            "error_message",
            "timeout_seconds",
            "created_at",
            "sent_at",
            "completed_at",
        ]
        read_only_fields = [
            "command_id",
            "status",
            "result",
            "error_message",
            "created_at",
            "sent_at",
            "completed_at",
        ]


class AgentHeartbeatSerializer(serializers.ModelSerializer):
    target_hostname = serializers.CharField(source="target.hostname", read_only=True)
    target_ip = serializers.CharField(source="target.ip_address", read_only=True)

    class Meta:
        model = AgentHeartbeat
        fields = [
            "id",
            "target",
            "target_hostname",
            "target_ip",
            "timestamp",
            "cpu_percent",
            "memory_percent",
            "disk_percent",
            "memory_total_kb",
            "memory_used_kb",
            "disk_total_kb",
            "disk_used_kb",
            "load_avg_1m",
            "load_avg_5m",
            "load_avg_15m",
            "uptime_seconds",
            "bytes_sent",
            "bytes_recv",
            "active_rules_count",
            "blocked_ips_count",
            "raw_data",
        ]
        read_only_fields = ["id", "timestamp"]

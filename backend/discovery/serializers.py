"""
Serializers per Discovery
"""

from rest_framework import serializers
from .models import DiscoveredHost
from targets.models import Target


class DiscoveredHostSerializer(serializers.ModelSerializer):
    """Serializer completo per DiscoveredHost"""

    already_target = serializers.SerializerMethodField()

    class Meta:
        model = DiscoveredHost
        fields = [
            "id",
            "ip_address",
            "mac_address",
            "hostname",
            "vendor",
            "network",
            "netmask",
            "discovered_at",
            "last_seen",
            "scan_count",
            "is_alive",
            "is_imported",
            "notes",
            "already_target",
        ]
        read_only_fields = ["id", "discovered_at", "last_seen", "scan_count"]

    def get_already_target(self, obj):
        """Check if IP already exists as target"""
        return Target.objects.filter(ip_address=obj.ip_address).exists()


class DiscoveredHostListSerializer(serializers.ModelSerializer):
    """Serializer semplificato per liste"""

    already_target = serializers.SerializerMethodField()

    class Meta:
        model = DiscoveredHost
        fields = [
            "id",
            "ip_address",
            "mac_address",
            "hostname",
            "vendor",
            "last_seen",
            "is_alive",
            "is_imported",
            "already_target",
        ]

    def get_already_target(self, obj):
        return Target.objects.filter(ip_address=obj.ip_address).exists()


class BulkImportResultSerializer(serializers.Serializer):
    """Serializer per risultati bulk import"""

    imported = serializers.IntegerField()
    skipped = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.DictField())

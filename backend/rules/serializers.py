"""
Serializers per l'app Rules
"""

from rest_framework import serializers
from .models import FirewallRule


class FirewallRuleSerializer(serializers.ModelSerializer):
    """Serializer per il modello FirewallRule"""

    rule_description = serializers.ReadOnlyField()
    target_ip = serializers.CharField(source="target.ip_address", read_only=True)

    class Meta:
        model = FirewallRule
        fields = [
            "id",
            "target",
            "target_ip",
            "chain",
            "interface",
            "rule_number",
            "protocol",
            "port",
            "source_ip",
            "dest_ip",
            "action",
            "comment",
            "is_custom",
            "is_synced",
            "group_origin",
            "created_at",
            "updated_at",
            "rule_description",
        ]
        read_only_fields = [
            "is_synced",
            "created_at",
            "updated_at",
        ]


class FirewallRuleListSerializer(serializers.ModelSerializer):
    """Serializer semplificato per lista regole"""

    target_ip = serializers.CharField(source="target.ip_address", read_only=True)
    rule_description = serializers.ReadOnlyField()

    class Meta:
        model = FirewallRule
        fields = [
            "id",
            "target",
            "target_ip",
            "chain",
            "interface",
            "rule_number",
            "protocol",
            "port",
            "source_ip",
            "dest_ip",
            "action",
            "comment",
            "is_custom",
            "is_synced",
            "group_origin",
            "rule_description",
            "created_at",
            "updated_at",
        ]

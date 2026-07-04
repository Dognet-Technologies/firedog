"""
Serializers per l'app Threats
"""

from rest_framework import serializers
from .models import ThreatLog
from targets.models import Target, Statistics
from threats.models import ThreatLog
from audit.models import AuditLog
from rules.models import FirewallRule


class ThreatLogSerializer(serializers.ModelSerializer):
    """Serializer per il modello ThreatLog"""

    target_ip = serializers.CharField(source="target.ip_address", read_only=True)
    attack_description = serializers.ReadOnlyField()

    class Meta:
        model = ThreatLog
        fields = [
            "id",
            "target",
            "target_ip",
            "source_ip",
            "dest_port",
            "protocol",
            "threat_score",
            "severity",
            "packet_count",
            "reasons",
            "description",
            "country_code",
            "is_blocked",
            "is_resolved",
            "resolved_at",
            "detected_at",
            "updated_at",
            "attack_description",
        ]
        read_only_fields = [
            "detected_at",
            "updated_at",
            "resolved_at",
        ]


class ThreatLogListSerializer(serializers.ModelSerializer):
    """Serializer per lista minacce.

    Include i campi che il frontend rende sia in tabella (protocol, dest_port,
    packet_count, country_code) sia nel modal di dettaglio (description,
    reasons, resolved_at). Tenuto comunque distinto dal serializer pieno per
    non esporre dati interni che potessero servire in futuro al solo detail.
    """

    target_ip = serializers.CharField(source="target.ip_address", read_only=True)

    class Meta:
        model = ThreatLog
        fields = [
            "id",
            "target_ip",
            "source_ip",
            "dest_port",
            "protocol",
            "threat_score",
            "severity",
            "packet_count",
            "country_code",
            "description",
            "reasons",
            "is_blocked",
            "is_resolved",
            "resolved_at",
            "detected_at",
        ]


class ThreatLogStatsSerializer(serializers.Serializer):
    """Serializer per statistiche minacce"""

    total_threats = serializers.IntegerField()
    critical_threats = serializers.IntegerField()
    high_threats = serializers.IntegerField()
    medium_threats = serializers.IntegerField()
    low_threats = serializers.IntegerField()
    blocked_ips = serializers.IntegerField()
    resolved_threats = serializers.IntegerField()
    unresolved_threats = serializers.IntegerField()
    top_attackers = serializers.ListField(child=serializers.DictField())
    recent_threats = ThreatLogListSerializer(many=True)

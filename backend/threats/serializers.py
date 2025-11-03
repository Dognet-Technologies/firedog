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
    
    target_ip = serializers.CharField(source='target.ip_address', read_only=True)
    attack_description = serializers.ReadOnlyField()
    
    class Meta:
        model = ThreatLog
        fields = [
            'id',
            'target',
            'target_ip',
            'source_ip',
            'dest_port',
            'protocol',
            'threat_score',
            'severity',
            'packet_count',
            'reasons',
            'description',
            'country_code',
            'is_blocked',
            'is_resolved',
            'resolved_at',
            'detected_at',
            'updated_at',
            'attack_description',
        ]
        read_only_fields = [
            'detected_at',
            'updated_at',
            'resolved_at',
        ]


class ThreatLogListSerializer(serializers.ModelSerializer):
    """Serializer semplificato per lista minacce"""
    
    target_ip = serializers.CharField(source='target.ip_address', read_only=True)
    
    class Meta:
        model = ThreatLog
        fields = [
            'id',
            'target_ip',
            'source_ip',
            'threat_score',
            'severity',
            'is_blocked',
            'is_resolved',
            'detected_at',
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


# === Aggiunto per modfica === # 
class ThreatLogSerializer(serializers.Serializer):
    """Serializer per ThreatLog model"""
    id = serializers.IntegerField(read_only=True)
    target_id = serializers.IntegerField()
    source_ip = serializers.IPAddressField()
    threat_score = serializers.IntegerField()
    packets = serializers.IntegerField()
    ports_count = serializers.IntegerField()
    protocols = serializers.CharField()
    threat_type = serializers.CharField()
    classification = serializers.CharField()
    detected_at = serializers.DateTimeField()
    acknowledged = serializers.BooleanField()
    
    # Extra info
    target_hostname = serializers.SerializerMethodField()
    severity_color = serializers.SerializerMethodField()
    
    def get_target_hostname(self, obj):
        """Ottieni hostname del target"""
        return obj.target.hostname if obj.target else None
    
    def get_severity_color(self, obj):
        """Colore per UI in base a classification"""
        colors = {
            'CRITICAL': '#dc2626',  # red-600
            'HIGH': '#ea580c',      # orange-600
            'MEDIUM': '#ca8a04',    # yellow-600
            'LOW': '#65a30d'        # lime-600
        }
        return colors.get(obj.classification, '#6b7280')  # gray-500 default


class ThreatLogListSerializer(serializers.Serializer):
    """Serializer compatto per liste"""
    id = serializers.IntegerField(read_only=True)
    source_ip = serializers.IPAddressField()
    threat_score = serializers.IntegerField()
    threat_type = serializers.CharField()
    classification = serializers.CharField()
    detected_at = serializers.DateTimeField()
    acknowledged = serializers.BooleanField()
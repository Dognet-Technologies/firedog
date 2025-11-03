from rest_framework import serializers
from django.contrib.postgres.fields import ArrayField
from api.models import Statistics
from threats.models import ThreatLog
from audit.models import AuditLog
from rules.models import FirewallRule


class StatisticsSerializer(serializers.Serializer):
    """Serializer per Statistics model"""
    id = serializers.IntegerField(read_only=True)
    target_id = serializers.IntegerField()
    input_packets = serializers.IntegerField()
    output_packets = serializers.IntegerField()
    input_dropped = serializers.IntegerField()
    output_dropped = serializers.IntegerField()
    pcap_input_size = serializers.IntegerField()
    pcap_output_size = serializers.IntegerField()
    collected_at = serializers.DateTimeField()
    
    # Campi calcolati
    input_drop_rate = serializers.SerializerMethodField()
    output_drop_rate = serializers.SerializerMethodField()
    
    def get_input_drop_rate(self, obj):
        """Calcola percentuale pacchetti droppati in input"""
        if obj.input_packets > 0:
            return round((obj.input_dropped / obj.input_packets) * 100, 2)
        return 0.0
    
    def get_output_drop_rate(self, obj):
        """Calcola percentuale pacchetti droppati in output"""
        if obj.output_packets > 0:
            return round((obj.output_dropped / obj.output_packets) * 100, 2)
        return 0.0


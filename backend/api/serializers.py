"""
Serializers per l'app API
"""

from rest_framework import serializers
from .models import Statistics, Alert, Config


class StatisticsSerializer(serializers.ModelSerializer):
    """Serializer per Statistics model"""

    # Campi calcolati
    input_drop_rate = serializers.SerializerMethodField()
    output_drop_rate = serializers.SerializerMethodField()
    total_packets = serializers.SerializerMethodField()
    total_dropped = serializers.SerializerMethodField()

    class Meta:
        model = Statistics
        fields = [
            "id",
            "target",
            "input_packets",
            "output_packets",
            "input_dropped",
            "output_dropped",
            "pcap_input_size",
            "pcap_output_size",
            "collected_at",
            "input_drop_rate",
            "output_drop_rate",
            "total_packets",
            "total_dropped",
        ]
        read_only_fields = ["collected_at"]

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

    def get_total_packets(self, obj):
        """Totale pacchetti processati"""
        return obj.input_packets + obj.output_packets

    def get_total_dropped(self, obj):
        """Totale pacchetti droppati"""
        return obj.input_dropped + obj.output_dropped


class AlertSerializer(serializers.ModelSerializer):
    """Serializer per Alert model"""

    target_hostname = serializers.CharField(source="target.hostname", read_only=True)
    severity_color = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            "id",
            "target",
            "target_hostname",
            "severity",
            "severity_color",
            "title",
            "message",
            "acknowledged",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_severity_color(self, obj):
        """Colore per UI in base a severity"""
        colors = {
            "critical": "#dc2626",  # red-600
            "high": "#ea580c",  # orange-600
            "medium": "#ca8a04",  # yellow-600
            "low": "#65a30d",  # lime-600
            "info": "#3b82f6",  # blue-500
        }
        return colors.get(obj.severity, "#6b7280")  # gray-500 default


class ConfigSerializer(serializers.ModelSerializer):
    """Serializer per Config model"""

    class Meta:
        model = Config
        fields = ["key", "value", "updated_at"]
        read_only_fields = ["updated_at"]

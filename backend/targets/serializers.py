"""
Serializers per l'app Targets
"""
from rest_framework import serializers
from .models import Target


class TargetSerializer(serializers.ModelSerializer):
    """Serializer per il modello Target"""
    
    connection_string = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    
    class Meta:
        model = Target
        fields = [
            'id',
            'ip_address',
            'hostname',
            'description',
            'status',
            'firedog_version',
            'ssh_port',
            'ssh_user',
            'last_seen',
            'last_fetch',
            'error_message',
            'created_at',
            'updated_at',
            'connection_string',
            'is_active',
        ]
        read_only_fields = [
            'status',
            'firedog_version',
            'last_seen',
            'last_fetch',
            'error_message',
            'created_at',
            'updated_at',
        ]


class TargetListSerializer(serializers.ModelSerializer):
    """Serializer semplificato per lista targets"""
    
    is_active = serializers.ReadOnlyField()
    
    class Meta:
        model = Target
        fields = [
            'id',
            'ip_address',
            'hostname',
            'status',
            'firedog_version',
            'last_seen',
            'is_active',
        ]


class TargetCreateSerializer(serializers.ModelSerializer):
    """Serializer per creazione target"""
    
    class Meta:
        model = Target
        fields = [
            'ip_address',
            'hostname',
            'description',
            'ssh_port',
            'ssh_user',
        ]
    
    def validate_ip_address(self, value):
        """Verifica che IP non sia già presente"""
        if Target.objects.filter(ip_address=value).exists():
            raise serializers.ValidationError("Questo IP è già registrato come target")
        return value

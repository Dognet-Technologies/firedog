"""
Serializers per l'app Audit
"""
from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer per il modello AuditLog"""
    
    username = serializers.CharField(source='user.username', read_only=True)
    action_display = serializers.ReadOnlyField()
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user',
            'username',
            'action',
            'action_display',
            'description',
            'old_values',
            'new_values',
            'ip_address',
            'user_agent',
            'success',
            'error_message',
            'created_at',
        ]
        read_only_fields = ['created_at']


class AuditLogListSerializer(serializers.ModelSerializer):
    """Serializer semplificato per lista audit logs"""
    
    username = serializers.CharField(source='user.username', read_only=True)
    action_display = serializers.ReadOnlyField()
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'username',
            'action_display',
            'description',
            'success',
            'created_at',
        ]

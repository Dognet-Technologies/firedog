"""
Serializers per l'app Audit
"""
from rest_framework import serializers
from .models import AuditLog
from rest_framework import serializers
from .models import FirewallRule
from targets.models import Target
from api.models import Statistics
from threats.models import ThreatLog
from audit.models import AuditLog
from rules.models import FirewallRule

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

class AuditLogSerializer(serializers.Serializer):
    """Serializer per AuditLog model"""
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField()
    action = serializers.CharField()
    target_id = serializers.IntegerField(allow_null=True)
    details = serializers.JSONField()
    ip_address = serializers.IPAddressField(allow_null=True)
    timestamp = serializers.DateTimeField()
    
    # Extra info
    target_hostname = serializers.SerializerMethodField()
    action_description = serializers.SerializerMethodField()
    
    def get_target_hostname(self, obj):
        """Ottieni hostname del target se presente"""
        if obj.target:
            return obj.target.hostname
        return None
    
    def get_action_description(self, obj):
        """Descrizione human-readable dell'azione"""
        descriptions = {
            'login': 'User logged in',
            'logout': 'User logged out',
            'target.add': 'Added new target',
            'target.install': 'Installed firedog on target',
            'target.delete': 'Deleted target',
            'rule.add': 'Added firewall rule',
            'rule.remove': 'Removed firewall rule',
            'threat.acknowledge': 'Acknowledged threat',
            'config.update': 'Updated configuration',
            'ssh_key.rotate': 'Rotated SSH keys',
            'file.integrity.violation': 'File integrity violation detected',
            'traffic.analyze': 'Analyzed network traffic'
        }
        return descriptions.get(obj.action, obj.action)



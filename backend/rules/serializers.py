"""
Serializers per l'app Rules
"""
from rest_framework import serializers
from .models import FirewallRule
from targets.models import Target, Statistics
from threats.models import ThreatLog
from audit.models import AuditLog
from rules.models import FirewallRule


class FirewallRuleSerializer(serializers.ModelSerializer):
    """Serializer per il modello FirewallRule"""
    
    rule_description = serializers.ReadOnlyField()
    target_ip = serializers.CharField(source='target.ip_address', read_only=True)
    
    class Meta:
        model = FirewallRule
        fields = [
            'id',
            'target',
            'target_ip',
            'chain',
            'rule_number',
            'protocol',
            'port',
            'source_ip',
            'dest_ip',
            'action',
            'comment',
            'is_custom',
            'is_synced',
            'created_at',
            'updated_at',
            'rule_description',
        ]
        read_only_fields = [
            'is_synced',
            'created_at',
            'updated_at',
        ]


class FirewallRuleCreateSerializer(serializers.ModelSerializer):
    """Serializer per creazione regola firewall"""
    
    class Meta:
        model = FirewallRule
        fields = [
            'target',
            'chain',
            'protocol',
            'port',
            'source_ip',
            'dest_ip',
            'action',
            'comment',
        ]
    
    def validate_target(self, value):
        """Verifica che il target sia online"""
        if value.status != 'online':
            raise serializers.ValidationError(
                f"Il target deve essere online per aggiungere regole (stato attuale: {value.status})"
            )
        return value
    
    def validate(self, data):
        """Validazione incrociata"""
        chain = data.get('chain')
        source_ip = data.get('source_ip')
        dest_ip = data.get('dest_ip')
        
        # Validazione source_ip solo per INPUT
        if source_ip and chain != 'INPUT':
            raise serializers.ValidationError({
                'source_ip': 'source_ip può essere specificato solo per chain INPUT'
            })
        
        # Validazione dest_ip solo per OUTPUT
        if dest_ip and chain != 'OUTPUT':
            raise serializers.ValidationError({
                'dest_ip': 'dest_ip può essere specificato solo per chain OUTPUT'
            })
        
        return data


class FirewallRuleListSerializer(serializers.ModelSerializer):
    """Serializer semplificato per lista regole"""
    
    target_ip = serializers.CharField(source='target.ip_address', read_only=True)
    rule_description = serializers.ReadOnlyField()
    
    class Meta:
        model = FirewallRule
        fields = [
            'id',
            'target_ip',
            'chain',
            'protocol',
            'port',
            'action',
            'is_synced',
            'rule_description',
        ]


class FirewallRuleSerializer(serializers.Serializer):
    """Serializer per FirewallRule model"""
    id = serializers.IntegerField(read_only=True)
    target_id = serializers.IntegerField()
    chain = serializers.CharField()
    rule_number = serializers.IntegerField()
    protocol = serializers.CharField()
    port = serializers.IntegerField(allow_null=True)
    source_ip = serializers.IPAddressField(allow_null=True)
    dest_ip = serializers.IPAddressField(allow_null=True)
    action = serializers.CharField()
    comment = serializers.CharField(allow_blank=True)
    packets = serializers.IntegerField()
    bytes = serializers.IntegerField()
    synced_at = serializers.DateTimeField()
    
    # Extra
    target_hostname = serializers.SerializerMethodField()
    formatted_rule = serializers.SerializerMethodField()
    
    def get_target_hostname(self, obj):
        return obj.target.hostname if obj.target else None
    
    def get_formatted_rule(self, obj):
        """Formatta regola per display"""
        parts = [obj.action, obj.protocol.upper()]
        
        if obj.port:
            parts.append(f"port {obj.port}")
        
        if obj.source_ip:
            parts.append(f"from {obj.source_ip}")
        
        if obj.dest_ip:
            parts.append(f"to {obj.dest_ip}")
        
        if obj.comment:
            parts.append(f"# {obj.comment}")
        
        return " ".join(parts)


class FirewallRuleListSerializer(serializers.Serializer):
    """Serializer compatto per liste"""
    id = serializers.IntegerField(read_only=True)
    chain = serializers.CharField()
    rule_number = serializers.IntegerField()
    protocol = serializers.CharField()
    port = serializers.IntegerField(allow_null=True)
    action = serializers.CharField()
    comment = serializers.CharField()
    packets = serializers.IntegerField()
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
    target_ip = serializers.CharField(source="target.ip_address", read_only=True)

    class Meta:
        model = FirewallRule
        fields = [
            "id",
            "target",
            "target_ip",
            "chain",
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


class FirewallRuleCreateSerializer(serializers.ModelSerializer):
    """Serializer per creazione regola firewall"""

    class Meta:
        model = FirewallRule
        fields = [
            "target",
            "chain",
            "protocol",
            "port",
            "source_ip",
            "dest_ip",
            "action",
            "comment",
        ]

    def validate_target(self, value):
        """Verifica che il target sia online"""
        if value.status != "online":
            raise serializers.ValidationError(
                f"Il target deve essere online per aggiungere regole (stato attuale: {value.status})"
            )
        return value

    def validate(self, data):
        """Validazione incrociata"""
        chain = data.get("chain")
        source_ip = data.get("source_ip")
        dest_ip = data.get("dest_ip")

        # Validazione source_ip solo per INPUT
        if source_ip and chain != "INPUT":
            raise serializers.ValidationError(
                {"source_ip": "source_ip può essere specificato solo per chain INPUT"}
            )

        # Validazione dest_ip solo per OUTPUT
        if dest_ip and chain != "OUTPUT":
            raise serializers.ValidationError(
                {"dest_ip": "dest_ip può essere specificato solo per chain OUTPUT"}
            )

        return data


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


# Note: la versione legacy di FirewallRuleSerializer/FirewallRuleListSerializer
# (Serializer plain con campi packets/bytes/synced_at che non esistono nel modello)
# è stata rimossa. Le definizioni canoniche sono quelle ModelSerializer in cima
# a questo file: erano shadowed da queste duplicate e bloccavano POST /api/rules/
# con errori "Campo obbligatorio" su campi inesistenti.


# Serializers per operazioni SSH (add/remove via comando remoto)


class AddFirewallRuleViaSSHSerializer(serializers.Serializer):
    """
    Serializer per aggiungere regola firewall via SSH
    Esegue: ssh user@target "sudo firewall-manager --add-input 80 tcp --comment 'HTTP'"
    """

    target_id = serializers.IntegerField(required=True)
    chain = serializers.ChoiceField(
        choices=["INPUT", "OUTPUT"],
        required=True,
        help_text="Chain iptables (INPUT o OUTPUT)",
    )
    port = serializers.IntegerField(
        min_value=1,
        max_value=65535,
        required=True,
        help_text="Porta da aprire/bloccare",
    )
    protocol = serializers.ChoiceField(
        choices=["tcp", "udp"], default="tcp", help_text="Protocollo di rete"
    )
    source_ip = serializers.IPAddressField(
        required=False, allow_null=True, help_text="IP sorgente (solo per INPUT)"
    )
    dest_ip = serializers.IPAddressField(
        required=False, allow_null=True, help_text="IP destinazione (solo per OUTPUT)"
    )
    comment = serializers.CharField(
        max_length=256,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Commento descrittivo",
    )

    def validate_target_id(self, value):
        """Verifica che target esista e sia online"""
        try:
            target = Target.objects.get(id=value)
            if target.status != "online":
                raise serializers.ValidationError(
                    f"Target non online (status: {target.status})"
                )
            return value
        except Target.DoesNotExist:
            raise serializers.ValidationError(f"Target {value} non trovato")

    def validate_comment(self, value):
        """Sanitizza commento per sicurezza SSH"""
        import re

        if not value:
            return ""

        # Rimuovi caratteri pericolosi per shell
        # Permetti solo: lettere, numeri, spazi, trattini, underscore, punto
        clean = re.sub(r"[^a-zA-Z0-9\s\-_\.]", "", value)
        return clean[:256]

    def validate(self, data):
        """Validazione cross-field"""
        chain = data["chain"]
        source_ip = data.get("source_ip")
        dest_ip = data.get("dest_ip")

        # source_ip solo per INPUT
        if source_ip and chain != "INPUT":
            raise serializers.ValidationError(
                {"source_ip": "source_ip può essere specificato solo per chain INPUT"}
            )

        # dest_ip solo per OUTPUT
        if dest_ip and chain != "OUTPUT":
            raise serializers.ValidationError(
                {"dest_ip": "dest_ip può essere specificato solo per chain OUTPUT"}
            )

        return data


class RemoveFirewallRuleViaSSHSerializer(serializers.Serializer):
    """
    Serializer per rimuovere regola firewall via SSH
    Esegue: ssh user@target "sudo firewall-manager --remove INPUT 5"
    """

    target_id = serializers.IntegerField(required=True)
    chain = serializers.ChoiceField(
        choices=["INPUT", "OUTPUT", "FORWARD"], required=True
    )
    rule_number = serializers.IntegerField(
        min_value=1, required=True, help_text="Numero della regola da rimuovere"
    )

    def validate_target_id(self, value):
        """Verifica che target esista e sia online"""
        try:
            target = Target.objects.get(id=value)
            if target.status != "online":
                raise serializers.ValidationError(
                    f"Target non online (status: {target.status})"
                )
            return value
        except Target.DoesNotExist:
            raise serializers.ValidationError(f"Target {value} non trovato")

"""
Serializers per l'app Targets
"""

from rest_framework import serializers
from .models import Target, FirewallStats, NetworkInterface


class NetworkInterfaceSerializer(serializers.ModelSerializer):
    """Serializer per le interfacce di rete (NIC) di un target — read-only,
    popolate dallo snapshot dell'agent (vedi agent_manager.consumers)."""

    target_hostname = serializers.CharField(source="target.hostname", read_only=True)

    class Meta:
        model = NetworkInterface
        fields = [
            "id",
            "target",
            "target_hostname",
            "name",
            "ip_address",
            "mac_address",
            "is_primary",
            "is_up",
            "first_seen",
            "last_seen",
        ]
        read_only_fields = fields

"""
Serializers per Whitelist e BlockedIPs
Con validazioni di sicurezza OWASP/NIST
"""
from .models import WhitelistEntry, BlockedIP
import re
import ipaddress


class TargetSerializer(serializers.ModelSerializer):
    """Serializer per il modello Target"""

    connection_string = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    target_groups = serializers.SerializerMethodField()
    # Tutte le NIC dell'host (supporto multi-homed): l'interfaccia primaria
    # (is_primary=True) è quella di ip_address/mac_address sopra, le altre
    # sono in più.
    interfaces = NetworkInterfaceSerializer(many=True, read_only=True)

    class Meta:
        model = Target
        fields = [
            "id",
            "ip_address",
            "hostname",
            "mac_address",
            "description",
            "status",
            "firedog_version",
            "ssh_port",
            "ssh_user",
            "last_seen",
            "last_fetch",
            "error_message",
            "created_at",
            "updated_at",
            "connection_string",
            "is_active",
            "target_groups",
            "interfaces",
        ]
        read_only_fields = [
            "status",
            "firedog_version",
            "last_seen",
            "last_fetch",
            "error_message",
            "created_at",
            "updated_at",
        ]

    def get_target_groups(self, obj):
        """Ritorna i TargetGroup a cui appartiene questo target"""
        return [
            {
                "id": group.id,
                "name": group.name,
                "color": group.color,
                "icon": group.icon,
            }
            for group in obj.groups.all()
        ]


class TargetListSerializer(serializers.ModelSerializer):
    """Serializer semplificato per lista targets"""

    is_active = serializers.ReadOnlyField()
    target_groups = serializers.SerializerMethodField()
    interfaces_count = serializers.SerializerMethodField()

    class Meta:
        model = Target
        fields = [
            "id",
            "ip_address",
            "hostname",
            "status",
            "firedog_version",
            "last_seen",
            "is_active",
            "target_groups",
            "interfaces_count",
        ]

    def get_interfaces_count(self, obj):
        return obj.interfaces.count()

    def get_target_groups(self, obj):
        """Ritorna i TargetGroup a cui appartiene questo target"""
        return [
            {
                "id": group.id,
                "name": group.name,
                "color": group.color,
            }
            for group in obj.groups.all()
        ]


class TargetCreateSerializer(serializers.ModelSerializer):
    """Serializer per creazione target"""

    group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
        help_text="Lista di ID dei TargetGroup a cui assegnare il target",
    )

    class Meta:
        model = Target
        fields = [
            "ip_address",
            "hostname",
            "mac_address",
            "description",
            "ssh_port",
            "ssh_user",
            "group_ids",
        ]

    def validate_ip_address(self, value):
        """Verifica che IP non sia già presente"""
        if Target.objects.filter(ip_address=value).exists():
            raise serializers.ValidationError("Questo IP è già registrato come target")
        return value

    def validate_mac_address(self, value):
        """Normalizza il MAC in lowercase con colon-separator e valida il formato."""
        if not value:
            return value
        import re

        normalized = value.strip().lower().replace("-", ":")
        if not re.fullmatch(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", normalized):
            raise serializers.ValidationError(
                "MAC address non valido (formato atteso AA:BB:CC:DD:EE:FF)"
            )
        return normalized

    def create(self, validated_data):
        """Crea target e assegna ai gruppi specificati"""
        from .models import TargetGroup

        # Estrai group_ids dai validated_data
        group_ids = validated_data.pop("group_ids", [])

        # Crea il target
        target = super().create(validated_data)

        # Assegna il target ai gruppi specificati
        if group_ids:
            groups = TargetGroup.objects.filter(id__in=group_ids)
            target.groups.set(groups)

        return target


class WhitelistEntrySerializer(serializers.ModelSerializer):
    """Serializer per WhitelistEntry"""

    target_ip = serializers.CharField(source="target.ip_address", read_only=True)
    target_hostname = serializers.CharField(source="target.hostname", read_only=True)
    is_subnet = serializers.ReadOnlyField()

    class Meta:
        model = WhitelistEntry
        fields = [
            "id",
            "target",
            "target_ip",
            "target_hostname",
            "ip_address",
            "description",
            "added_by",
            "added_at",
            "last_seen",
            "hit_count",
            "is_active",
            "is_subnet",
        ]
        read_only_fields = [
            "added_at",
            "last_seen",
            "hit_count",
        ]

    def validate_ip_address(self, value):
        """
        Valida IP o CIDR notation
        Previene injection e valori malformati
        """
        value = value.strip()

        # Validazione lunghezza
        if len(value) > 50:
            raise serializers.ValidationError("IP address troppo lungo")

        # Validazione caratteri permessi
        if not re.match(r"^[0-9a-fA-F:.\/]+$", value):
            raise serializers.ValidationError(
                "Formato non valido. Usa: 192.168.1.1 o 192.168.1.0/24"
            )

        try:
            # Controlla se è un IP o una subnet
            if "/" in value:
                # CIDR notation
                ipaddress.ip_network(value, strict=False)
            else:
                # Singolo IP
                ipaddress.ip_address(value)
        except ValueError as e:
            raise serializers.ValidationError(f"IP o subnet non valido: {str(e)}")

        return value

    def validate_description(self, value):
        """Sanitizza descrizione (anti-XSS)"""
        if value:
            # Rimuovi caratteri potenzialmente pericolosi
            value = re.sub(r'[<>\'";]', "", value)
            value = value.strip()[:512]
        return value

    def validate(self, data):
        """Validazione incrociata"""
        target = data.get("target")
        ip_address = data.get("ip_address")

        # Verifica che non esista già
        if WhitelistEntry.objects.filter(
            target=target, ip_address=ip_address, is_active=True
        ).exists():
            raise serializers.ValidationError(
                f"L'IP {ip_address} è già nella whitelist per questo target"
            )

        return data


class WhitelistEntryCreateSerializer(serializers.ModelSerializer):
    """Serializer per creazione whitelist entry"""

    class Meta:
        model = WhitelistEntry
        fields = [
            "target",
            "ip_address",
            "description",
            "added_by",
        ]

    def validate_ip_address(self, value):
        """Valida IP o CIDR"""
        value = value.strip()

        if len(value) > 50:
            raise serializers.ValidationError("IP address troppo lungo")

        if not re.match(r"^[0-9a-fA-F:.\/]+$", value):
            raise serializers.ValidationError("Formato non valido")

        try:
            if "/" in value:
                ipaddress.ip_network(value, strict=False)
            else:
                ipaddress.ip_address(value)
        except ValueError as e:
            raise serializers.ValidationError(f"IP o subnet non valido: {str(e)}")

        return value


class BlockedIPSerializer(serializers.ModelSerializer):
    """Serializer per BlockedIP"""

    target_ip = serializers.CharField(source="target.ip_address", read_only=True)
    target_hostname = serializers.CharField(source="target.hostname", read_only=True)
    is_expired = serializers.ReadOnlyField()
    is_permanent = serializers.ReadOnlyField()
    block_reason_display = serializers.CharField(
        source="get_block_reason_display", read_only=True
    )

    class Meta:
        model = BlockedIP
        fields = [
            "id",
            "target",
            "target_ip",
            "target_hostname",
            "ip_address",
            "block_reason",
            "block_reason_display",
            "description",
            "blocked_by",
            "blocked_at",
            "threat_score",
            "packet_count",
            "last_attempt",
            "expires_at",
            "is_active",
            "is_expired",
            "is_permanent",
            "unblocked_at",
            "unblocked_by",
        ]
        read_only_fields = [
            "blocked_at",
            "packet_count",
            "last_attempt",
            "unblocked_at",
            "unblocked_by",
        ]

    def validate_ip_address(self, value):
        """
        Valida IP address
        Previene injection e valori malformati
        """
        try:
            ipaddress.ip_address(value)
        except ValueError as e:
            raise serializers.ValidationError(f"IP address non valido: {str(e)}")

        return value

    def validate_threat_score(self, value):
        """Valida threat score (0-100)"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Threat score deve essere tra 0 e 100")
        return value

    def validate_description(self, value):
        """Sanitizza descrizione (anti-XSS)"""
        if value:
            value = re.sub(r'[<>\'";]', "", value)
            value = value.strip()[:1000]
        return value

    def validate(self, data):
        """Validazione incrociata"""
        target = data.get("target")
        ip_address = data.get("ip_address")

        # Verifica che non sia già bloccato
        if BlockedIP.objects.filter(
            target=target, ip_address=ip_address, is_active=True
        ).exists():
            raise serializers.ValidationError(
                f"L'IP {ip_address} è già bloccato per questo target"
            )

        # Non permettere blocco di IP privati critici
        try:
            ip = ipaddress.ip_address(ip_address)
            if ip.is_loopback:
                raise serializers.ValidationError(
                    "Non puoi bloccare indirizzi di loopback"
                )
            if str(ip).startswith("192.168.1.1"):  # Gateway comune
                raise serializers.ValidationError(
                    "Attenzione: stai per bloccare un probabile gateway"
                )
        except ValueError:
            pass

        return data


class BlockedIPCreateSerializer(serializers.ModelSerializer):
    """Serializer per creazione blocco IP"""

    class Meta:
        model = BlockedIP
        fields = [
            "target",
            "ip_address",
            "block_reason",
            "description",
            "blocked_by",
            "threat_score",
            "expires_at",
        ]

    def validate_ip_address(self, value):
        """Valida IP"""
        try:
            ipaddress.ip_address(value)
        except ValueError as e:
            raise serializers.ValidationError(f"IP address non valido: {str(e)}")
        return value


class BlockedIPStatsSerializer(serializers.Serializer):
    """Serializer per statistiche IP bloccati"""

    total_blocked = serializers.IntegerField()
    active_blocks = serializers.IntegerField()
    expired_blocks = serializers.IntegerField()
    manual_blocks = serializers.IntegerField()
    automatic_blocks = serializers.IntegerField()
    total_packets_blocked = serializers.IntegerField()
    top_blocked_ips = serializers.ListField(child=serializers.DictField())
    blocks_by_reason = serializers.DictField()


class FirewallStatsSerializer(serializers.ModelSerializer):
    """Serializer per statistiche firewall (traffico)"""

    target_hostname = serializers.CharField(source="target.hostname", read_only=True)

    class Meta:
        model = FirewallStats
        fields = [
            "id",
            "target",
            "target_hostname",
            "hostname",
            "firedog_version",
            "os_version",
            "kernel_version",
            "uptime_seconds",
            "input_packets",
            "output_packets",
            "forward_packets",
            "pcap_input_dropped_bytes",
            "pcap_output_dropped_bytes",
            "dropped_input_packets",
            "dropped_output_packets",
            "protocols",
            "conntrack_count",
            "conntrack_max",
            "status",
            "collected_at",
            "imported_at",
        ]
        read_only_fields = ["id", "imported_at"]



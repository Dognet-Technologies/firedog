"""
Serializers per agent_manager app
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_ipv46_address
from rest_framework import serializers

from rules.models import FirewallRule, validate_interface_name, validate_rule_comment

from .models import (
    AgentAPIKey,
    PairingSession,
    AgentConnection,
    AgentCommand,
    AgentHeartbeat,
)

_VALID_CHAINS = {c for c, _ in FirewallRule.CHAIN_CHOICES}
_VALID_PROTOCOLS = {c for c, _ in FirewallRule.PROTOCOL_CHOICES}
_VALID_RULE_ACTIONS = {c for c, _ in FirewallRule.ACTION_CHOICES}
_VALID_COMMAND_ACTIONS = {c for c, _ in AgentCommand.ACTION_CHOICES}

# Campi ammessi per i payload di update_config/update_pcap_config inviati
# tramite questo endpoint generico — stessi nomi già validati su
# TargetViewSet.update_threat_config/update_pcap_config, qui serve solo a
# impedire che un payload completamente fuori forma arrivi all'agent
# passando da questo endpoint invece di quelli dedicati.
_KNOWN_PAYLOAD_KEYS = {
    "update_config": {
        "auto_block_threshold", "auto_block_enabled",
        "bruteforce_min_attempts", "bruteforce_score_per_attempt",
        "synflood_min_connections", "synflood_score_per_conn",
    },
    "update_pcap_config": {
        "pcap_save_path", "pcap_analysis_tool",
        "pcap_custom_filters", "pcap_threat_commands",
    },
}


def _validate_ip_value(value, field_name):
    try:
        validate_ipv46_address(value)
    except DjangoValidationError:
        raise ValueError(f"{field_name} non è un IP valido: {value!r}")


def _validate_port_value(value, field_name):
    if isinstance(value, bool) or not isinstance(value, int) or not (1 <= value <= 65535):
        raise ValueError(f"{field_name} non è una porta valida: {value!r}")


def _validate_rule_payload(payload):
    if "chain" in payload and payload["chain"] not in _VALID_CHAINS:
        raise ValueError(f"chain non valida: {payload['chain']!r}")
    if "protocol" in payload and payload["protocol"] is not None and payload["protocol"] not in _VALID_PROTOCOLS:
        raise ValueError(f"protocol non valido: {payload['protocol']!r}")
    if "action" in payload and payload["action"] is not None and payload["action"] not in _VALID_RULE_ACTIONS:
        raise ValueError(f"action non valida: {payload['action']!r}")
    interface = payload.get("interface")
    if interface:
        try:
            validate_interface_name(str(interface))
        except DjangoValidationError:
            raise ValueError(f"interface non valida: {interface!r}")
    comment = payload.get("comment")
    if comment:
        try:
            validate_rule_comment(comment)
        except DjangoValidationError as e:
            raise ValueError(f"comment non valido: {e.messages[0]}")
    for ip_field in ("src_ip", "dst_ip"):
        if payload.get(ip_field):
            _validate_ip_value(payload[ip_field], ip_field)
    for port_field in ("src_port", "dst_port"):
        if payload.get(port_field) is not None:
            _validate_port_value(payload[port_field], port_field)
    rule_num = payload.get("rule_num")
    if rule_num is not None and (isinstance(rule_num, bool) or not isinstance(rule_num, int) or rule_num < 1):
        raise ValueError(f"rule_num non valido: {rule_num!r}")


def _validate_block_payload(payload):
    ip = payload.get("ip")
    if not ip:
        raise ValueError("ip è obbligatorio")
    _validate_ip_value(ip, "ip")
    direction = payload.get("direction", "INPUT")
    if not isinstance(direction, str) or direction.upper() not in {"INPUT", "OUTPUT", "BOTH"}:
        raise ValueError(f"direction non valida: {direction!r}")


def _validate_check_integrity_payload(payload):
    paths = payload.get("paths")
    if paths is not None and (
        not isinstance(paths, list) or not all(isinstance(p, str) for p in paths)
    ):
        raise ValueError("paths deve essere una lista di stringhe")


def _validate_known_keys(payload, action):
    unknown = set(payload) - _KNOWN_PAYLOAD_KEYS[action]
    if unknown:
        raise ValueError(f"campi non riconosciuti per {action}: {sorted(unknown)}")


def validate_command_payload(action, payload):
    """Valida `payload` per `action` secondo lo stesso schema già
    applicato al path dedicato (rules/views.py → rules/services.py) —
    riusabile sia dal serializer (AgentCommandViewSet.create) sia da
    send_to_group, che altrimenti costruiva AgentCommand direttamente
    bypassando ogni validazione (HIGH trovato in code review, 2026-11).
    Solleva ValueError con un messaggio leggibile se non valido."""
    if action not in _VALID_COMMAND_ACTIONS:
        raise ValueError(f"azione sconosciuta: {action!r}")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("deve essere un oggetto JSON")

    if action in ("add_rule", "remove_rule"):
        _validate_rule_payload(payload)
    elif action in ("block_ip", "unblock_ip"):
        _validate_block_payload(payload)
    elif action == "check_integrity":
        _validate_check_integrity_payload(payload)
    elif action in _KNOWN_PAYLOAD_KEYS:
        _validate_known_keys(payload, action)
    # sync_rules: nessun campo richiesto, payload ignorato dall'agent.


class AgentAPIKeySerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by", read_only=True)

    class Meta:
        model = AgentAPIKey
        fields = [
            "id",
            "key_hash",
            "is_active",
            "created_at",
            "expires_at",
            "created_by",
            "created_by_username",
            "last_used_at",
        ]
        read_only_fields = ["id", "key_hash", "created_at", "last_used_at"]


class PairingSessionSerializer(serializers.ModelSerializer):
    target_hostname = serializers.CharField(source="target.hostname", read_only=True)
    target_ip = serializers.CharField(source="target.ip_address", read_only=True)

    class Meta:
        model = PairingSession
        fields = [
            "id",
            "target",
            "target_hostname",
            "target_ip",
            "status",
            "phase_1_verified",
            "phase_2_verified",
            "agent_ip",
            "agent_hostname",
            "agent_mac",
            "error_message",
            "created_at",
            "expires_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "phase_1_verified",
            "phase_2_verified",
            "agent_ip",
            "agent_hostname",
            "agent_mac",
            "error_message",
            "created_at",
            "expires_at",
            "completed_at",
        ]


class AgentConnectionSerializer(serializers.ModelSerializer):
    target_hostname = serializers.CharField(source="target.hostname", read_only=True)
    target_ip = serializers.CharField(source="target.ip_address", read_only=True)

    class Meta:
        model = AgentConnection
        fields = [
            "target",
            "target_hostname",
            "target_ip",
            "websocket_channel",
            "is_online",
            "last_heartbeat",
            "heartbeat_interval",
            "system_info",
            "connected_at",
            "disconnected_at",
        ]
        read_only_fields = [
            "websocket_channel",
            "is_online",
            "last_heartbeat",
            "system_info",
            "connected_at",
            "disconnected_at",
        ]


class AgentCommandSerializer(serializers.ModelSerializer):
    target_hostname = serializers.CharField(source="target.hostname", read_only=True)
    target_ip = serializers.CharField(source="target.ip_address", read_only=True)

    class Meta:
        model = AgentCommand
        fields = [
            "command_id",
            "target",
            "target_hostname",
            "target_ip",
            "action",
            "payload",
            "status",
            "result",
            "error_message",
            "timeout_seconds",
            "created_at",
            "sent_at",
            "completed_at",
        ]
        read_only_fields = [
            "command_id",
            "status",
            "result",
            "error_message",
            "created_at",
            "sent_at",
            "completed_at",
        ]

    def validate(self, attrs):
        """`payload` era JSON completamente libero, forwardato all'agent
        senza alcun controllo di schema — a differenza dello stesso
        identico dato quando arriva dal path dedicato
        (rules/views.py → rules/services.py), già validato (HIGH trovato
        in code review, 2026-11)."""
        try:
            validate_command_payload(attrs.get("action"), attrs.get("payload"))
        except ValueError as e:
            raise serializers.ValidationError({"payload": str(e)})
        return attrs


class AgentHeartbeatSerializer(serializers.ModelSerializer):
    target_hostname = serializers.CharField(source="target.hostname", read_only=True)
    target_ip = serializers.CharField(source="target.ip_address", read_only=True)

    class Meta:
        model = AgentHeartbeat
        fields = [
            "id",
            "target",
            "target_hostname",
            "target_ip",
            "timestamp",
            "cpu_percent",
            "memory_percent",
            "disk_percent",
            "memory_total_kb",
            "memory_used_kb",
            "disk_total_kb",
            "disk_used_kb",
            "load_avg_1m",
            "load_avg_5m",
            "load_avg_15m",
            "uptime_seconds",
            "bytes_sent",
            "bytes_recv",
            "active_rules_count",
            "blocked_ips_count",
            "raw_data",
        ]
        read_only_fields = ["id", "timestamp"]

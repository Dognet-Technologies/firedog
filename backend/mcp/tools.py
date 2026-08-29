"""
Catalogo tool MCP di FireDog — phase 1 (lettura) + phase 2 (scrittura, contratto §4/§6).

Convenzioni (contratto MCP §5):
- collezioni:   {"<plural>": [...], "total": n, "limit": l, "offset": o}
- entità:       {"<singular>": {...}}
- non trovato:  {"<singular>": null, "found": false}  (non è un errore)
- limit default 50, hard max 200; offset 0-based
- filtri multi-valore come stringa separata da virgole (es. "severities": "critical,high")

I tool di scrittura (create_rule, delete_rule, block_ip, unblock_ip) richiedono
che l'utente proprietario della API key sia superuser o nel gruppo "Admin"
(stesso RBAC di IsAdminUser sulle REST view equivalenti — la chiave MCP
impersona l'utente, i permessi non vengono allargati).
"""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_ipv46_address
from django.db import IntegrityError
from django.db.models import Count, Max

from audit.models import AuditLog
from rules.models import FirewallRule
from rules.services import dispatch_add_rule, dispatch_remove_rule
from targets.models import Alert, BlockedIP, Target, WhitelistEntry
from targets.services import record_blocked_ip
from targets.services import unblock_ip as unblock_ip_service
from threats.models import ThreatLog

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class ToolParamError(Exception):
    """Parametri del tool non validi → JSON-RPC -32602 (Invalid params)."""


class ToolPermissionError(Exception):
    """Ruolo insufficiente per il tool → risultato tools/call con isError: true."""


def _require_admin(user):
    """I tool di scrittura richiedono lo stesso RBAC di IsAdminUser (accounts.permissions)."""
    if user.is_superuser or user.groups.filter(name="Admin").exists():
        return
    raise ToolPermissionError(
        "Permesso negato: questo tool richiede il ruolo Admin."
    )


def _validate_ip(label, value):
    try:
        validate_ipv46_address(value)
    except DjangoValidationError:
        raise ToolParamError(f"{label} non è un IP valido: {value}.")


def _parse_pagination(arguments):
    """Estrae e valida limit/offset secondo il contratto (50 default, 200 max)."""
    try:
        limit = int(arguments.get("limit", DEFAULT_LIMIT))
        offset = int(arguments.get("offset", 0))
    except (TypeError, ValueError):
        raise ToolParamError("limit e offset devono essere interi.")
    if limit < 1:
        raise ToolParamError("limit deve essere >= 1.")
    if offset < 0:
        raise ToolParamError("offset deve essere >= 0.")
    return min(limit, MAX_LIMIT), offset


def _csv_values(value):
    """Filtro multi-valore passato come stringa separata da virgole."""
    return [v.strip() for v in str(value).split(",") if v.strip()]


def _validate_arguments(schema, arguments):
    """Valida gli argomenti contro l'inputSchema (additionalProperties: false)."""
    if not isinstance(arguments, dict):
        raise ToolParamError("arguments deve essere un oggetto.")
    allowed = set(schema.get("properties", {}).keys())
    unknown = set(arguments.keys()) - allowed
    if unknown:
        raise ToolParamError(f"Parametri sconosciuti: {', '.join(sorted(unknown))}.")
    for required in schema.get("required", []):
        if required not in arguments:
            raise ToolParamError(f"Parametro obbligatorio mancante: {required}.")


def _pagination_properties():
    return {
        "limit": {
            "type": "integer",
            "description": f"Numero massimo di risultati (default {DEFAULT_LIMIT}, max {MAX_LIMIT})",
        },
        "offset": {
            "type": "integer",
            "description": "Offset 0-based per la paginazione",
        },
    }


# ---------------------------------------------------------------------------
# Serializzatori leggeri (dict) per i payload dei tool
# ---------------------------------------------------------------------------


def _iso(dt):
    return dt.isoformat() if dt else None


def _target_summary(target):
    return {
        "id": target.id,
        "ip_address": target.ip_address,
        "hostname": target.hostname,
        "status": target.status,
        "connection_type": target.connection_type,
        "firedog_version": target.firedog_version,
        "last_seen": _iso(target.last_seen),
        "description": target.description,
    }


def _target_detail(target):
    data = _target_summary(target)
    data.update(
        {
            "mac_address": target.mac_address,
            "ssh_port": target.ssh_port,
            "ssh_user": target.ssh_user,
            "last_fetch": _iso(target.last_fetch),
            "error_message": target.error_message,
            "created_at": _iso(target.created_at),
            "updated_at": _iso(target.updated_at),
            "rules_count": target.firewall_rules.count(),
            "blocked_ips_count": target.blocked_ips.count(),
            "whitelist_count": target.whitelist_entries.filter(is_active=True).count(),
            "groups": list(target.groups.values_list("name", flat=True)),
        }
    )
    return data


def _rule_dict(rule):
    return {
        "id": rule.id,
        "target_id": rule.target_id,
        "target_ip": rule.target.ip_address,
        "target_hostname": rule.target.hostname,
        "chain": rule.chain,
        "rule_number": rule.rule_number,
        "protocol": rule.protocol,
        "port": rule.port,
        "source_ip": rule.source_ip,
        "dest_ip": rule.dest_ip,
        "action": rule.action,
        "comment": rule.comment,
        "is_custom": rule.is_custom,
        "is_synced": rule.is_synced,
        "created_at": _iso(rule.created_at),
        "updated_at": _iso(rule.updated_at),
    }


def _threat_dict(threat):
    return {
        "id": threat.id,
        "target_id": threat.target_id,
        "source_ip": threat.source_ip,
        "dest_port": threat.dest_port,
        "protocol": threat.protocol,
        "threat_score": threat.threat_score,
        "severity": threat.severity,
        "packet_count": threat.packet_count,
        "country_code": threat.country_code,
        "is_blocked": threat.is_blocked,
        "is_resolved": threat.is_resolved,
        "detected_at": _iso(threat.detected_at),
        "description": threat.description,
    }


def _blocked_ip_dict(entry):
    return {
        "id": entry.id,
        "target_id": entry.target_id,
        "ip_address": entry.ip_address,
        "block_reason": entry.block_reason,
        "description": entry.description,
        "blocked_by": entry.blocked_by,
        "threat_score": entry.threat_score,
        "packet_count": entry.packet_count,
        "blocked_at": _iso(entry.blocked_at),
        "expires_at": _iso(entry.expires_at),
    }


# ---------------------------------------------------------------------------
# Handler dei tool
# ---------------------------------------------------------------------------


def list_targets(user, arguments):
    limit, offset = _parse_pagination(arguments)
    qs = Target.objects.all().order_by("hostname", "ip_address")

    if arguments.get("status"):
        qs = qs.filter(status=arguments["status"])
    if arguments.get("statuses"):
        qs = qs.filter(status__in=_csv_values(arguments["statuses"]))
    if arguments.get("connection_type"):
        qs = qs.filter(connection_type=arguments["connection_type"])
    if arguments.get("hostname"):
        qs = qs.filter(hostname__icontains=arguments["hostname"])
    if arguments.get("ip_address"):
        qs = qs.filter(ip_address=arguments["ip_address"])

    total = qs.count()
    targets = [_target_summary(t) for t in qs[offset : offset + limit]]
    return {"targets": targets, "total": total, "limit": limit, "offset": offset}


def get_target(user, arguments):
    lookups = {
        k: arguments[k] for k in ("id", "ip_address", "hostname") if arguments.get(k)
    }
    if len(lookups) != 1:
        raise ToolParamError(
            "Specificare esattamente uno tra: id, ip_address, hostname."
        )

    key, value = next(iter(lookups.items()))
    if key == "id":
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ToolParamError("id deve essere un intero.")

    target = Target.objects.filter(**{key: value}).first()
    if target is None:
        return {"target": None, "found": False}
    return {"target": _target_detail(target)}


def list_rules(user, arguments):
    limit, offset = _parse_pagination(arguments)
    qs = FirewallRule.objects.select_related("target").order_by(
        "target_id", "chain", "rule_number"
    )

    if arguments.get("target_id"):
        try:
            qs = qs.filter(target_id=int(arguments["target_id"]))
        except (TypeError, ValueError):
            raise ToolParamError("target_id deve essere un intero.")
    if arguments.get("chain"):
        qs = qs.filter(chain=str(arguments["chain"]).upper())
    if arguments.get("action"):
        qs = qs.filter(action=str(arguments["action"]).upper())
    if arguments.get("actions"):
        qs = qs.filter(
            action__in=[a.upper() for a in _csv_values(arguments["actions"])]
        )
    if arguments.get("protocol"):
        qs = qs.filter(protocol=str(arguments["protocol"]).lower())
    if arguments.get("port"):
        try:
            qs = qs.filter(port=int(arguments["port"]))
        except (TypeError, ValueError):
            raise ToolParamError("port deve essere un intero.")
    if arguments.get("source_ip"):
        qs = qs.filter(source_ip=arguments["source_ip"])
    if "is_custom" in arguments:
        qs = qs.filter(is_custom=bool(arguments["is_custom"]))
    if "is_synced" in arguments:
        qs = qs.filter(is_synced=bool(arguments["is_synced"]))

    total = qs.count()
    rules = [_rule_dict(r) for r in qs[offset : offset + limit]]
    return {"rules": rules, "total": total, "limit": limit, "offset": offset}


def get_rule(user, arguments):
    try:
        rule_id = int(arguments["id"])
    except (TypeError, ValueError):
        raise ToolParamError("id deve essere un intero.")

    rule = FirewallRule.objects.select_related("target").filter(id=rule_id).first()
    if rule is None:
        return {"rule": None, "found": False}
    return {"rule": _rule_dict(rule)}


def list_threats(user, arguments):
    limit, offset = _parse_pagination(arguments)
    qs = ThreatLog.objects.order_by("-detected_at")

    if arguments.get("severity"):
        qs = qs.filter(severity=arguments["severity"])
    if arguments.get("severities"):
        qs = qs.filter(severity__in=_csv_values(arguments["severities"]))
    if arguments.get("target_id"):
        try:
            qs = qs.filter(target_id=int(arguments["target_id"]))
        except (TypeError, ValueError):
            raise ToolParamError("target_id deve essere un intero.")
    if arguments.get("source_ip"):
        qs = qs.filter(source_ip=arguments["source_ip"])
    if "is_blocked" in arguments:
        qs = qs.filter(is_blocked=bool(arguments["is_blocked"]))
    if "is_resolved" in arguments:
        qs = qs.filter(is_resolved=bool(arguments["is_resolved"]))
    if arguments.get("min_score"):
        try:
            qs = qs.filter(threat_score__gte=int(arguments["min_score"]))
        except (TypeError, ValueError):
            raise ToolParamError("min_score deve essere un intero.")

    total = qs.count()
    threats = [_threat_dict(t) for t in qs[offset : offset + limit]]
    return {"threats": threats, "total": total, "limit": limit, "offset": offset}


def list_blocked_ips(user, arguments):
    limit, offset = _parse_pagination(arguments)
    qs = BlockedIP.objects.order_by("-blocked_at")

    if arguments.get("target_id"):
        try:
            qs = qs.filter(target_id=int(arguments["target_id"]))
        except (TypeError, ValueError):
            raise ToolParamError("target_id deve essere un intero.")
    if arguments.get("ip_address"):
        qs = qs.filter(ip_address=arguments["ip_address"])
    if arguments.get("block_reason"):
        qs = qs.filter(block_reason=arguments["block_reason"])

    total = qs.count()
    blocked = [_blocked_ip_dict(b) for b in qs[offset : offset + limit]]
    return {"blocked_ips": blocked, "total": total, "limit": limit, "offset": offset}


def get_policy_summary(user, arguments):
    targets_by_status = dict(
        Target.objects.values_list("status").annotate(count=Count("id"))
    )
    rules_by_chain = dict(
        FirewallRule.objects.values_list("chain").annotate(count=Count("id"))
    )
    rules_by_action = dict(
        FirewallRule.objects.values_list("action").annotate(count=Count("id"))
    )
    exposed_ports = sorted(
        FirewallRule.objects.filter(chain="INPUT", action="ACCEPT", port__isnull=False)
        .values_list("port", flat=True)
        .distinct()
    )
    return {
        "targets": {
            "total": Target.objects.count(),
            "by_status": targets_by_status,
        },
        "rules": {
            "total": FirewallRule.objects.count(),
            "by_chain": rules_by_chain,
            "by_action": rules_by_action,
            "unsynced": FirewallRule.objects.filter(is_synced=False).count(),
        },
        "exposed_ports": exposed_ports,
        "blocked_ips_total": BlockedIP.objects.count(),
        "whitelist_active": WhitelistEntry.objects.filter(is_active=True).count(),
        "alerts_unacknowledged": Alert.objects.filter(acknowledged=False).count(),
        "last_sync": _iso(Target.objects.aggregate(m=Max("last_fetch"))["m"]),
    }


# ---------------------------------------------------------------------------
# Handler dei tool di scrittura (phase 2)
# ---------------------------------------------------------------------------


def _get_target_or_raise(arguments):
    try:
        target_id = int(arguments["target_id"])
    except (TypeError, ValueError):
        raise ToolParamError("target_id deve essere un intero.")
    target = Target.objects.filter(id=target_id).first()
    if target is None:
        raise ToolParamError(f"Target {target_id} non trovato.")
    return target


def create_rule(user, arguments):
    _require_admin(user)
    target = _get_target_or_raise(arguments)

    chain = str(arguments["chain"]).upper()
    if chain not in dict(FirewallRule.CHAIN_CHOICES):
        raise ToolParamError(
            f"chain non valida: {chain}. Valori ammessi: "
            f"{', '.join(c for c, _ in FirewallRule.CHAIN_CHOICES)}."
        )

    protocol = str(arguments.get("protocol", "tcp")).lower()
    if protocol not in dict(FirewallRule.PROTOCOL_CHOICES):
        raise ToolParamError(
            f"protocol non valido: {protocol}. Valori ammessi: "
            f"{', '.join(c for c, _ in FirewallRule.PROTOCOL_CHOICES)}."
        )

    action = str(arguments.get("action", "ACCEPT")).upper()
    if action not in dict(FirewallRule.ACTION_CHOICES):
        raise ToolParamError(
            f"action non valida: {action}. Valori ammessi: "
            f"{', '.join(c for c, _ in FirewallRule.ACTION_CHOICES)}."
        )

    port = arguments.get("port")
    if port is not None:
        try:
            port = int(port)
        except (TypeError, ValueError):
            raise ToolParamError("port deve essere un intero.")
        if not (1 <= port <= 65535):
            raise ToolParamError("port deve essere compreso tra 1 e 65535.")

    source_ip = arguments.get("source_ip") or None
    dest_ip = arguments.get("dest_ip") or None
    if source_ip:
        _validate_ip("source_ip", source_ip)
    if dest_ip:
        _validate_ip("dest_ip", dest_ip)

    comment = str(arguments.get("comment", ""))[:256]

    rule = FirewallRule.objects.create(
        target=target,
        chain=chain,
        protocol=protocol,
        port=port,
        source_ip=source_ip,
        dest_ip=dest_ip,
        action=action,
        comment=comment,
        is_custom=True,
        is_synced=False,
    )
    dispatched = dispatch_add_rule(rule)

    AuditLog.log_action(
        action="create",
        description=f"MCP: creata regola {rule.rule_description} su {target}",
        user=user,
        content_object=rule,
        new_values={
            "chain": chain, "protocol": protocol, "port": port,
            "source_ip": source_ip, "dest_ip": dest_ip, "action": action,
        },
    )
    logger.info(
        "MCP create_rule: rule %s creata da %s su target %s (dispatched=%s)",
        rule.id, user, target.id, dispatched,
    )
    return {"rule": _rule_dict(rule), "dispatched_to_agent": dispatched}


def delete_rule(user, arguments):
    _require_admin(user)
    try:
        rule_id = int(arguments["id"])
    except (TypeError, ValueError):
        raise ToolParamError("id deve essere un intero.")

    rule = FirewallRule.objects.select_related("target").filter(id=rule_id).first()
    if rule is None:
        return {"deleted": False, "found": False}

    target = rule.target
    rule_number = rule.rule_number
    chain = rule.chain
    rule_desc = rule.rule_description
    rule.delete()
    dispatched = dispatch_remove_rule(target, chain, rule_number)

    AuditLog.log_action(
        action="delete",
        description=f"MCP: eliminata regola {rule_desc} su {target}",
        user=user,
        old_values={"id": rule_id, "chain": chain, "rule_number": rule_number},
    )
    logger.info(
        "MCP delete_rule: rule %s eliminata da %s (dispatched=%s)",
        rule_id, user, dispatched,
    )
    return {"deleted": True, "found": True, "dispatched_to_agent": dispatched}


def block_ip(user, arguments):
    _require_admin(user)
    target = _get_target_or_raise(arguments)

    ip_address = arguments.get("ip_address")
    if not ip_address:
        raise ToolParamError("ip_address è obbligatorio.")
    _validate_ip("ip_address", ip_address)

    block_reason = str(arguments.get("block_reason", "manual"))
    if block_reason not in dict(BlockedIP.BLOCK_REASON_CHOICES):
        raise ToolParamError(
            f"block_reason non valido: {block_reason}. Valori ammessi: "
            f"{', '.join(c for c, _ in BlockedIP.BLOCK_REASON_CHOICES)}."
        )

    try:
        block = BlockedIP.objects.create(
            target=target,
            ip_address=ip_address,
            block_reason=block_reason,
            description=str(arguments.get("description", "")),
            blocked_by=f"mcp:{user.username}",
            threat_score=int(arguments.get("threat_score", 0) or 0),
        )
    except IntegrityError:
        raise ToolParamError(
            f"{ip_address} è già bloccato su questo target (record esistente)."
        )

    record_blocked_ip(block, user=user)
    logger.info(
        "MCP block_ip: %s bloccato su target %s da %s", ip_address, target.id, user
    )
    return {"blocked_ip": _blocked_ip_dict(block)}


def unblock_ip(user, arguments):
    _require_admin(user)
    try:
        block_id = int(arguments["id"])
    except (TypeError, ValueError):
        raise ToolParamError("id deve essere un intero.")

    block = BlockedIP.objects.filter(id=block_id).first()
    if block is None:
        return {"unblocked": False, "found": False}

    unblocked = unblock_ip_service(block, user=user)
    return {"unblocked": unblocked, "found": True, "blocked_ip": _blocked_ip_dict(block)}


# ---------------------------------------------------------------------------
# Registro dei tool esposti da tools/list e tools/call
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "list_targets",
        "description": (
            "Elenca gli host gestiti da FireDog (target firewall), ordinati per hostname. "
            "Espone: id, ip_address, hostname, status (online/offline/error), "
            "connection_type, firedog_version, last_seen. Filtri: status, statuses (csv), "
            "connection_type, hostname (substring), ip_address."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filtro stato esatto (es. online)",
                },
                "statuses": {
                    "type": "string",
                    "description": "Stati multipli separati da virgola",
                },
                "connection_type": {
                    "type": "string",
                    "description": "Tipo di connessione al target",
                },
                "hostname": {
                    "type": "string",
                    "description": "Match parziale sull'hostname",
                },
                "ip_address": {"type": "string", "description": "Indirizzo IP esatto"},
                **_pagination_properties(),
            },
            "additionalProperties": False,
        },
        "handler": list_targets,
    },
    {
        "name": "get_target",
        "description": (
            "Dettaglio di un singolo target con stato di connettività (status, last_seen, "
            "last_fetch, error_message), conteggi regole/IP bloccati/whitelist e gruppi. "
            "Specificare esattamente uno tra: id, ip_address, hostname."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "ID del target"},
                "ip_address": {"type": "string", "description": "IP esatto del target"},
                "hostname": {
                    "type": "string",
                    "description": "Hostname esatto del target",
                },
            },
            "additionalProperties": False,
        },
        "handler": get_target,
    },
    {
        "name": "list_rules",
        "description": (
            "Elenca le regole firewall iptables sui target. Espone: id, target, chain "
            "(INPUT/OUTPUT/FORWARD), protocol, port, source_ip, dest_ip, action "
            "(ACCEPT/DROP/REJECT), is_custom, is_synced. Filtri: target_id, chain, action, "
            "actions (csv), protocol, port, source_ip, is_custom, is_synced."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_id": {"type": "integer", "description": "Limita a un target"},
                "chain": {
                    "type": "string",
                    "description": "Chain iptables (INPUT/OUTPUT/FORWARD)",
                },
                "action": {
                    "type": "string",
                    "description": "Azione esatta (ACCEPT/DROP/REJECT)",
                },
                "actions": {
                    "type": "string",
                    "description": "Azioni multiple separate da virgola",
                },
                "protocol": {
                    "type": "string",
                    "description": "Protocollo (tcp/udp/icmp/all)",
                },
                "port": {"type": "integer", "description": "Porta esatta"},
                "source_ip": {"type": "string", "description": "IP sorgente esatto"},
                "is_custom": {
                    "type": "boolean",
                    "description": "Solo regole create da FireDog",
                },
                "is_synced": {
                    "type": "boolean",
                    "description": "Stato sincronizzazione col target",
                },
                **_pagination_properties(),
            },
            "additionalProperties": False,
        },
        "handler": list_rules,
    },
    {
        "name": "get_rule",
        "description": "Dettaglio di una singola regola firewall per id (tutti i campi della regola).",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "ID della regola"}},
            "required": ["id"],
            "additionalProperties": False,
        },
        "handler": get_rule,
    },
    {
        "name": "list_threats",
        "description": (
            "Elenca le minacce rilevate (pacchetti bloccati dal firewall), ordinate per "
            "detected_at discendente. Espone: source_ip, dest_port, protocol, threat_score, "
            "severity, packet_count, country_code, is_blocked, is_resolved. Filtri: severity, "
            "severities (csv), target_id, source_ip, is_blocked, is_resolved, min_score."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "description": "Severità esatta"},
                "severities": {
                    "type": "string",
                    "description": "Severità multiple separate da virgola",
                },
                "target_id": {"type": "integer", "description": "Limita a un target"},
                "source_ip": {"type": "string", "description": "IP sorgente esatto"},
                "is_blocked": {
                    "type": "boolean",
                    "description": "Solo minacce già bloccate",
                },
                "is_resolved": {
                    "type": "boolean",
                    "description": "Solo minacce risolte",
                },
                "min_score": {"type": "integer", "description": "Threat score minimo"},
                **_pagination_properties(),
            },
            "additionalProperties": False,
        },
        "handler": list_threats,
    },
    {
        "name": "list_blocked_ips",
        "description": (
            "Elenca gli IP bloccati sui target, ordinati per blocked_at discendente. "
            "Espone: ip_address, block_reason, threat_score, packet_count, blocked_by, "
            "blocked_at, expires_at. Filtri: target_id, ip_address, block_reason."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_id": {"type": "integer", "description": "Limita a un target"},
                "ip_address": {"type": "string", "description": "IP esatto"},
                "block_reason": {"type": "string", "description": "Motivo del blocco"},
                **_pagination_properties(),
            },
            "additionalProperties": False,
        },
        "handler": list_blocked_ips,
    },
    {
        "name": "get_policy_summary",
        "description": (
            "Rollup aggregato della postura firewall: target per stato, regole per "
            "chain/azione, regole non sincronizzate (drift), porte esposte (INPUT ACCEPT), "
            "totale IP bloccati, whitelist attive, alert non riconosciuti, ultimo sync."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "handler": get_policy_summary,
    },
    {
        "name": "create_rule",
        "description": (
            "[Admin] Crea una regola firewall custom su un target e la invia "
            "all'agent via WebSocket (se connesso, altrimenti resta is_synced=false "
            "in attesa di riconciliazione). Richiede target_id e chain; protocol "
            "default tcp, action default ACCEPT."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_id": {"type": "integer", "description": "ID del target"},
                "chain": {
                    "type": "string",
                    "description": "Chain iptables (INPUT/OUTPUT/FORWARD)",
                },
                "protocol": {
                    "type": "string",
                    "description": "Protocollo (tcp/udp/icmp/all), default tcp",
                },
                "port": {"type": "integer", "description": "Porta di destinazione (1-65535)"},
                "source_ip": {"type": "string", "description": "IP sorgente"},
                "dest_ip": {"type": "string", "description": "IP destinazione"},
                "action": {
                    "type": "string",
                    "description": "Azione (ACCEPT/DROP/REJECT), default ACCEPT",
                },
                "comment": {"type": "string", "description": "Commento descrittivo"},
            },
            "required": ["target_id", "chain"],
            "additionalProperties": False,
        },
        "handler": create_rule,
    },
    {
        "name": "delete_rule",
        "description": (
            "[Admin] Elimina una regola firewall per id e chiede all'agent di "
            "rimuoverla dal target (se connesso). found=false se l'id non esiste "
            "(non è un errore)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "ID della regola"}},
            "required": ["id"],
            "additionalProperties": False,
        },
        "handler": delete_rule,
    },
    {
        "name": "block_ip",
        "description": (
            "[Admin] Registra il blocco di un IP su un target: crea il record "
            "BlockedIP e, se block_reason non è 'manual', un ThreatLog companion. "
            "Nota: è un record di tracking/audit, non applica di per sé una regola "
            "iptables sul target — abbinare a create_rule (action=DROP) per "
            "l'enforcement effettivo."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_id": {"type": "integer", "description": "ID del target"},
                "ip_address": {"type": "string", "description": "IP da bloccare"},
                "block_reason": {
                    "type": "string",
                    "description": (
                        "Motivo (manual/threat_detected/port_scan/brute_force/"
                        "syn_flood/ddos/malware/other), default manual"
                    ),
                },
                "description": {"type": "string", "description": "Descrizione del blocco"},
                "threat_score": {
                    "type": "integer",
                    "description": "Score minaccia 0-100, default 0",
                },
            },
            "required": ["target_id", "ip_address"],
            "additionalProperties": False,
        },
        "handler": block_ip,
    },
    {
        "name": "unblock_ip",
        "description": (
            "[Admin] Sblocca un BlockedIP per id (is_active=false). "
            "unblocked=false se era già sbloccato, found=false se l'id non esiste."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "ID del BlockedIP"}},
            "required": ["id"],
            "additionalProperties": False,
        },
        "handler": unblock_ip,
    },
]

TOOLS_BY_NAME = {tool["name"]: tool for tool in TOOLS}


def public_tool_list():
    """Catalogo per tools/list: solo name, description, inputSchema."""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["inputSchema"],
        }
        for t in TOOLS
    ]


def call_tool(name, arguments, user):
    """
    Esegue un tool. Solleva ToolParamError per tool sconosciuto o argomenti
    non validi (→ -32602); ogni altra eccezione è un errore di esecuzione
    che il chiamante deve mappare su isError: true.
    """
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        raise ToolParamError(f"Tool sconosciuto: {name}.")
    arguments = arguments or {}
    _validate_arguments(tool["inputSchema"], arguments)
    return tool["handler"](user, arguments)

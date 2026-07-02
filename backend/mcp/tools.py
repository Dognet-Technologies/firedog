"""
Catalogo tool MCP di FireDog — phase 1, solo lettura (contratto §4/§6).

Convenzioni (contratto MCP §5):
- collezioni:   {"<plural>": [...], "total": n, "limit": l, "offset": o}
- entità:       {"<singular>": {...}}
- non trovato:  {"<singular>": null, "found": false}  (non è un errore)
- limit default 50, hard max 200; offset 0-based
- filtri multi-valore come stringa separata da virgole (es. "severities": "critical,high")
"""

import logging

from django.db.models import Count, Max

from rules.models import FirewallRule
from targets.models import Alert, BlockedIP, Target, WhitelistEntry
from threats.models import ThreatLog

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class ToolParamError(Exception):
    """Parametri del tool non validi → JSON-RPC -32602 (Invalid params)."""


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

"""Salvataggio delle minacce che arrivano dai target e invio degli alert.

Due sorgenti, una sola regola:
- threat_log dell'agent (dog_agent: brute-force SSH, SYN flood), ogni 60 s;
- threats dello snapshot di firewall-manager (IP visti nel pcap dei drop).

Una minaccia è una riga per (target, IP sorgente) finché non viene risolta:
i reinvii aggiornano score e dettagli. L'alert parte quando la riga nasce già
high/critical o quando la sua severità sale, mai a ogni reinvio (l'agent
ripete le stesse minacce a ogni scansione).
"""

import ipaddress
import logging

from .models import ThreatLog

logger = logging.getLogger(__name__)

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
ALERT_SEVERITIES = ("high", "critical")

# ThreatType di dog_agent (SCREAMING_SNAKE_CASE) → reason salvata nel ThreatLog.
AGENT_THREAT_REASONS = {
    "BRUTE_FORCE": "brute_force",
    "SYN_FLOOD": "syn_flood",
    "PORT_SCAN": "port_scan",
    "UNKNOWN_TRAFFIC": "unknown_traffic",
}
VALID_PROTOCOLS = ("tcp", "udp", "icmp")
MAX_DESCRIPTION = 512


def severity_for_score(score: int) -> str:
    """Stesse soglie di ThreatLog.severity_level."""
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def clamp_score(value) -> int | None:
    try:
        return max(0, min(100, int(value or 0)))
    except (TypeError, ValueError):
        return None


def valid_ip(value) -> str | None:
    try:
        return str(ipaddress.ip_address(str(value).strip()))
    except ValueError:
        return None


def upsert_threat(target, source_ip: str, defaults: dict) -> tuple[ThreatLog, bool]:
    """Crea o aggiorna la minaccia aperta per (target, IP). Ritorna la riga e
    se è nuova o più grave di prima (cioè se merita un alert)."""
    previous = (
        ThreatLog.objects.filter(target=target, source_ip=source_ip, is_resolved=False)
        .values_list("severity", flat=True)
        .first()
    )
    threat, _ = ThreatLog.objects.update_or_create(
        target=target, source_ip=source_ip, is_resolved=False, defaults=defaults
    )
    escalated = previous is None or SEVERITY_RANK.get(threat.severity, 0) > SEVERITY_RANK.get(previous, 0)
    return threat, escalated


def notify_threat(threat: ThreatLog) -> None:
    """Alert in app per le critiche, notifica (email/Slack/Discord) secondo
    la soglia di Impostazioni > Monitoraggio."""
    if threat.severity not in ALERT_SEVERITIES:
        return
    from settings.tasks import trigger_threat_alert
    from targets.models import Alert

    if threat.severity == "critical":
        Alert.objects.create(
            target=threat.target,
            severity="critical",
            title=f"Minaccia critica da {threat.source_ip}",
            message=threat.description or f"Score {threat.threat_score}/100",
        )
    try:
        trigger_threat_alert(threat)
    except Exception:  # il broker giù non deve far perdere la minaccia salvata
        logger.exception("Invio alert per la minaccia %s fallito", threat.pk)


def _agent_threat_defaults(entry: dict, score: int) -> dict:
    reason = AGENT_THREAT_REASONS.get(str(entry.get("threat_type", "")).upper(), "unknown_traffic")
    protocol = str(entry.get("protocol") or "").lower()
    try:
        dest_port = int(entry["dst_port"]) if entry.get("dst_port") else None
    except (TypeError, ValueError):
        dest_port = None
    defaults = {
        "threat_score": score,
        "severity": severity_for_score(score),
        "reasons": [reason],
        "description": str(entry.get("description") or "")[:MAX_DESCRIPTION],
        "protocol": protocol if protocol in VALID_PROTOCOLS else "",
        "dest_port": dest_port if dest_port and 0 < dest_port < 65536 else None,
    }
    # Solo True: un reinvio senza blocco non deve "sbloccare" la riga.
    if entry.get("auto_blocked") is True:
        defaults["is_blocked"] = True
    return defaults


def ingest_agent_threats(target, entries) -> int:
    """Salva le ThreatEntry di un messaggio threat_log. Ritorna quante sono
    state accettate; le voci malformate vengono scartate e registrate."""
    if not isinstance(entries, list):
        return 0
    saved = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        ip = valid_ip(entry.get("src_ip"))
        score = clamp_score(entry.get("score"))
        if ip is None or score is None:
            logger.warning("threat_log dal target %s: voce scartata (%r)", target.pk, entry.get("src_ip"))
            continue
        threat, escalated = upsert_threat(target, ip, _agent_threat_defaults(entry, score))
        saved += 1
        if escalated:
            notify_threat(threat)
    return saved

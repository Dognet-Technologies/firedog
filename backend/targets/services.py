"""
Effetti collaterali della creazione/rimozione di un BlockedIP: audit log e
ThreatLog companion.

Estratto da BlockedIPViewSet perché lo stesso comportamento serve anche ai
tool di scrittura MCP (phase 2), che non passano da una request DRF.
"""

import logging

from audit.models import AuditLog

logger = logging.getLogger("firedog.targets_api")

# Mapping reason -> (severity, threat_score) per il ThreatLog companion.
# Un blocco "manual" non genera ThreatLog: non c'è una minaccia rilevata,
# è solo una decisione dell'operatore. Le altre reason corrispondono a
# minacce reali che devono apparire in /api/threats/ per coerenza con la
# Dashboard (Recent Threats, Threat Distribution, Activity Timeline).
THREAT_FROM_REASON = {
    "ddos": ("critical", 95),
    "syn_flood": ("critical", 90),
    "malware": ("critical", 95),
    "brute_force": ("high", 80),
    "port_scan": ("high", 70),
    "threat_detected": ("high", 75),
    "other": ("low", 30),
}


def record_blocked_ip(block, *, user=None, ip_address=None):
    """Audit log + ThreatLog companion per un BlockedIP appena creato."""
    AuditLog.log_action(
        action="create",
        description=f"Blocked IP {block.ip_address} (reason: {block.block_reason})",
        user=user,
        content_object=block,
        ip_address=ip_address,
        new_values={
            "ip_address": block.ip_address,
            "target": block.target.id,
            "reason": block.block_reason,
        },
    )

    if block.block_reason != "manual":
        from threats.models import ThreatLog

        sev, score = THREAT_FROM_REASON.get(block.block_reason, ("medium", 50))
        reason_label = block.get_block_reason_display()
        ThreatLog.objects.create(
            target=block.target,
            source_ip=block.ip_address,
            threat_score=score,
            severity=sev,
            packet_count=block.packet_count or 1,
            reasons=[block.block_reason],
            description=block.description or f"{reason_label} detected from {block.ip_address}",
            is_blocked=True,
        )

    logger.warning(
        "IP blocked: %s on target %s - Reason: %s",
        block.ip_address, block.target.id, block.block_reason,
    )


def unblock_ip(block, *, user=None, ip_address=None):
    """Sblocca un BlockedIP attivo e registra l'audit log. Idempotente."""
    if not block.is_active:
        return False

    unblocked_by = getattr(user, "username", "") or ""
    block.unblock(unblocked_by=unblocked_by)

    AuditLog.log_action(
        action="update",
        description=f"Unblocked IP {block.ip_address}",
        user=user,
        content_object=block,
        ip_address=ip_address,
    )
    logger.info("IP unblocked: %s on target %s", block.ip_address, block.target.id)
    return True

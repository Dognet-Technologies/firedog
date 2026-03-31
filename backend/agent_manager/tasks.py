"""
Celery tasks per agent_manager
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from .models import AgentConnection, AgentHeartbeat, PairingSession, AgentCommand
from targets.models import Alert

logger = logging.getLogger(__name__)


@shared_task
def check_agent_health():
    """
    Verifica salute degli agent ogni 2 minuti
    Marca come offline agent senza heartbeat da 2+ minuti
    """
    threshold = timezone.now() - timedelta(minutes=2)

    offline_agents = AgentConnection.objects.filter(
        is_online=True, last_heartbeat__lt=threshold
    )

    count = 0
    for connection in offline_agents:
        connection.mark_offline()

        # Crea alert
        Alert.objects.create(
            target=connection.target,
            severity="high",
            title="Agent Offline",
            message=f"Agent {connection.target.hostname} has not sent heartbeat for more than 2 minutes",
        )

        count += 1
        logger.warning(f"Marked agent offline: {connection.target}")

    if count > 0:
        logger.info(f"Health check: Marked {count} agents offline")

    return f"Checked agent health, marked {count} offline"


@shared_task
def cleanup_old_heartbeats():
    """
    Rimuove heartbeat più vecchi di 24 ore
    Esegui ogni ora
    """
    threshold = timezone.now() - timedelta(hours=24)
    deleted_count, _ = AgentHeartbeat.objects.filter(timestamp__lt=threshold).delete()

    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} old heartbeats")

    return f"Deleted {deleted_count} old heartbeats"


@shared_task
def cleanup_expired_pairing_sessions():
    """
    Rimuove sessioni di pairing scadute più vecchie di 7 giorni
    Esegui ogni giorno
    """
    threshold = timezone.now() - timedelta(days=7)

    # Marca come expired le sessioni scadute
    expired = PairingSession.objects.filter(
        expires_at__lt=timezone.now(),
        status__in=["waiting", "verifying_api", "verifying_hash"],
    )

    for session in expired:
        session.status = "expired"
        session.save(update_fields=["status"])

        # Reset target status
        if session.target.status == "pairing":
            session.target.status = "unpaired"
            session.target.save(update_fields=["status"])

    # Elimina vecchie sessioni
    deleted_count, _ = PairingSession.objects.filter(created_at__lt=threshold).delete()

    logger.info(f"Cleaned up {deleted_count} old pairing sessions")
    return f"Deleted {deleted_count} old pairing sessions"


@shared_task
def timeout_stale_commands():
    """
    Marca come timeout comandi in esecuzione da troppo tempo
    Esegui ogni 5 minuti
    """
    count = 0

    # Trova comandi sent o executing oltre il timeout
    commands = AgentCommand.objects.filter(status__in=["sent", "executing"])

    for command in commands:
        if command.sent_at:
            elapsed = (timezone.now() - command.sent_at).total_seconds()
            if elapsed > command.timeout_seconds:
                command.mark_timeout()
                count += 1
                logger.warning(f"Command timeout: {command.command_id}")

    if count > 0:
        logger.info(f"Marked {count} commands as timeout")

    return f"Marked {count} commands as timeout"


@shared_task
def check_critical_threats():
    """
    Verifica minacce critiche e crea alert aggregati
    Esegui ogni 10 minuti
    """
    from threats.models import ThreatLog

    threshold = timezone.now() - timedelta(minutes=10)

    # Trova threat critici recenti
    critical_threats = ThreatLog.objects.filter(
        timestamp__gte=threshold, threat_score__gte=80
    ).select_related("target")

    # Raggruppa per target
    threats_by_target = {}
    for threat in critical_threats:
        target_id = threat.target_id
        if target_id not in threats_by_target:
            threats_by_target[target_id] = []
        threats_by_target[target_id].append(threat)

    # Crea alert per target con molte minacce
    alert_count = 0
    for target_id, threats in threats_by_target.items():
        if len(threats) >= 3:
            # Almeno 3 minacce critiche
            target = threats[0].target

            Alert.objects.create(
                target=target,
                severity="critical",
                title=f"Multiple Critical Threats Detected",
                message=f"{len(threats)} critical threats detected in the last 10 minutes",
            )

            alert_count += 1
            logger.warning(
                f"Created alert for {len(threats)} critical threats on {target}"
            )

    return f"Created {alert_count} threat alerts"

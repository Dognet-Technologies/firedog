"""
Celery tasks per agent_manager
"""

from celery import shared_task
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
import logging

from .models import AgentConnection, AgentHeartbeat, PairingSession, AgentCommand
from targets.models import Alert

logger = logging.getLogger(__name__)


OFFLINE_AFTER_MINUTES = 2
OFFLINE_ALERT_TITLE = "Agent Offline"
# Disconnessioni più vecchie di così non vengono segnalate: al primo avvio
# dopo l'aggiornamento non devono partire alert per target spenti da mesi.
OFFLINE_ALERT_LOOKBACK = timedelta(days=1)


@shared_task
def check_agent_health():
    """
    Ogni 2 minuti: marca offline gli agent senza heartbeat da 2+ minuti e
    segnala (Alert in app + notifica) quelli offline da 2+ minuti.

    Due casi: heartbeat scaduto con connessione ancora "online" (host
    spento di colpo) e WebSocket chiusa (consumer.disconnect → is_online
    False). Il secondo prima non veniva mai segnalato. Un riavvio
    dell'agent (si ricollega in pochi secondi) non genera alert; ogni
    disconnessione viene segnalata una volta sola.
    """
    from settings.tasks import trigger_target_offline_alert

    now = timezone.now()
    threshold = now - timedelta(minutes=OFFLINE_AFTER_MINUTES)

    stale = AgentConnection.objects.filter(
        Q(is_online=True, last_heartbeat__lt=threshold)
        | Q(is_online=False, disconnected_at__lt=threshold, disconnected_at__gte=now - OFFLINE_ALERT_LOOKBACK)
    ).select_related("target")

    count = 0
    for connection in stale:
        if connection.is_online:
            connection.mark_offline()
            logger.warning("Agent offline (heartbeat scaduto): %s", connection.target)

        since = connection.disconnected_at or threshold
        if Alert.objects.filter(
            target=connection.target, title=OFFLINE_ALERT_TITLE, created_at__gte=since
        ).exists():
            continue

        Alert.objects.create(
            target=connection.target,
            severity="high",
            title=OFFLINE_ALERT_TITLE,
            message=(
                f"L'agent di {connection.target.hostname} non risponde da più di "
                f"{OFFLINE_AFTER_MINUTES} minuti"
            ),
        )
        try:
            trigger_target_offline_alert(connection.target, OFFLINE_AFTER_MINUTES)
        except Exception:
            logger.exception("Notifica offline per %s fallita", connection.target)
        count += 1

    if count:
        logger.info("Health check: %d agent segnalati offline", count)
    return f"Checked agent health, {count} segnalati offline"


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


AGGREGATED_ALERT_TITLE = "Multiple Critical Threats Detected"
AGGREGATED_ALERT_EVERY = timedelta(hours=1)


@shared_task
def check_critical_threats():
    """
    Verifica minacce critiche e crea alert aggregati
    Esegui ogni 10 minuti
    """
    from threats.models import ThreatLog

    threshold = timezone.now() - timedelta(minutes=10)

    # Trova threat critici recenti
    # Campo reale updated_at (le minacce ancora attive vengono aggiornate a
    # ogni reinvio); "timestamp" non esiste: il task falliva sempre.
    critical_threats = ThreatLog.objects.filter(
        updated_at__gte=threshold, threat_score__gte=80, is_resolved=False
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

            # Un attacco in corso resta "recente" a ogni reinvio dell'agent:
            # un alert aggregato per target finché non viene preso in carico,
            # non uno ogni 10 minuti.
            if Alert.objects.filter(
                target=target,
                title=AGGREGATED_ALERT_TITLE,
                acknowledged=False,
                created_at__gte=timezone.now() - AGGREGATED_ALERT_EVERY,
            ).exists():
                continue

            Alert.objects.create(
                target=target,
                severity="critical",
                title=AGGREGATED_ALERT_TITLE,
                message=f"{len(threats)} critical threats detected in the last 10 minutes",
            )

            alert_count += 1
            logger.warning(
                f"Created alert for {len(threats)} critical threats on {target}"
            )

    return f"Created {alert_count} threat alerts"

"""
Celery Tasks per Notifiche
File: backend/settings/tasks.py

Tasks asincroni per invio notifiche email/Slack/Discord
"""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone
import ipaddress
import logging
import smtplib
import socket
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter

logger = logging.getLogger("firedog.notifications")


class WebhookUrlError(ValueError):
    """URL webhook non valido o che risolve a un indirizzo non consentito."""


def _is_forbidden_ip(ip) -> bool:
    if getattr(ip, "ipv4_mapped", None) is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_webhook_url(url: str):
    """Difesa SSRF sui webhook Slack/Discord configurabili dall'admin:
    richiede https, rifiuta userinfo nell'URL, risolve l'host e rifiuta
    indirizzi privati/loopback/link-local/riservati (es. 169.254.169.254,
    i metadata cloud). L'endpoint che configura questi URL è già
    Admin-only, ma un admin compromesso/ingannato non deve poter usare
    questo campo come oracolo SSRF verso la rete interna (MEDIUM trovato
    in code review, 2026-11).

    Ritorna l'IP validato: _post_webhook si connette a QUELLO, senza una
    seconda risoluzione DNS che un DNS malevolo potrebbe far puntare a un
    indirizzo interno (DNS rebinding, seconda review 2026-11)."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise WebhookUrlError("il webhook deve usare https://")
    if parsed.username or parsed.password:
        raise WebhookUrlError("userinfo non consentito nell'URL del webhook")
    hostname = parsed.hostname
    if not hostname:
        raise WebhookUrlError("host del webhook mancante")

    try:
        addrinfo = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise WebhookUrlError(f"impossibile risolvere l'host del webhook: {e}")

    ips = [ipaddress.ip_address(sockaddr[0]) for *_rest, sockaddr in addrinfo]
    for ip in ips:
        if _is_forbidden_ip(ip):
            raise WebhookUrlError(f"l'host del webhook risolve a un IP non consentito: {ip}")
    if not ips:
        raise WebhookUrlError("l'host del webhook non risolve a nessun indirizzo")
    return ips[0]


class _PinnedHostAdapter(HTTPAdapter):
    """Connessione all'IP gia' validato, con SNI e verifica del certificato
    sull'hostname originale."""

    def __init__(self, hostname, **kwargs):
        self._hostname = hostname
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["server_hostname"] = self._hostname
        kwargs["assert_hostname"] = self._hostname
        super().init_poolmanager(*args, **kwargs)


def _post_webhook(url: str, payload: dict):
    """POST JSON al webhook verso l'IP validato da _validate_webhook_url."""
    ip = _validate_webhook_url(url)
    parsed = urlparse(url)
    host = f"[{ip}]" if ip.version == 6 else str(ip)
    port = f":{parsed.port}" if parsed.port else ""
    pinned_url = parsed._replace(netloc=f"{host}{port}").geturl()
    with requests.Session() as session:
        session.trust_env = False  # niente proxy da variabili d'ambiente
        session.mount("https://", _PinnedHostAdapter(parsed.hostname))
        return session.post(
            pinned_url,
            json=payload,
            timeout=10,
            allow_redirects=False,
            headers={"Host": f"{parsed.hostname}{port}"},
        )


def _webhook_error(response) -> str:
    """Solo lo status al chiamante: il corpo della risposta di un host
    arbitrario non deve tornare indietro (oracolo SSRF). Un estratto va nel
    log."""
    logger.error("webhook HTTP %s: %s", response.status_code, response.text[:200])
    return f"Status {response.status_code}"


# ==================== EMAIL TASKS ====================


def send_email_notification(subject, message, recipients, config):
    """
    Invia notifica email usando configurazione SMTP salvata

    Args:
        subject: Oggetto email
        message: Corpo messaggio (HTML supportato)
        recipients: Lista indirizzi email
        config: Istanza NotificationConfig

    Returns:
        dict: {'success': bool, 'error': str}
    """
    try:
        # Crea messaggio
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[FireDog] {subject}"
        msg["From"] = config.smtp_from_email
        msg["To"] = ", ".join(recipients)

        # Aggiungi corpo messaggio (text + HTML)
        text_part = MIMEText(message, "plain")
        html_part = MIMEText(f"<html><body>{message}</body></html>", "html")

        msg.attach(text_part)
        msg.attach(html_part)

        # Decripta password
        smtp_password = config.get_decrypted_smtp_password()

        # Contesto TLS: di default verifica piena (comportamento storico).
        # smtp_skip_tls_verify è l'unico modo per accettare un certificato
        # self-signed o emesso da una CA privata — senza, ssl.create_default_context()
        # rifiuta la connessione con CERTIFICATE_VERIFY_FAILED e nessuna
        # combinazione di impostazioni SMTP la farebbe funzionare.
        if getattr(config, "smtp_skip_tls_verify", False):
            tls_context = ssl.create_default_context()
            tls_context.check_hostname = False
            tls_context.verify_mode = ssl.CERT_NONE
        else:
            tls_context = ssl.create_default_context()

        # Connetti e invia
        if config.smtp_use_tls:
            # TLS/STARTTLS (porta 587)
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)
            server.starttls(context=tls_context)
        else:
            # Plain o SSL (porta 25 o 465)
            if config.smtp_port == 465:
                server = smtplib.SMTP_SSL(
                    config.smtp_host,
                    config.smtp_port,
                    timeout=10,
                    context=tls_context,
                )
            else:
                server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)

        # Login solo se username e password sono forniti
        if config.smtp_user and smtp_password:
            server.login(config.smtp_user, smtp_password)

        # Invia
        server.send_message(msg)
        server.quit()

        logger.info(f"Email sent to {len(recipients)} recipients")
        return {"success": True}

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication error: {e!s}")
        return {"success": False, "error": f"Autenticazione SMTP fallita: {e!s}"}

    except ssl.SSLCertVerificationError as e:
        # Non eredita da smtplib.SMTPException: senza questo except finirebbe
        # nel generico sotto con un messaggio criptico invece di indicare la
        # causa reale e la soluzione (il campo esiste apposta per questo).
        logger.error(f"SMTP TLS certificate error: {e!s}")
        return {
            "success": False,
            "error": (
                "Certificato TLS del server SMTP non verificabile "
                "(self-signed o CA privata). Se ti fidi di questo server, "
                "abilita 'Accetta certificati TLS non verificabili' nelle "
                f"impostazioni email. Dettaglio: {e}"
            ),
        }

    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e!s}")
        return {"success": False, "error": f"Errore SMTP: {e!s}"}

    except Exception as e:
        logger.error(f"Email send error: {e!s}", exc_info=True)
        return {"success": False, "error": str(e)}


# ==================== SLACK TASKS ====================


def send_slack_notification(message, webhook_url):
    """
    Invia notifica Slack via webhook

    Args:
        message: Testo messaggio
        webhook_url: URL webhook Slack

    Returns:
        dict: {'success': bool, 'error': str}
    """
    try:
        payload = {
            "text": f":fire: *FireDog Alert*\n{message}",
            "username": "FireDog Security",
            "icon_emoji": ":dog:",
        }

        response = _post_webhook(webhook_url, payload)

        if response.status_code == 200:
            logger.info("Slack notification sent successfully")
            return {"success": True}
        else:
            error_msg = _webhook_error(response)
            logger.error(f"Slack webhook error: {error_msg}")
            return {"success": False, "error": error_msg}

    except WebhookUrlError as e:
        logger.error(f"Slack webhook URL non valido: {e}")
        return {"success": False, "error": str(e)}

    except requests.RequestException as e:
        logger.error(f"Slack request error: {e!s}")
        return {"success": False, "error": str(e)}

    except Exception as e:
        logger.error(f"Slack send error: {e!s}", exc_info=True)
        return {"success": False, "error": str(e)}


# ==================== DISCORD TASKS ====================


def send_discord_notification(message, webhook_url):
    """
    Invia notifica Discord via webhook

    Args:
        message: Testo messaggio
        webhook_url: URL webhook Discord

    Returns:
        dict: {'success': bool, 'error': str}
    """
    try:
        payload = {
            "content": f"🔥 **FireDog Alert**\n{message}",
            "username": "FireDog Security",
            "avatar_url": "https://via.placeholder.com/128/FF6B35/FFFFFF?text=FD",
        }

        response = _post_webhook(webhook_url, payload)

        if response.status_code in [200, 204]:
            logger.info("Discord notification sent successfully")
            return {"success": True}
        else:
            error_msg = _webhook_error(response)
            logger.error(f"Discord webhook error: {error_msg}")
            return {"success": False, "error": error_msg}

    except WebhookUrlError as e:
        logger.error(f"Discord webhook URL non valido: {e}")
        return {"success": False, "error": str(e)}

    except requests.RequestException as e:
        logger.error(f"Discord request error: {e!s}")
        return {"success": False, "error": str(e)}

    except Exception as e:
        logger.error(f"Discord send error: {e!s}", exc_info=True)
        return {"success": False, "error": str(e)}


# ==================== TEST TASK ====================


def send_test_notification(notification_type, test_recipient="", username="admin"):
    """
    Invia notifica di test (sincrono per feedback immediato)

    Args:
        notification_type: 'email', 'slack', 'discord'
        test_recipient: Email destinatario test (opzionale)
        username: Username utente che ha richiesto il test

    Returns:
        dict: {'success': bool, 'error': str, 'details': dict}
    """
    from settings.models import NotificationConfig, NotificationLog

    config = NotificationConfig.get_config()

    test_message = f"""
FireDog Security - Test Notification

Questo è un messaggio di test inviato da {username}.
Timestamp: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

Se ricevi questo messaggio, la configurazione è corretta!
    """.strip()

    result = {"success": False, "details": {}}

    try:
        if notification_type == "email":
            recipients = (
                [test_recipient] if test_recipient else config.email_recipients[:1]
            )

            if not recipients:
                return {"success": False, "error": "Nessun destinatario configurato"}

            result = send_email_notification(
                subject="Test Notification",
                message=test_message,
                recipients=recipients,
                config=config,
            )

            result["details"] = {
                "smtp_host": config.smtp_host,
                "smtp_port": config.smtp_port,
                "smtp_user": config.smtp_user,
                "smtp_use_tls": config.smtp_use_tls,
                "smtp_skip_tls_verify": config.smtp_skip_tls_verify,
                "recipients": recipients,
            }

            # Log
            NotificationLog.log_notification(
                notification_type="email",
                alert_type="install_success",  # Usa tipo generico per test
                recipient=", ".join(recipients),
                message=test_message,
                success=result["success"],
                error_message=result.get("error", ""),
            )

        elif notification_type == "slack":
            result = send_slack_notification(
                message=test_message, webhook_url=config.slack_webhook_url
            )

            result["details"] = {"webhook_url": config.slack_webhook_url[:50] + "..."}

            # Log
            NotificationLog.log_notification(
                notification_type="slack",
                alert_type="install_success",
                recipient=config.slack_webhook_url,
                message=test_message,
                success=result["success"],
                error_message=result.get("error", ""),
            )

        elif notification_type == "discord":
            result = send_discord_notification(
                message=test_message, webhook_url=config.discord_webhook_url
            )

            result["details"] = {"webhook_url": config.discord_webhook_url[:50] + "..."}

            # Log
            NotificationLog.log_notification(
                notification_type="discord",
                alert_type="install_success",
                recipient=config.discord_webhook_url,
                message=test_message,
                success=result["success"],
                error_message=result.get("error", ""),
            )

        return result

    except Exception as e:
        logger.error(f"Test notification error: {e!s}", exc_info=True)
        return {"success": False, "error": str(e)}


# ==================== ALERT TASKS ====================


@shared_task(bind=True, max_retries=3)
def send_alert_notification(self, alert_type, message, target_id=None):
    """
    Task Celery asincrono per inviare alert

    Args:
        alert_type: Tipo di alert (threat_critical, target_offline, etc.)
        message: Messaggio da inviare
        target_id: ID target coinvolto (opzionale)

    Returns:
        dict: Risultati invio per ogni canale
    """
    from settings.models import NotificationConfig, NotificationLog
    from targets.models import Target

    try:
        config = NotificationConfig.get_config()
        target = Target.objects.get(id=target_id) if target_id else None

        # Verifica cooldown
        if not NotificationLog.can_send_alert(alert_type, target):
            logger.info(f"Alert {alert_type} in cooldown, skipping")
            return {"skipped": True, "reason": "cooldown"}

        # Verifica se questo tipo di alert è abilitato
        alert_enabled_map = {
            "threat_critical": config.alert_on_critical_threat,
            "threat_high": config.alert_on_high_threat,
            "target_offline": config.alert_on_target_offline,
            "ssh_error": config.alert_on_ssh_error,
            "install_success": config.alert_on_install_success,
            "install_failed": config.alert_on_install_failed,
        }

        if not alert_enabled_map.get(alert_type, False):
            logger.info(f"Alert {alert_type} disabled, skipping")
            return {"skipped": True, "reason": "disabled"}

        results = {}

        # Invia via Email
        if config.email_enabled and config.email_recipients:
            email_result = send_email_notification(
                subject=f"Alert: {alert_type.replace('_', ' ').title()}",
                message=message,
                recipients=config.email_recipients,
                config=config,
            )
            results["email"] = email_result

            NotificationLog.log_notification(
                notification_type="email",
                alert_type=alert_type,
                target=target,
                recipient=", ".join(config.email_recipients),
                message=message,
                success=email_result["success"],
                error_message=email_result.get("error", ""),
            )

        # Invia via Slack
        if config.slack_enabled and config.slack_webhook_url:
            slack_result = send_slack_notification(
                message=message, webhook_url=config.slack_webhook_url
            )
            results["slack"] = slack_result

            NotificationLog.log_notification(
                notification_type="slack",
                alert_type=alert_type,
                target=target,
                recipient=config.slack_webhook_url,
                message=message,
                success=slack_result["success"],
                error_message=slack_result.get("error", ""),
            )

        # Invia via Discord
        if config.discord_enabled and config.discord_webhook_url:
            discord_result = send_discord_notification(
                message=message, webhook_url=config.discord_webhook_url
            )
            results["discord"] = discord_result

            NotificationLog.log_notification(
                notification_type="discord",
                alert_type=alert_type,
                target=target,
                recipient=config.discord_webhook_url,
                message=message,
                success=discord_result["success"],
                error_message=discord_result.get("error", ""),
            )

        logger.info(f"Alert {alert_type} sent via {len(results)} channels")
        return results

    except Exception as e:
        logger.error(f"Send alert error: {e!s}", exc_info=True)

        # Retry con backoff esponenziale
        raise self.retry(exc=e, countdown=60 * (2**self.request.retries))


# ==================== HELPER FUNCTIONS ====================


# Impostazioni > Monitoraggio > "Soglia invio alert" è su scala 1-10 nella UI,
# gli score delle minacce su 0-100: 8/10 = score >= 80.
ALERT_MIN_SCORE_DEFAULT = 8
ALERT_MIN_SCORE_RANGE = (1, 10)


def alert_min_threat_score():
    """Score minimo (0-100) sotto il quale una minaccia non genera notifiche."""
    from settings.models import SystemSettings

    raw = SystemSettings.get_setting("alertNotificationMinScore", ALERT_MIN_SCORE_DEFAULT)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = ALERT_MIN_SCORE_DEFAULT
    low, high = ALERT_MIN_SCORE_RANGE
    return max(low, min(high, value)) * 10


def trigger_threat_alert(threat):
    """
    Notifica (email/Slack/Discord) per una minaccia high/critical sopra la
    soglia di Impostazioni > Monitoraggio. Chiamata da threats.ingest al
    primo rilevamento o quando la severità sale. Ritorna True se accodata.
    """
    if threat.severity not in ("high", "critical"):
        return False
    if threat.threat_score < alert_min_threat_score():
        return False

    reasons = ", ".join(threat.reasons or []) or "n/d"
    message = f"""
⚠️ MINACCIA RILEVATA

Target: {threat.target.hostname} ({threat.target.ip_address})
Severità: {threat.severity.upper()}
Score: {threat.threat_score}/100
Tipo: {reasons}
IP sorgente: {threat.source_ip}
Rilevata: {threat.detected_at.strftime('%Y-%m-%d %H:%M:%S')}

{threat.description}
    """.strip()

    send_alert_notification.delay(
        alert_type=f"threat_{threat.severity}", message=message, target_id=threat.target.id
    )
    return True


def trigger_target_offline_alert(target, minutes):
    """Notifica target offline (chiamata da agent_manager.tasks.check_agent_health)."""
    last_seen = target.last_seen.strftime('%Y-%m-%d %H:%M:%S') if target.last_seen else "mai"
    message = f"""
🔴 TARGET OFFLINE

Hostname: {target.hostname}
IP: {target.ip_address}
Ultimo contatto: {last_seen}

L'agent non risponde da più di {minutes} minuti.
    """.strip()

    send_alert_notification.delay(
        alert_type="target_offline", message=message, target_id=target.id
    )


# ==================== CONSERVAZIONE LOG ====================

# Impostazioni > Monitoraggio > "Conservazione log (giorni)". Stesso
# intervallo accettato dalla UI e da bulk_update.
LOG_RETENTION_DEFAULT_DAYS = 30
LOG_RETENTION_RANGE = (7, 365)
# Comandi conclusi: quelli pending/sent/executing restano finché finiscono.
FINISHED_COMMAND_STATUSES = ("success", "failed", "timeout")


def log_retention_days():
    from settings.models import SystemSettings

    raw = SystemSettings.get_setting("logRetention", LOG_RETENTION_DEFAULT_DAYS)
    low, high = LOG_RETENTION_RANGE
    # bool è un int in Python: True non deve diventare "1 giorno".
    if isinstance(raw, bool):
        return LOG_RETENTION_DEFAULT_DAYS
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return LOG_RETENTION_DEFAULT_DAYS
    return max(low, min(high, days))


def _retention_querysets(cutoff):
    """Storico che cresce nel tempo. Restano: audit log, IP bloccati, regole,
    target, host scoperti (stato, non storico)."""
    from agent_manager.models import AgentCommand
    from settings.models import DatabaseCleanupLog, NotificationLog
    from targets.models import Alert, FirewallStats, NetworkFlow, Statistics
    from threats.models import ThreatLog

    return [
        # updated_at: una minaccia ancora attiva viene aggiornata a ogni reinvio.
        ThreatLog.objects.filter(updated_at__lt=cutoff),
        Alert.objects.filter(created_at__lt=cutoff),
        NotificationLog.objects.filter(sent_at__lt=cutoff),
        AgentCommand.objects.filter(created_at__lt=cutoff, status__in=FINISHED_COMMAND_STATUSES),
        Statistics.objects.filter(collected_at__lt=cutoff),
        FirewallStats.objects.filter(collected_at__lt=cutoff),
        NetworkFlow.objects.filter(last_seen__lt=cutoff),
        DatabaseCleanupLog.objects.filter(executed_at__lt=cutoff),
    ]


@shared_task
def apply_log_retention():
    """Ogni notte: cancella lo storico più vecchio di logRetention giorni.
    Ritorna il numero di righe cancellate (cascade escluse)."""
    from settings.models import DatabaseCleanupLog

    days = log_retention_days()
    cutoff = timezone.now() - timedelta(days=days)
    deleted = 0
    try:
        for queryset in _retention_querysets(cutoff):
            _, per_model = queryset.delete()
            deleted += per_model.get(queryset.model._meta.label, 0)
    except Exception as e:
        logger.exception("Conservazione log fallita")
        DatabaseCleanupLog.objects.create(
            cleanup_type="all", records_deleted=deleted, retention_days=days,
            success=False, error_message=str(e)[:500],
        )
        raise
    DatabaseCleanupLog.objects.create(
        cleanup_type="all", records_deleted=deleted, retention_days=days, success=True
    )
    logger.info("Conservazione log: %d righe più vecchie di %d giorni cancellate", deleted, days)
    return deleted

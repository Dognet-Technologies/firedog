"""
Celery Tasks per Notifiche
File: backend/settings/tasks.py

Tasks asincroni per invio notifiche email/Slack/Discord
"""

from celery import shared_task
from django.utils import timezone
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

logger = logging.getLogger("firedog.notifications")


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

        # Connetti e invia
        if config.smtp_use_tls:
            # TLS/STARTTLS (porta 587)
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)
            server.starttls()
        else:
            # Plain o SSL (porta 25 o 465)
            if config.smtp_port == 465:
                server = smtplib.SMTP_SSL(
                    config.smtp_host, config.smtp_port, timeout=10
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
        logger.error(f"SMTP Authentication error: {str(e)}")
        return {"success": False, "error": f"Autenticazione SMTP fallita: {str(e)}"}

    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {str(e)}")
        return {"success": False, "error": f"Errore SMTP: {str(e)}"}

    except Exception as e:
        logger.error(f"Email send error: {str(e)}", exc_info=True)
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

        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 200:
            logger.info("Slack notification sent successfully")
            return {"success": True}
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            logger.error(f"Slack webhook error: {error_msg}")
            return {"success": False, "error": error_msg}

    except requests.RequestException as e:
        logger.error(f"Slack request error: {str(e)}")
        return {"success": False, "error": str(e)}

    except Exception as e:
        logger.error(f"Slack send error: {str(e)}", exc_info=True)
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

        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code in [200, 204]:
            logger.info("Discord notification sent successfully")
            return {"success": True}
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            logger.error(f"Discord webhook error: {error_msg}")
            return {"success": False, "error": error_msg}

    except requests.RequestException as e:
        logger.error(f"Discord request error: {str(e)}")
        return {"success": False, "error": str(e)}

    except Exception as e:
        logger.error(f"Discord send error: {str(e)}", exc_info=True)
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
        logger.error(f"Test notification error: {str(e)}", exc_info=True)
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
        logger.error(f"Send alert error: {str(e)}", exc_info=True)

        # Retry con backoff esponenziale
        raise self.retry(exc=e, countdown=60 * (2**self.request.retries))


# ==================== HELPER FUNCTIONS ====================


def trigger_threat_alert(threat, severity):
    """
    Helper per triggerare alert da minaccia rilevata

    Args:
        threat: Istanza ThreatLog
        severity: 'CRITICAL' o 'HIGH'
    """
    from settings.models import SystemSettings

    # Verifica soglia minaccia
    threat_threshold = SystemSettings.get_setting("threatThreshold", 8)

    if threat.threat_score < threat_threshold:
        return  # Sotto soglia, non inviare alert

    alert_type = f"threat_{severity.lower()}"

    message = f"""
⚠️ THREAT DETECTED ⚠️

Target: {threat.target.hostname} ({threat.target.ip_address})
Severity: {severity}
Score: {threat.threat_score}/10
Type: {threat.threat_type}
Source IP: {threat.source_ip}
Timestamp: {threat.detected_at.strftime('%Y-%m-%d %H:%M:%S')}

Details:
{threat.description}
    """.strip()

    # Invia alert asincrono
    send_alert_notification.delay(
        alert_type=alert_type, message=message, target_id=threat.target.id
    )


def trigger_target_offline_alert(target):
    """
    Helper per triggerare alert target offline

    Args:
        target: Istanza Target
    """
    message = f"""
🔴 TARGET OFFLINE

Hostname: {target.hostname}
IP: {target.ip_address}
Last seen: {target.last_heartbeat.strftime('%Y-%m-%d %H:%M:%S') if target.last_heartbeat else 'Never'}

Il target non risponde da più di {target.heartbeat_interval} minuti.
    """.strip()

    send_alert_notification.delay(
        alert_type="target_offline", message=message, target_id=target.id
    )

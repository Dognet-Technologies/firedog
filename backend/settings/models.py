"""
Models per Settings App
Gestione configurazioni sistema
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class SystemSettings(models.Model):
    """
    Configurazioni di sistema persistenti
    Ogni impostazione è memorizzata come coppia key-value
    """

    CATEGORY_CHOICES = [
        ("general", "Generale"),
        ("appearance", "Aspetto"),
        ("notifications", "Notifiche"),
        ("security", "Sicurezza"),
        ("monitoring", "Monitoraggio"),
    ]

    key = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Chiave univoca dell'impostazione",
    )

    value = models.JSONField(help_text="Valore dell'impostazione (JSON)")

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default="general",
        help_text="Categoria dell'impostazione",
    )

    description = models.TextField(
        blank=True, help_text="Descrizione dell'impostazione"
    )

    is_public = models.BooleanField(
        default=True, help_text="Se True, visibile a tutti gli utenti autenticati"
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="settings_updates",
    )

    class Meta:
        db_table = "system_settings"
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"
        ordering = ["category", "key"]

    def __str__(self):
        return f"{self.category}.{self.key}"

    @classmethod
    def get_setting(cls, key, default=None):
        """Recupera valore impostazione"""
        try:
            setting = cls.objects.get(key=key)
            return setting.value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_setting(cls, key, value, category="general", user=None):
        """Imposta valore impostazione"""
        setting, created = cls.objects.update_or_create(
            key=key,
            defaults={
                "value": value,
                "category": category,
                "updated_by": user,
            },
        )
        return setting


class DatabaseCleanupLog(models.Model):
    """
    Log delle operazioni di pulizia database
    Traccia cosa è stato eliminato e quando
    """

    CLEANUP_TYPE_CHOICES = [
        ("audit_logs", "Audit Logs"),
        ("threat_logs", "Threat Logs"),
        ("statistics", "Statistics"),
        ("discovered_hosts", "Discovered Hosts"),
        ("all", "All"),
    ]

    cleanup_type = models.CharField(
        max_length=50,
        choices=CLEANUP_TYPE_CHOICES,
        help_text="Tipo di pulizia eseguita",
    )

    records_deleted = models.IntegerField(
        default=0, help_text="Numero di record eliminati"
    )

    retention_days = models.IntegerField(help_text="Giorni di retention applicati")

    executed_at = models.DateTimeField(auto_now_add=True)
    executed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="cleanup_executions"
    )

    success = models.BooleanField(
        default=True, help_text="Se True, operazione completata con successo"
    )

    error_message = models.TextField(
        blank=True, help_text="Messaggio di errore se success=False"
    )

    class Meta:
        db_table = "database_cleanup_logs"
        verbose_name = "Database Cleanup Log"
        verbose_name_plural = "Database Cleanup Logs"
        ordering = ["-executed_at"]

    def __str__(self):
        return f"{self.cleanup_type} - {self.executed_at.strftime('%Y-%m-%d %H:%M')}"


class NotificationConfig(models.Model):
    """
    Configurazione notifiche globali
    Singleton: esiste sempre e solo un record (pk=1)
    """

    # Email
    email_enabled = models.BooleanField(
        default=False, help_text="Abilita notifiche email"
    )

    email_recipients = models.JSONField(
        default=list, help_text="Lista indirizzi email destinatari"
    )

    # SMTP Configuration (salvate in DB)
    smtp_host = models.CharField(
        max_length=255,
        blank=True,
        default="localhost",
        help_text="Host SMTP (es. smtp.gmail.com, localhost)",
    )

    smtp_port = models.IntegerField(
        default=587,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        help_text="Porta SMTP (587 per TLS, 465 per SSL, 25 per plain)",
    )

    smtp_user = models.CharField(
        max_length=255,
        blank=True,
        default="microcyber",
        help_text="Username SMTP (es. microcyber)",
    )

    smtp_password = models.CharField(
        max_length=500, blank=True, help_text="Password SMTP (salvata encrypted)"
    )

    smtp_use_tls = models.BooleanField(
        default=True, help_text="Usa STARTTLS per connessione sicura"
    )

    smtp_from_email = models.EmailField(
        blank=True,
        default="firedog@localhost",
        help_text="Email mittente per le notifiche",
    )

    # Slack
    slack_enabled = models.BooleanField(
        default=False, help_text="Abilita notifiche Slack"
    )

    slack_webhook_url = models.URLField(
        blank=True, max_length=500, help_text="URL webhook Slack"
    )

    # Discord
    discord_enabled = models.BooleanField(
        default=False, help_text="Abilita notifiche Discord"
    )

    discord_webhook_url = models.URLField(
        blank=True, max_length=500, help_text="URL webhook Discord"
    )

    # Trigger Alerts (basati su threatThreshold in SystemSettings)
    alert_on_critical_threat = models.BooleanField(
        default=True, help_text="Invia alert per minacce critiche"
    )

    alert_on_high_threat = models.BooleanField(
        default=True, help_text="Invia alert per minacce high"
    )

    alert_on_target_offline = models.BooleanField(
        default=True, help_text="Invia alert quando target va offline"
    )

    target_offline_threshold_minutes = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Minuti prima di considerare target offline",
    )

    alert_on_ssh_error = models.BooleanField(
        default=True, help_text="Invia alert per errori SSH"
    )

    alert_on_install_success = models.BooleanField(
        default=False, help_text="Invia alert per installazioni completate"
    )

    alert_on_install_failed = models.BooleanField(
        default=True, help_text="Invia alert per installazioni fallite"
    )

    # Anti-flood
    cooldown_minutes = models.IntegerField(
        default=60,
        validators=[MinValueValidator(5), MaxValueValidator(1440)],
        help_text="Cooldown tra notifiche dello stesso tipo (minuti)",
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_config_updates",
    )

    class Meta:
        db_table = "notification_config"
        verbose_name = "Notification Configuration"
        verbose_name_plural = "Notification Configurations"

    def __str__(self):
        return f"NotificationConfig (updated: {self.updated_at})"

    @classmethod
    def get_config(cls):
        """Ottieni o crea configurazione singleton"""
        config, created = cls.objects.get_or_create(pk=1)
        return config

    def save(self, *args, **kwargs):
        """Forza pk=1 (singleton) e encrypta password"""
        self.pk = 1

        # Encrypta password SMTP se presente
        if self.smtp_password and not self.smtp_password.startswith("gAAAAAB"):
            self.smtp_password = self._encrypt_password(self.smtp_password)

        super().save(*args, **kwargs)

    def _encrypt_password(self, password):
        """Encrypta password usando Fernet (symmetric encryption)"""
        from cryptography.fernet import Fernet
        from django.conf import settings

        # Usa SECRET_KEY come base per encryption key
        key = settings.SECRET_KEY[:32].encode().ljust(32, b"0")
        from base64 import urlsafe_b64encode

        fernet_key = urlsafe_b64encode(key)

        cipher = Fernet(fernet_key)
        encrypted = cipher.encrypt(password.encode())
        return encrypted.decode()

    def get_decrypted_smtp_password(self):
        """Decripta password SMTP per uso"""
        if not self.smtp_password:
            return ""

        # Se non è encrypted, ritorna così com'è
        if not self.smtp_password.startswith("gAAAAAB"):
            return self.smtp_password

        try:
            from cryptography.fernet import Fernet
            from django.conf import settings

            key = settings.SECRET_KEY[:32].encode().ljust(32, b"0")
            from base64 import urlsafe_b64encode

            fernet_key = urlsafe_b64encode(key)

            cipher = Fernet(fernet_key)
            decrypted = cipher.decrypt(self.smtp_password.encode())
            return decrypted.decode()
        except Exception:
            return ""


class NotificationLog(models.Model):
    """
    Log delle notifiche inviate (per cooldown e audit)
    """

    NOTIFICATION_TYPE_CHOICES = [
        ("email", "Email"),
        ("slack", "Slack"),
        ("discord", "Discord"),
    ]

    ALERT_TYPE_CHOICES = [
        ("threat_critical", "Critical Threat"),
        ("threat_high", "High Threat"),
        ("target_offline", "Target Offline"),
        ("ssh_error", "SSH Error"),
        ("install_success", "Installation Success"),
        ("install_failed", "Installation Failed"),
    ]

    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES,
        help_text="Tipo di notifica inviata",
    )

    alert_type = models.CharField(
        max_length=50, choices=ALERT_TYPE_CHOICES, help_text="Tipo di alert"
    )

    target = models.ForeignKey(
        "targets.Target",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    recipient = models.CharField(
        max_length=500, help_text="Destinatario (email o webhook URL)"
    )

    message = models.TextField(help_text="Contenuto messaggio inviato")

    success = models.BooleanField(
        default=True, help_text="Se True, notifica inviata con successo"
    )

    error_message = models.TextField(
        blank=True, help_text="Messaggio di errore se success=False"
    )

    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification_logs"
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["alert_type", "sent_at"]),
            models.Index(fields=["target", "sent_at"]),
        ]

    def __str__(self):
        return f"{self.alert_type} - {self.notification_type} ({self.sent_at})"

    @classmethod
    def can_send_alert(cls, alert_type, target=None):
        """
        Verifica se può inviare alert (cooldown)
        Ritorna True se può inviare, False se è in cooldown
        """
        config = NotificationConfig.get_config()
        cooldown_minutes = config.cooldown_minutes

        cutoff_time = timezone.now() - timedelta(minutes=cooldown_minutes)

        # Controlla se esiste già un alert dello stesso tipo nel periodo di cooldown
        query = cls.objects.filter(
            alert_type=alert_type, sent_at__gte=cutoff_time, success=True
        )

        if target:
            query = query.filter(target=target)

        return not query.exists()

    @classmethod
    def log_notification(
        cls,
        notification_type,
        alert_type,
        recipient,
        message,
        target=None,
        success=True,
        error_message="",
    ):
        """Helper per creare log notifica"""
        return cls.objects.create(
            notification_type=notification_type,
            alert_type=alert_type,
            target=target,
            recipient=recipient,
            message=message,
            success=success,
            error_message=error_message,
        )

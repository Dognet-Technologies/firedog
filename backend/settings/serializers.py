"""
Serializers per Settings App
Con validazioni di sicurezza OWASP/NIST
"""

from rest_framework import serializers
from .models import SystemSettings, SSHKey, DatabaseCleanupLog
from django.contrib.auth.models import User
import re


class SystemSettingsSerializer(serializers.ModelSerializer):
    """Serializer per SystemSettings"""

    updated_by_username = serializers.CharField(
        source="updated_by.username", read_only=True
    )

    class Meta:
        model = SystemSettings
        fields = [
            "id",
            "key",
            "value",
            "category",
            "description",
            "is_public",
            "updated_at",
            "updated_by",
            "updated_by_username",
        ]
        read_only_fields = ["updated_at"]

    def validate_key(self, value):
        """Valida formato chiave (solo alfanumerici e underscore)"""
        if not re.match(r"^[a-zA-Z0-9_]+$", value):
            raise serializers.ValidationError(
                "La chiave può contenere solo lettere, numeri e underscore"
            )

        if len(value) > 100:
            raise serializers.ValidationError(
                "La chiave non può superare 100 caratteri"
            )

        return value.lower()

    def validate_value(self, value):
        """Valida che il valore sia JSON serializzabile"""
        if value is None:
            raise serializers.ValidationError("Il valore non può essere null")

        # Verifica che non contenga chiavi sensibili
        sensitive_keys = ["password", "secret", "token", "api_key", "private_key"]

        def check_sensitive(obj, path=""):
            if isinstance(obj, dict):
                for key, val in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if any(s in key.lower() for s in sensitive_keys):
                        raise serializers.ValidationError(
                            f"Non salvare dati sensibili nelle impostazioni: {current_path}"
                        )
                    check_sensitive(val, current_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_sensitive(item, f"{path}[{i}]")

        check_sensitive(value)
        return value


class SystemSettingsBulkSerializer(serializers.Serializer):
    """Serializer per operazioni bulk su settings"""

    settings = serializers.DictField(
        child=serializers.JSONField(), help_text="Dizionario di impostazioni da salvare"
    )

    category = serializers.ChoiceField(
        choices=SystemSettings.CATEGORY_CHOICES,
        required=False,
        help_text="Categoria delle impostazioni",
    )

    def validate_settings(self, value):
        """Valida che non ci siano più di 50 impostazioni alla volta"""
        if len(value) > 50:
            raise serializers.ValidationError(
                "Non puoi salvare più di 50 impostazioni contemporaneamente"
            )

        # Valida ogni chiave
        for key in value.keys():
            if not re.match(r"^[a-zA-Z0-9_]+$", key):
                raise serializers.ValidationError(f"Chiave non valida: {key}")

        return value


class SSHKeySerializer(serializers.ModelSerializer):
    """Serializer per SSHKey (lettura)"""

    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )

    associated_targets = serializers.IntegerField(
        source="associated_targets_count", read_only=True
    )

    # Non esponiamo mai la chiave privata in lettura
    private_key = serializers.HiddenField(default="")

    class Meta:
        model = SSHKey
        fields = [
            "id",
            "name",
            "key_type",
            "key_size",
            "public_key",
            "private_key",  # Hidden
            "fingerprint",
            "scope",
            "scope_value",
            "created_at",
            "created_by",
            "created_by_username",
            "is_active",
            "last_used_at",
            "associated_targets",
        ]
        read_only_fields = [
            "fingerprint",
            "created_at",
            "last_used_at",
        ]

    def to_representation(self, instance):
        """Override per oscurare parte della chiave pubblica"""
        data = super().to_representation(instance)

        # Mostra solo inizio e fine della chiave pubblica
        public_key = data.get("public_key", "")
        if len(public_key) > 100:
            data["public_key"] = f"{public_key[:50]}...{public_key[-30:]}"

        return data


class SSHKeyCreateSerializer(serializers.Serializer):
    """Serializer per creazione/generazione chiave SSH"""

    name = serializers.CharField(
        max_length=255, help_text="Nome descrittivo della chiave"
    )

    key_type = serializers.ChoiceField(
        choices=["ed25519", "rsa", "ecdsa"],
        default="ed25519",
        help_text="Tipo di chiave SSH",
    )

    key_size = serializers.IntegerField(
        required=False,
        min_value=2048,
        max_value=8192,
        help_text="Dimensione chiave RSA (solo per type=rsa)",
    )

    scope = serializers.ChoiceField(
        choices=["global", "group", "target"],
        default="global",
        help_text="Ambito di utilizzo",
    )

    scope_value = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="Valore scope (gruppo o target ID)",
    )

    passphrase = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        help_text="Passphrase per proteggere la chiave privata",
    )

    def validate_name(self, value):
        """Valida nome chiave"""
        # Sanitizza nome (anti-path-traversal)
        value = re.sub(r"[^\w\s-]", "", value).strip()

        if len(value) < 3:
            raise serializers.ValidationError(
                "Il nome deve essere lungo almeno 3 caratteri"
            )

        # Verifica unicità nome
        if SSHKey.objects.filter(name=value).exists():
            raise serializers.ValidationError("Esiste già una chiave con questo nome")

        return value

    def validate(self, data):
        """Validazione incrociata"""
        key_type = data.get("key_type")
        key_size = data.get("key_size")
        scope = data.get("scope")
        scope_value = data.get("scope_value")

        # RSA richiede key_size
        if key_type == "rsa" and not key_size:
            raise serializers.ValidationError(
                {"key_size": "key_size è obbligatorio per chiavi RSA"}
            )

        # Ed25519 e ECDSA non usano key_size
        if key_type in ["ed25519", "ecdsa"] and key_size:
            raise serializers.ValidationError(
                {"key_size": f"key_size non è supportato per {key_type}"}
            )

        # Scope group/target richiedono scope_value
        if scope in ["group", "target"] and not scope_value:
            raise serializers.ValidationError(
                {"scope_value": f"scope_value è obbligatorio per scope={scope}"}
            )

        # Scope global non deve avere scope_value
        if scope == "global" and scope_value:
            data["scope_value"] = None

        return data

    def validate_passphrase(self, value):
        """Valida robustezza passphrase"""
        if value and len(value) < 8:
            raise serializers.ValidationError(
                "La passphrase deve essere lunga almeno 8 caratteri"
            )
        return value


class SSHKeyImportSerializer(serializers.Serializer):
    """Serializer per importare chiave SSH esistente"""

    name = serializers.CharField(max_length=255)

    public_key = serializers.CharField(
        help_text="Chiave pubblica SSH (formato OpenSSH)"
    )

    private_key = serializers.CharField(
        write_only=True, help_text="Chiave privata SSH (formato OpenSSH)"
    )

    scope = serializers.ChoiceField(
        choices=["global", "group", "target"], default="global"
    )

    scope_value = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )

    def validate_public_key(self, value):
        """Valida formato chiave pubblica"""
        value = value.strip()

        # Deve iniziare con ssh-rsa, ssh-ed25519, o ecdsa-sha2-*
        valid_prefixes = ["ssh-rsa", "ssh-ed25519", "ecdsa-sha2-"]

        if not any(value.startswith(prefix) for prefix in valid_prefixes):
            raise serializers.ValidationError(
                "Formato chiave pubblica non valido. "
                "Deve iniziare con ssh-rsa, ssh-ed25519 o ecdsa-sha2-*"
            )

        # Verifica che abbia almeno 2 parti (type + key)
        parts = value.split()
        if len(parts) < 2:
            raise serializers.ValidationError("Chiave pubblica malformata")

        return value

    def validate_private_key(self, value):
        """Valida formato chiave privata"""
        value = value.strip()

        # Deve iniziare con -----BEGIN
        if not value.startswith("-----BEGIN"):
            raise serializers.ValidationError(
                "Formato chiave privata non valido. " "Deve iniziare con -----BEGIN"
            )

        # Deve finire con -----END
        if not value.endswith("-----"):
            raise serializers.ValidationError(
                "Formato chiave privata non valido. " "Deve terminare con -----END"
            )

        return value

    def validate(self, data):
        """Validazione incrociata"""
        scope = data.get("scope")
        scope_value = data.get("scope_value")

        if scope in ["group", "target"] and not scope_value:
            raise serializers.ValidationError(
                {"scope_value": f"scope_value è obbligatorio per scope={scope}"}
            )

        if scope == "global":
            data["scope_value"] = None

        return data


class DatabaseStatsSerializer(serializers.Serializer):
    """Serializer per statistiche database"""

    total_size = serializers.CharField(help_text="Dimensione totale DB")
    connection_status = serializers.CharField(help_text="Stato connessione")
    database_name = serializers.CharField(help_text="Nome database")
    database_version = serializers.CharField(help_text="Versione PostgreSQL")

    # Contatori per tabella
    targets_count = serializers.IntegerField()
    rules_count = serializers.IntegerField()
    threats_count = serializers.IntegerField()
    audit_logs_count = serializers.IntegerField()
    statistics_count = serializers.IntegerField()
    discovered_hosts_count = serializers.IntegerField()

    # Info spazio
    tables_size = serializers.DictField(
        child=serializers.CharField(), help_text="Dimensione per tabella"
    )


class DatabaseCleanupSerializer(serializers.Serializer):
    """Serializer per operazioni di pulizia database"""

    cleanup_type = serializers.ChoiceField(
        choices=["audit_logs", "threat_logs", "statistics", "discovered_hosts", "all"],
        help_text="Tipo di pulizia da eseguire",
    )

    retention_days = serializers.IntegerField(
        min_value=1,
        max_value=3650,
        help_text="Giorni di retention (mantieni dati più recenti di N giorni)",
    )

    dry_run = serializers.BooleanField(
        default=False, help_text="Se True, simula l'operazione senza eliminare"
    )

    def validate_retention_days(self, value):
        """Valida retention days basato su tipo cleanup"""
        cleanup_type = self.initial_data.get("cleanup_type")

        # Retention minima per tipo
        min_retention = {
            "audit_logs": 30,
            "threat_logs": 90,
            "statistics": 30,
            "discovered_hosts": 7,
        }

        if cleanup_type in min_retention:
            min_days = min_retention[cleanup_type]
            if value < min_days:
                raise serializers.ValidationError(
                    f"Retention minima per {cleanup_type}: {min_days} giorni"
                )

        return value


class DatabaseCleanupLogSerializer(serializers.ModelSerializer):
    """Serializer per log operazioni di pulizia"""

    executed_by_username = serializers.CharField(
        source="executed_by.username", read_only=True
    )

    cleanup_type_display = serializers.CharField(
        source="get_cleanup_type_display", read_only=True
    )

    class Meta:
        model = DatabaseCleanupLog
        fields = [
            "id",
            "cleanup_type",
            "cleanup_type_display",
            "records_deleted",
            "retention_days",
            "executed_at",
            "executed_by",
            "executed_by_username",
            "success",
            "error_message",
        ]
        read_only_fields = "__all__"


class DatabaseConnectionTestSerializer(serializers.Serializer):
    """Serializer per test connessione database"""

    status = serializers.CharField(help_text="Stato connessione (connected/error)")
    message = serializers.CharField(help_text="Messaggio descrittivo")
    latency_ms = serializers.FloatField(help_text="Latenza connessione in ms")
    database_name = serializers.CharField(help_text="Nome database")
    database_version = serializers.CharField(help_text="Versione PostgreSQL")


# ==================== NOTIFICATION SERIALIZERS ====================


class NotificationConfigSerializer(serializers.ModelSerializer):
    """Serializer per NotificationConfig"""

    updated_by_username = serializers.CharField(
        source="updated_by.username", read_only=True
    )

    class Meta:
        from .models import NotificationConfig

        model = NotificationConfig
        fields = [
            "id",
            "email_enabled",
            "email_recipients",
            "smtp_host",
            "smtp_port",
            "smtp_user",
            "smtp_password",
            "smtp_use_tls",
            "smtp_from_email",
            "slack_enabled",
            "slack_webhook_url",
            "discord_enabled",
            "discord_webhook_url",
            "alert_on_critical_threat",
            "alert_on_high_threat",
            "alert_on_target_offline",
            "target_offline_threshold_minutes",
            "alert_on_ssh_error",
            "alert_on_install_success",
            "alert_on_install_failed",
            "cooldown_minutes",
            "updated_at",
            "updated_by",
            "updated_by_username",
        ]
        read_only_fields = ["updated_at", "updated_by", "updated_by_username"]
        extra_kwargs = {"smtp_password": {"write_only": True}}  # Non esporre in lettura

    def validate_email_recipients(self, value):
        """Valida lista email"""
        if not isinstance(value, list):
            raise serializers.ValidationError("email_recipients deve essere una lista")

        if len(value) > 50:
            raise serializers.ValidationError("Massimo 50 indirizzi email")

        # Valida formato email
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError

        for email in value:
            try:
                validate_email(email)
            except ValidationError:
                raise serializers.ValidationError(f"Email non valida: {email}")

        return value

    def validate_slack_webhook_url(self, value):
        """Valida webhook Slack"""
        if value and not value.startswith("https://hooks.slack.com/"):
            raise serializers.ValidationError(
                "URL webhook Slack non valido. Deve iniziare con https://hooks.slack.com/"
            )
        return value

    def validate_discord_webhook_url(self, value):
        """Valida webhook Discord"""
        if value and not value.startswith("https://discord.com/api/webhooks/"):
            raise serializers.ValidationError(
                "URL webhook Discord non valido. Deve iniziare con https://discord.com/api/webhooks/"
            )
        return value

    def validate(self, data):
        """Validazione incrociata"""
        # Se email abilitata, verifica configurazione completa
        if data.get("email_enabled"):
            required_fields = {
                "email_recipients": "Inserisci almeno un indirizzo email",
                "smtp_host": "Inserisci host SMTP",
                "smtp_port": "Inserisci porta SMTP",
                "smtp_user": "Inserisci username SMTP",
                "smtp_from_email": "Inserisci email mittente",
            }

            for field, error_msg in required_fields.items():
                if not data.get(field):
                    raise serializers.ValidationError({field: error_msg})

        # Se Slack abilitato, deve avere webhook URL
        if data.get("slack_enabled") and not data.get("slack_webhook_url"):
            raise serializers.ValidationError(
                {"slack_webhook_url": "Inserisci webhook URL Slack"}
            )

        # Se Discord abilitato, deve avere webhook URL
        if data.get("discord_enabled") and not data.get("discord_webhook_url"):
            raise serializers.ValidationError(
                {"discord_webhook_url": "Inserisci webhook URL Discord"}
            )

        return data


class NotificationTestSerializer(serializers.Serializer):
    """
    Serializer per test notifiche
    Usa le credenziali già salvate in NotificationConfig
    """

    notification_type = serializers.ChoiceField(
        choices=["email", "slack", "discord"], help_text="Tipo di notifica da testare"
    )

    test_recipient = serializers.CharField(
        required=False,
        help_text="Destinatario per test (email o lascia vuoto per usare config)",
    )

    def validate(self, data):
        """Verifica che la configurazione sia completa"""
        from .models import NotificationConfig

        notification_type = data.get("notification_type")
        config = NotificationConfig.get_config()

        if notification_type == "email":
            if not config.email_enabled:
                raise serializers.ValidationError(
                    "Email non abilitata. Configura prima le impostazioni email."
                )

            if not config.smtp_host or not config.smtp_user:
                raise serializers.ValidationError(
                    "Configurazione SMTP incompleta. Inserisci host e username SMTP."
                )

        elif notification_type == "slack":
            if not config.slack_enabled or not config.slack_webhook_url:
                raise serializers.ValidationError(
                    "Slack non configurato. Inserisci webhook URL Slack."
                )

        elif notification_type == "discord":
            if not config.discord_enabled or not config.discord_webhook_url:
                raise serializers.ValidationError(
                    "Discord non configurato. Inserisci webhook URL Discord."
                )

        return data


class NotificationLogSerializer(serializers.ModelSerializer):
    """Serializer per NotificationLog"""

    target_hostname = serializers.CharField(
        source="target.hostname", read_only=True, allow_null=True
    )

    notification_type_display = serializers.CharField(
        source="get_notification_type_display", read_only=True
    )

    alert_type_display = serializers.CharField(
        source="get_alert_type_display", read_only=True
    )

    class Meta:
        from .models import NotificationLog

        model = NotificationLog
        fields = [
            "id",
            "notification_type",
            "notification_type_display",
            "alert_type",
            "alert_type_display",
            "target",
            "target_hostname",
            "recipient",
            "message",
            "success",
            "error_message",
            "sent_at",
        ]
        read_only_fields = "__all__"


# ==================== USER MANAGEMENT SERIALIZERS ====================


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer per profilo utente"""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
        ]
        read_only_fields = [
            "id",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
        ]


class ChangeUsernameSerializer(serializers.Serializer):
    """Serializer per cambio username"""

    new_username = serializers.CharField(
        min_length=3, max_length=150, help_text="Nuovo username"
    )

    def validate_new_username(self, value):
        """Valida nuovo username"""
        # Solo alfanumerici, underscore, hyphen
        if not re.match(r"^[a-zA-Z0-9_-]+$", value):
            raise serializers.ValidationError(
                "Username può contenere solo lettere, numeri, underscore e trattini"
            )

        # Verifica unicità
        request = self.context.get("request")
        if (
            request
            and User.objects.filter(username=value).exclude(pk=request.user.pk).exists()
        ):
            raise serializers.ValidationError("Username già in uso")

        return value


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer per cambio password con validazione OWASP/NIST

    Requisiti:
    - Minimo 9 caratteri
    - Almeno 2 lettere maiuscole
    - Almeno 2 lettere minuscole
    - Almeno 2 numeri
    - Almeno 2 caratteri speciali
    """

    current_password = serializers.CharField(
        write_only=True, help_text="Password attuale"
    )

    new_password = serializers.CharField(
        write_only=True, min_length=9, help_text="Nuova password"
    )

    confirm_password = serializers.CharField(
        write_only=True, help_text="Conferma nuova password"
    )

    def validate_current_password(self, value):
        """Verifica che la password attuale sia corretta"""
        user = self.context.get("request").user

        if not user.check_password(value):
            raise serializers.ValidationError("Password attuale non corretta")

        return value

    def validate_new_password(self, value):
        """
        Valida nuova password secondo requisiti:
        - Min 9 caratteri
        - Almeno 2 maiuscole
        - Almeno 2 minuscole
        - Almeno 2 numeri
        - Almeno 2 caratteri speciali
        """
        if len(value) < 9:
            raise serializers.ValidationError(
                "La password deve essere lunga almeno 9 caratteri"
            )

        # Conta caratteri per tipo
        uppercase_count = sum(1 for c in value if c.isupper())
        lowercase_count = sum(1 for c in value if c.islower())
        digit_count = sum(1 for c in value if c.isdigit())
        special_count = sum(1 for c in value if not c.isalnum())

        errors = []

        if uppercase_count < 2:
            errors.append("almeno 2 lettere maiuscole")

        if lowercase_count < 2:
            errors.append("almeno 2 lettere minuscole")

        if digit_count < 2:
            errors.append("almeno 2 numeri")

        if special_count < 2:
            errors.append("almeno 2 caratteri speciali")

        if errors:
            raise serializers.ValidationError(
                f"La password deve contenere: {', '.join(errors)}"
            )

        # Verifica che non sia uguale alla password attuale
        user = self.context.get("request").user
        if user.check_password(value):
            raise serializers.ValidationError(
                "La nuova password deve essere diversa da quella attuale"
            )

        return value

    def validate(self, data):
        """Verifica che new_password e confirm_password corrispondano"""
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Le password non corrispondono"}
            )

        return data

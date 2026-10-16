"""
App Config per Settings
"""

from django.apps import AppConfig


class SettingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "settings"
    verbose_name = "System Settings"

    def ready(self):
        """
        Inizializzazione app
        Carica signal handlers e impostazioni default
        """
        # Import signals
        # from . import signals

        # _initialize_default_settings() fa query DB — NON richiamarla da
        # qui: ready() gira anche durante `manage.py migrate` prima che la
        # tabella system_settings esista, e romperebbe le migrazioni. Le
        # chiavi mancanti restano semplicemente assenti finché il frontend
        # non fa il primo salvataggio (usa i default locali fino ad allora).
        pass

    def _initialize_default_settings(self):
        """Crea impostazioni default se non esistono"""
        from .models import SystemSettings

        default_settings = {
            # General
            "systemName": {"value": "FireDog Security", "category": "general"},
            "timezone": {"value": "Europe/Rome", "category": "general"},
            "language": {"value": "it", "category": "general"},
            # Appearance
            "theme": {"value": "dark", "category": "appearance"},
            "fontFamily": {"value": "Inter", "category": "appearance"},
            "fontSize": {"value": 14, "category": "appearance"},
            "borderRadius": {"value": 8, "category": "appearance"},
            "enableAnimations": {"value": True, "category": "appearance"},
            # Notifications
            "emailNotifications": {"value": False, "category": "notifications"},
            "slackNotifications": {"value": False, "category": "notifications"},
            "discordNotifications": {"value": False, "category": "notifications"},
            # Security
            "sessionTimeout": {"value": 30, "category": "security"},
            "maxLoginAttempts": {"value": 5, "category": "security"},
            "enableMFA": {"value": False, "category": "security"},
            # Monitoring
            "scanInterval": {"value": 60, "category": "monitoring"},
            "logRetention": {"value": 30, "category": "monitoring"},
            "enableAutoBlock": {"value": True, "category": "monitoring"},
            "alertNotificationMinScore": {"value": 8, "category": "monitoring"},
            "pcapSavePath": {"value": "/var/log/ulogd", "category": "monitoring"},
            "pcapAnalysisTool": {"value": "tcpdump", "category": "monitoring"},
            "pcapCustomFilters": {"value": [], "category": "monitoring"},
            "pcapThreatCommands": {"value": [], "category": "monitoring"},
        }

        for key, config in default_settings.items():
            SystemSettings.objects.get_or_create(
                key=key,
                defaults={
                    "value": config["value"],
                    "category": config["category"],
                    "description": f"Default {key} setting",
                    "is_public": True,
                },
            )

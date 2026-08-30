"""
Views per Settings App
Gestione configurazioni e database
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db import connection, transaction
from django.utils import timezone
from django.contrib.auth import update_session_auth_hash
from datetime import timedelta
import logging
from .tasks import send_test_notification
from .models import (
    SystemSettings,
    DatabaseCleanupLog,
    NotificationConfig,
    NotificationLog,
)
from .serializers import (
    SystemSettingsSerializer,
    SystemSettingsBulkSerializer,
    DatabaseStatsSerializer,
    DatabaseCleanupSerializer,
    DatabaseCleanupLogSerializer,
    DatabaseConnectionTestSerializer,
    NotificationConfigSerializer,
    NotificationLogSerializer,
    UserProfileSerializer,
    ChangeUsernameSerializer,
    ChangePasswordSerializer,
)

logger = logging.getLogger("firedog.settings")


class SystemSettingsViewSet(viewsets.ModelViewSet):
    """
    ViewSet per gestione impostazioni di sistema

    Endpoints:
    - GET /api/settings/ - Lista tutte le impostazioni
    - GET /api/settings/{id}/ - Dettaglio impostazione
    - POST /api/settings/ - Crea nuova impostazione
    - PUT/PATCH /api/settings/{id}/ - Aggiorna impostazione
    - DELETE /api/settings/{id}/ - Elimina impostazione
    - POST /api/settings/bulk_update/ - Aggiorna multiple impostazioni
    - POST /api/settings/reset/ - Reset a valori default
    """

    queryset = SystemSettings.objects.all()
    serializer_class = SystemSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtra impostazioni in base a categoria"""
        queryset = super().get_queryset()

        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category)

        # Filtra solo impostazioni pubbliche per utenti non admin
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_public=True)

        return queryset

    def perform_create(self, serializer):
        """Salva chi ha creato l'impostazione"""
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        """Salva chi ha aggiornato l'impostazione"""
        serializer.save(updated_by=self.request.user)

    @action(detail=False, methods=["post"])
    def bulk_update(self, request):
        """
        Aggiorna multiple impostazioni in una sola richiesta

        POST /api/settings/bulk_update/
        Body: {
            "settings": {
                "systemName": "FireDog Security",
                "timezone": "Europe/Rome",
                ...
            },
            "category": "general"
        }
        """
        serializer = SystemSettingsBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        settings_data = serializer.validated_data["settings"]
        category = serializer.validated_data.get("category", "general")

        updated_settings = []

        with transaction.atomic():
            for key, value in settings_data.items():
                setting = SystemSettings.set_setting(
                    key=key, value=value, category=category, user=request.user
                )
                updated_settings.append(setting)

        # Log audit
        from audit.models import AuditLog

        AuditLog.log_action(
            username=request.user.username,
            action="settings.bulk_update",
            details={"updated_count": len(updated_settings), "category": category},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        result_serializer = SystemSettingsSerializer(updated_settings, many=True)
        return Response(
            {"updated_count": len(updated_settings), "settings": result_serializer.data}
        )

    @action(detail=False, methods=["post"])
    def reset(self, request):
        """
        Reset impostazioni ai valori default

        POST /api/settings/reset/
        Body: {
            "category": "general"  // Optional, se omesso reset tutto
        }
        """
        category = request.data.get("category")

        if category:
            deleted_count, _ = SystemSettings.objects.filter(category=category).delete()
        else:
            deleted_count, _ = SystemSettings.objects.all().delete()

        # Log audit
        from audit.models import AuditLog

        AuditLog.log_action(
            username=request.user.username,
            action="settings.reset",
            details={"deleted_count": deleted_count, "category": category or "all"},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return Response(
            {
                "message": "Impostazioni ripristinate ai valori default",
                "deleted_count": deleted_count,
            }
        )


class DatabaseManagementViewSet(viewsets.ViewSet):
    """
    ViewSet per gestione database

    Endpoints:
    - GET /api/settings/database/stats/ - Statistiche database
    - POST /api/settings/database/test-connection/ - Test connessione
    - POST /api/settings/database/cleanup/ - Pulizia dati vecchi
    - GET /api/settings/database/cleanup-logs/ - Log pulizie
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        Recupera statistiche database

        GET /api/settings/database/stats/
        """
        try:
            with connection.cursor() as cursor:
                # Dimensione totale database
                cursor.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                """)
                total_size = cursor.fetchone()[0]

                # Versione PostgreSQL
                cursor.execute("SELECT version()")
                db_version = cursor.fetchone()[0].split()[1]

                # Nome database
                cursor.execute("SELECT current_database()")
                db_name = cursor.fetchone()[0]

                # Dimensione per tabella
                cursor.execute("""
                    SELECT
                        schemaname || '.' || tablename AS table_name,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
                    FROM pg_tables
                    WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                    LIMIT 20
                """)
                tables_size = {row[0]: row[1] for row in cursor.fetchall()}

            # Conta record per tabella
            from targets.models import Target
            from rules.models import FirewallRule
            from threats.models import ThreatLog
            from audit.models import AuditLog
            from discovery.models import DiscoveredHost

            try:
                from targets.models import Statistics

                statistics_count = Statistics.objects.count()
            except:
                statistics_count = 0

            stats_data = {
                "total_size": total_size,
                "connection_status": "connected",
                "database_name": db_name,
                "database_version": db_version,
                "targets_count": Target.objects.count(),
                "rules_count": FirewallRule.objects.count(),
                "threats_count": ThreatLog.objects.count(),
                "audit_logs_count": AuditLog.objects.count(),
                "statistics_count": statistics_count,
                "discovered_hosts_count": DiscoveredHost.objects.count(),
                "tables_size": tables_size,
            }

            serializer = DatabaseStatsSerializer(stats_data)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return Response(
                {"error": f"Errore recupero statistiche: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"])
    def test_connection(self, request):
        """
        Testa connessione database

        POST /api/settings/database/test-connection/
        """
        import time

        try:
            start_time = time.time()

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

                cursor.execute("SELECT current_database()")
                db_name = cursor.fetchone()[0]

                cursor.execute("SELECT version()")
                db_version = cursor.fetchone()[0].split()[1]

            latency_ms = (time.time() - start_time) * 1000

            result = {
                "status": "connected",
                "message": "Connessione database OK",
                "latency_ms": round(latency_ms, 2),
                "database_name": db_name,
                "database_version": db_version,
            }

            serializer = DatabaseConnectionTestSerializer(result)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return Response(
                {
                    "status": "error",
                    "message": f"Errore connessione: {str(e)}",
                    "latency_ms": 0,
                    "database_name": "",
                    "database_version": "",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    @action(detail=False, methods=["post"])
    def cleanup(self, request):
        """
        Pulizia dati vecchi dal database

        POST /api/settings/database/cleanup/
        Body: {
            "cleanup_type": "audit_logs",
            "retention_days": 90,
            "dry_run": false
        }
        """
        serializer = DatabaseCleanupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cleanup_type = serializer.validated_data["cleanup_type"]
        retention_days = serializer.validated_data["retention_days"]
        dry_run = serializer.validated_data["dry_run"]

        cutoff_date = timezone.now() - timedelta(days=retention_days)

        try:
            records_deleted = 0

            with transaction.atomic():
                if cleanup_type in ["audit_logs", "all"]:
                    from audit.models import AuditLog

                    queryset = AuditLog.objects.filter(timestamp__lt=cutoff_date)
                    count = queryset.count()
                    if not dry_run:
                        queryset.delete()
                    records_deleted += count

                if cleanup_type in ["threat_logs", "all"]:
                    from threats.models import ThreatLog

                    queryset = ThreatLog.objects.filter(detected_at__lt=cutoff_date)
                    count = queryset.count()
                    if not dry_run:
                        queryset.delete()
                    records_deleted += count

                if cleanup_type in ["statistics", "all"]:
                    try:
                        from targets.models import Statistics

                        queryset = Statistics.objects.filter(
                            collected_at__lt=cutoff_date
                        )
                        count = queryset.count()
                        if not dry_run:
                            queryset.delete()
                        records_deleted += count
                    except:
                        pass

                if cleanup_type in ["discovered_hosts", "all"]:
                    from discovery.models import DiscoveredHost

                    queryset = DiscoveredHost.objects.filter(
                        discovered_at__lt=cutoff_date, imported=False
                    )
                    count = queryset.count()
                    if not dry_run:
                        queryset.delete()
                    records_deleted += count

            # Log operazione se non dry_run
            if not dry_run:
                DatabaseCleanupLog.objects.create(
                    cleanup_type=cleanup_type,
                    records_deleted=records_deleted,
                    retention_days=retention_days,
                    executed_by=request.user,
                    success=True,
                )

                # Log audit
                from audit.models import AuditLog

                AuditLog.log_action(
                    username=request.user.username,
                    action="database.cleanup",
                    details={
                        "cleanup_type": cleanup_type,
                        "records_deleted": records_deleted,
                        "retention_days": retention_days,
                    },
                    ip_address=request.META.get("REMOTE_ADDR"),
                )

            return Response(
                {
                    "success": True,
                    "records_deleted": records_deleted,
                    "dry_run": dry_run,
                    "message": f'{"Simulazione: " if dry_run else ""}{records_deleted} record eliminati',
                }
            )

        except Exception as e:
            logger.error(f"Database cleanup failed: {e}")

            # Log errore
            if not dry_run:
                DatabaseCleanupLog.objects.create(
                    cleanup_type=cleanup_type,
                    records_deleted=0,
                    retention_days=retention_days,
                    executed_by=request.user,
                    success=False,
                    error_message=str(e),
                )

            return Response(
                {"error": f"Errore pulizia database: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def cleanup_logs(self, request):
        """
        Recupera log delle operazioni di pulizia

        GET /api/settings/database/cleanup-logs/
        """
        logs = DatabaseCleanupLog.objects.all()[:50]
        serializer = DatabaseCleanupLogSerializer(logs, many=True)
        return Response(serializer.data)


# ==================== NOTIFICATION VIEWSET ====================


class NotificationViewSet(viewsets.ViewSet):
    """
    ViewSet per gestione notifiche

    Endpoints:
    - GET    /api/settings/notifications/config/
    - PUT    /api/settings/notifications/config/
    - POST   /api/settings/notifications/test/
    - GET    /api/settings/notifications/logs/
    - GET    /api/settings/notifications/smtp-info/
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    @action(detail=False, methods=["get", "put"])
    def config(self, request):
        """
        GET/PUT /api/settings/notifications/config/
        Ottieni o aggiorna configurazione notifiche
        """

        config = NotificationConfig.get_config()

        if request.method == "GET":
            serializer = NotificationConfigSerializer(config)
            return Response(serializer.data)

        elif request.method == "PUT":
            serializer = NotificationConfigSerializer(
                config, data=request.data, partial=True, context={"request": request}
            )

            if serializer.is_valid():
                serializer.save(updated_by=request.user)

                logger.info(f"Notification config updated by {request.user.username}")

                return Response(serializer.data)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def test(self, request):
        """
        POST /api/settings/notifications/test/
        Testa invio notifica

        Body:
        {
            "notification_type": "email|slack|discord",
            "test_recipient": "test@example.com"  // opzionale
        }
        """
        from .serializers import NotificationTestSerializer

        serializer = NotificationTestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        notification_type = serializer.validated_data["notification_type"]
        test_recipient = serializer.validated_data.get("test_recipient", "")

        try:
            # Esegui task sincrono per test immediato
            result = send_test_notification(
                notification_type=notification_type,
                test_recipient=test_recipient,
                username=request.user.username,
            )

            if result.get("success"):
                return Response(
                    {
                        "success": True,
                        "message": f"Test {notification_type} inviato con successo!",
                        "details": result.get("details", {}),
                    }
                )
            else:
                return Response(
                    {
                        "success": False,
                        "message": f"Errore invio test {notification_type}",
                        "error": result.get("error", "Unknown error"),
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            logger.error(f"Test notification error: {str(e)}", exc_info=True)
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def logs(self, request):
        """
        GET /api/settings/notifications/logs/?limit=50
        Ottieni ultimi log notifiche
        """

        limit = int(request.query_params.get("limit", 50))

        logs = NotificationLog.objects.all()[:limit]
        serializer = NotificationLogSerializer(logs, many=True)

        return Response({"count": logs.count(), "results": serializer.data})

    @action(detail=False, methods=["get"])
    def smtp_info(self, request):
        """
        GET /api/settings/notifications/smtp-info/
        Ritorna info/guida configurazione SMTP/Postfix
        """
        return Response(
            {
                "title": "Configurazione SMTP",
                "description": "Guida rapida per configurare Postfix/Sendmail su Ubuntu",
                "steps": [
                    {
                        "step": 1,
                        "title": "Installa Postfix",
                        "command": "sudo apt update && sudo apt install postfix mailutils -y",
                        "description": 'Durante l\'installazione, seleziona "Internet Site"',
                    },
                    {
                        "step": 2,
                        "title": "Configura Postfix",
                        "command": "sudo nano /etc/postfix/main.cf",
                        "description": "Imposta:\nmyhostname = firedog.local\nmydestination = localhost",
                    },
                    {
                        "step": 3,
                        "title": "Riavvia Postfix",
                        "command": "sudo systemctl restart postfix",
                        "description": "Applica le modifiche",
                    },
                    {
                        "step": 4,
                        "title": "Test Manuale",
                        "command": 'echo "Test mail" | mail -s "Test" user@example.com',
                        "description": "Verifica invio email da terminale",
                    },
                ],
                "common_configs": {
                    "localhost": {
                        "smtp_host": "localhost",
                        "smtp_port": 25,
                        "smtp_user": "microcyber",
                        "smtp_use_tls": False,
                        "description": "Postfix locale (default)",
                    },
                    "gmail": {
                        "smtp_host": "smtp.gmail.com",
                        "smtp_port": 587,
                        "smtp_user": "your-email@gmail.com",
                        "smtp_use_tls": True,
                        "description": "Gmail SMTP (richiede App Password)",
                    },
                    "sendgrid": {
                        "smtp_host": "smtp.sendgrid.net",
                        "smtp_port": 587,
                        "smtp_user": "apikey",
                        "smtp_use_tls": True,
                        "description": "SendGrid SMTP",
                    },
                },
                "troubleshooting": [
                    {
                        "problem": "Connection refused",
                        "solution": "Verifica che Postfix sia attivo: sudo systemctl status postfix",
                    },
                    {
                        "problem": "Authentication failed",
                        "solution": "Controlla username/password SMTP. Per Gmail usa App Password.",
                    },
                    {
                        "problem": "TLS error",
                        "solution": "Prova a disabilitare TLS o cambia porta (25, 465, 587)",
                    },
                ],
            }
        )


# ==================== USER MANAGEMENT VIEWSET ====================


class UserManagementViewSet(viewsets.ViewSet):
    """
    ViewSet per gestione profilo utente

    Endpoints:
    - GET    /api/settings/user/profile/
    - PUT    /api/settings/user/change-username/
    - PUT    /api/settings/user/change-password/
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def profile(self, request):
        """
        GET /api/settings/user/profile/
        Ottieni informazioni profilo utente corrente
        """

        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["put"])
    def change_username(self, request):
        """
        PUT /api/settings/user/change-username/
        Cambia username utente corrente

        Body:
        {
            "new_username": "nuovo_username"
        }
        """
        from audit.models import AuditLog

        serializer = ChangeUsernameSerializer(
            data=request.data, context={"request": request}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        old_username = request.user.username
        new_username = serializer.validated_data["new_username"]

        # Aggiorna username
        request.user.username = new_username
        request.user.save()

        # Log audit
        AuditLog.log_action(
            username=new_username,
            action="user.change_username",
            details={"old_username": old_username, "new_username": new_username},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        logger.info(f"Username changed: {old_username} -> {new_username}")

        return Response(
            {
                "success": True,
                "message": "Username aggiornato con successo",
                "new_username": new_username,
            }
        )

    @action(detail=False, methods=["put"])
    def change_password(self, request):
        """
        PUT /api/settings/user/change-password/
        Cambia password utente corrente

        Body:
        {
            "current_password": "password_attuale",
            "new_password": "nuova_password",
            "confirm_password": "nuova_password"
        }
        """
        from audit.models import AuditLog

        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Cambia password
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()

        # Mantieni sessione attiva dopo cambio password
        update_session_auth_hash(request, request.user)

        # Log audit
        AuditLog.log_action(
            username=request.user.username,
            action="user.change_password",
            details={"success": True},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        logger.info(f"Password changed for user: {request.user.username}")

        return Response(
            {"success": True, "message": "Password aggiornata con successo"}
        )

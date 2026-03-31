"""
Nuovi API Endpoints per Frontend
File: backend/api/views.py (NUOVE VIEWS DA AGGIUNGERE)

Questi endpoint forniscono i dati necessari per le pagine frontend:
- Statistics per un target
- Threats con filtri
- Traffic analysis
- Logs (audit, system, firewall)
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
import logging

logger = logging.getLogger("firedog.api")


class StatisticsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet per visualizzare statistics

    Endpoints:


    GET /api/targets/{target_id}/stats/
    GET /api/targets/{target_id}/stats/latest/
    GET /api/targets/{target_id}/stats/{id}/
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["collected_at"]

    def get_queryset(self):
        """Filtra stats per target"""
        from targets.models import Statistics

        target_id = self.kwargs.get("target_pk")
        return Statistics.objects.filter(target_id=target_id).order_by("-collected_at")

    def get_serializer_class(self):
        from api.serializers import StatisticsSerializer

        return StatisticsSerializer

    @action(detail=False, methods=["get"])
    def latest(self, request, target_pk=None):
        """


        Restituisce l'ultima statistica registrata
        GET /api/targets/{target_id}/stats/latest/
        """

        stats = self.get_queryset().first()

        if not stats:
            return Response(
                {"error": "No statistics available"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def history(self, request, target_pk=None):
        """


        Restituisce lo storico stats nelle ultime N ore
        GET /api/targets/{target_id}/stats/history/?hours=24
        """

        hours = int(request.query_params.get("hours", 24))
        since = timezone.now() - timedelta(hours=hours)

        stats = self.get_queryset().filter(collected_at__gte=since)
        serializer = self.get_serializer(stats, many=True)

        return Response(
            {"hours": hours, "count": stats.count(), "results": serializer.data}
        )


class ThreatLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet per visualizzare threats

    Endpoints:
    -
    GET /api/targets/{target_id}/threats/
    GET /api/targets/{target_id}/threats/{id}/
    POST /api/targets/{target_id}/threats/{id}/acknowledge/
    GET /api/targets/{target_id}/threats/summary/
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["classification", "threat_type", "acknowledged", "source_ip"]

    def get_queryset(self):
        """Filtra threats per target"""
        from threats.models import ThreatLog

        target_id = self.kwargs.get("target_pk")
        return ThreatLog.objects.filter(target_id=target_id).order_by("-detected_at")

    def get_serializer_class(self):
        from threats.serializers import ThreatLogSerializer

        return ThreatLogSerializer

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, target_pk=None, pk=None):
        """


        Marca una minaccia come acknowledged
        POST /api/targets/{target_id}/threats/{id}/acknowledge/
        """

        threat = self.get_object()
        threat.acknowledged = True
        threat.save()

        # Log audit
        from audit.models import AuditLog

        AuditLog.log_action(
            username=request.user.username,
            action="threat.acknowledge",
            target_id=target_pk,
            details={"threat_id": pk, "source_ip": str(threat.source_ip)},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        serializer = self.get_serializer(threat)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def summary(self, request, target_pk=None):
        """


        Restituisce riepilogo threats per severity
        GET /api/targets/{target_id}/threats/summary/?hours=24
        """

        hours = int(request.query_params.get("hours", 24))
        since = timezone.now() - timedelta(hours=hours)

        threats = self.get_queryset().filter(detected_at__gte=since)

        summary = {
            "total": threats.count(),
            "by_classification": {
                "critical": threats.filter(classification="CRITICAL").count(),
                "high": threats.filter(classification="HIGH").count(),
                "medium": threats.filter(classification="MEDIUM").count(),
                "low": threats.filter(classification="LOW").count(),
            },
            "acknowledged": threats.filter(acknowledged=True).count(),
            "unacknowledged": threats.filter(acknowledged=False).count(),
            "top_attackers": list(
                threats.values("source_ip")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
            ),
        }

        return Response(summary)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet per visualizzare audit logs

    Endpoints:
    -  - Log specifico
    GET /api/logs/audit/
    GET /api/logs/audit/{id}/
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["username", "action", "target"]

    def get_queryset(self):
        from audit.models import AuditLog

        return AuditLog.objects.all().order_by("-timestamp")

    def get_serializer_class(self):
        from audit.serializers import AuditLogSerializer

        return AuditLogSerializer

    @action(detail=False, methods=["get"])
    def recent(self, request):
        """


        Ultimi N audit logs
        GET /api/logs/audit/recent/?hours=24&limit=100
        """

        hours = int(request.query_params.get("hours", 24))
        limit = int(request.query_params.get("limit", 100))
        since = timezone.now() - timedelta(hours=hours)

        logs = self.get_queryset().filter(timestamp__gte=since)[:limit]
        serializer = self.get_serializer(logs, many=True)

        return Response({"count": logs.count(), "results": serializer.data})


class NetworkTrafficViewSet(viewsets.ViewSet):
    """
    ViewSet per analisi traffico rete

    Endpoints:
    -  - Analisi traffico
    GET /api/targets/{target_id}/traffic/realtime/
    GET /api/targets/{target_id}/traffic/analyze/
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def realtime(self, request, target_pk=None):
        """


        Ottiene stats in tempo reale
        GET /api/targets/{target_id}/traffic/realtime/
        """

        from targets.models import Target, Statistics

        try:
            target = Target.objects.get(id=target_pk)

            # Ultime 10 statistics per grafico
            recent_stats = Statistics.objects.filter(target=target).order_by(
                "-collected_at"
            )[:10]

            from api.serializers import StatisticsSerializer

            serializer = StatisticsSerializer(recent_stats, many=True)

            return Response(
                {
                    "target": {
                        "id": target.id,
                        "hostname": target.hostname,
                        "ip_address": str(target.ip_address),
                        "status": target.status,
                    },
                    "statistics": serializer.data,
                }
            )

        except Target.DoesNotExist:
            return Response(
                {"error": "Target not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["post"])
    def analyze(self, request, target_pk=None):
        """


        Triggera analisi traffico sul target
        POST /api/targets/{target_id}/traffic/analyze/
        """
        Body: {"hours": 24}

        from targets.models import Target
        from core.ssh_manager import SSHManager, SSHConnectionError

        hours = request.data.get("hours", 1)

        try:
            target = Target.objects.get(id=target_pk)

            if target.status != "online":
                return Response(
                    {"error": "Target is not online"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            # Connessione SSH e analisi
            ssh = SSHManager(
                host=target.ip_address, port=target.ssh_port, username=target.ssh_user
            )
            ssh.connect()

            analysis = ssh.analyze_traffic(hours=hours)
            ssh.disconnect()

            if not analysis:
                return Response(
                    {"error": "Analysis failed"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Log audit
            from audit.models import AuditLog

            AuditLog.log_action(
                username=request.user.username,
                action="traffic.analyze",
                target=target,
                details={"hours": hours},
                ip_address=request.META.get("REMOTE_ADDR"),
            )

            return Response(analysis)

        except Target.DoesNotExist:
            return Response(
                {"error": "Target not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except SSHConnectionError as e:
            return Response(
                {"error": f"SSH connection failed: {str(e)}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class PerformanceViewSet(viewsets.ViewSet):
    """
    ViewSet per metriche performance sistema

    Endpoints:
    -  - Metriche sistema
    GET /api/targets/{target_id}/performance/
    """

    permission_classes = [IsAuthenticated]

    def list(self, request, target_pk=None):
        """


        Ottiene metriche CPU, RAM, Disk (future implementation)
        # TODO: Implementare quando saranno disponibili i comandi
        # per recuperare metriche sistema dal target

        GET /api/targets/{target_id}/performance/
        """

        return Response(
            {
                "message": "Performance monitoring not yet implemented",
                "planned_metrics": [
                    "cpu_usage_percent",
                    "memory_usage_percent",
                    "disk_usage_percent",
                    "network_io_bytes",
                ],
            }
        )


# ==================== LOG VIEWS ====================
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
import os


class LogAPIView(APIView):
    """
    API per recuperare log
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        GET /api/logs/?source=django&lines=100
        """
        source = request.query_params.get("source", "django")
        lines = int(request.query_params.get("lines", 100))

        logs_dir = settings.LOGS_DIR

        log_files = {
            "django": logs_dir / "django.log",
            "celery": logs_dir / "celery.log",
            "application": logs_dir / "application.log",
        }

        file_path = log_files.get(source)

        if not file_path or not os.path.exists(file_path):
            return Response(
                {"source": source, "logs": [], "message": "Log file not found"}
            )

        try:
            with open(file_path, "r") as f:
                all_lines = f.readlines()
                last_lines = [
                    line.strip() for line in all_lines[-lines:] if line.strip()
                ]

            return Response(
                {"source": source, "logs": last_lines, "total_lines": len(last_lines)}
            )
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class LogSourcesAPIView(APIView):
    """
    API per elencare sorgenti log disponibili
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        GET /api/logs/sources/
        """
        logs_dir = settings.LOGS_DIR

        sources = []
        log_files = {
            "django": {
                "name": "Django/Daphne",
                "path": logs_dir / "django.log",
                "description": "Log del server web Django e Daphne",
            },
            "celery": {
                "name": "Celery",
                "path": logs_dir / "celery.log",
                "description": "Log dei task Celery Worker e Beat",
            },
            "application": {
                "name": "Application",
                "path": logs_dir / "application.log",
                "description": "Log generale dell'applicazione FireDog",
            },
        }

        for key, info in log_files.items():
            file_path = info["path"]
            exists = os.path.exists(file_path)
            size

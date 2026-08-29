"""
Views per l'app Audit
"""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta
import logging

from .models import AuditLog
from .serializers import AuditLogSerializer, AuditLogListSerializer

logger = logging.getLogger("firedog.audit")


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet per visualizzare audit logs

    Endpoints:
    - GET /api/audit/ - Lista audit logs
    - GET /api/audit/{id}/ - Dettaglio log specifico
    - GET /api/audit/recent/ - Ultimi N logs
    """

    queryset = AuditLog.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["user", "action", "success"]

    def get_serializer_class(self):
        if self.action == "list":
            return AuditLogListSerializer
        return AuditLogSerializer

    @action(detail=False, methods=["get"])
    def recent(self, request):
        """
        GET /api/audit/recent/?hours=24&limit=100

        Restituisce gli ultimi N audit logs
        """
        hours = int(request.query_params.get("hours", 24))
        limit = int(request.query_params.get("limit", 100))
        since = timezone.now() - timedelta(hours=hours)

        logs = self.get_queryset().filter(created_at__gte=since)[:limit]
        serializer = self.get_serializer(logs, many=True)

        return Response(
            {"hours": hours, "count": logs.count(), "results": serializer.data}
        )

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        GET /api/audit/stats/?hours=24

        Statistiche audit logs
        """
        from django.db.models import Count

        hours = int(request.query_params.get("hours", 24))
        since = timezone.now() - timedelta(hours=hours)

        logs = self.get_queryset().filter(created_at__gte=since)

        stats = {
            "total": logs.count(),
            "successful": logs.filter(success=True).count(),
            "failed": logs.filter(success=False).count(),
            "by_action": list(
                logs.values("action")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
            ),
            "by_user": list(
                logs.values("user__username")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
            ),
        }

        return Response(stats)

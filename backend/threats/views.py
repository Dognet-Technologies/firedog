from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from .models import ThreatLog
from .serializers import (
    ThreatLogSerializer,
    ThreatLogListSerializer,
    ThreatLogStatsSerializer,
)


class ThreatLogViewSet(viewsets.ModelViewSet):
    queryset = ThreatLog.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["target", "severity", "is_blocked", "is_resolved", "source_ip"]

    def get_serializer_class(self):
        if self.action == "list":
            return ThreatLogListSerializer
        return ThreatLogSerializer

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Statistiche minacce"""
        queryset = self.get_queryset()

        stats = {
            "total_threats": queryset.count(),
            "critical_threats": queryset.filter(severity="critical").count(),
            "high_threats": queryset.filter(severity="high").count(),
            "medium_threats": queryset.filter(severity="medium").count(),
            "low_threats": queryset.filter(severity="low").count(),
            "blocked_ips": queryset.filter(is_blocked=True)
            .values("source_ip")
            .distinct()
            .count(),
            "resolved_threats": queryset.filter(is_resolved=True).count(),
            "unresolved_threats": queryset.filter(is_resolved=False).count(),
            "top_attackers": list(
                queryset.values("source_ip")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
            ),
            "recent_threats": ThreatLogListSerializer(
                queryset.order_by("-detected_at")[:20], many=True
            ).data,
        }

        return Response(stats)

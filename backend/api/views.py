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

logger = logging.getLogger('firedog.api')


class StatisticsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet per visualizzare statistics
    
    Endpoints:
    - GET /api/targets/{target_id}/stats/ - Lista tutte le stats
    - GET /api/targets/{target_id}/stats/latest/ - Ultima statistica
    - GET /api/targets/{target_id}/stats/{id}/ - Statistica specifica
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['collected_at']
    
    def get_queryset(self):
        """Filtra stats per target"""
        from api.models import Statistics
        target_id = self.kwargs.get('target_pk')
        return Statistics.objects.filter(target_id=target_id).order_by('-collected_at')
    
    def get_serializer_class(self):
        from api.serializers import StatisticsSerializer
        return StatisticsSerializer
    
    @action(detail=False, methods=['get'])
    def latest(self, request, target_pk=None):
        """
        GET /api/targets/{target_id}/stats/latest/
        
        Restituisce l'ultima statistica registrata
        """
        stats = self.get_queryset().first()
        
        if not stats:
            return Response(
                {'error': 'No statistics available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def history(self, request, target_pk=None):
        """
        GET /api/targets/{target_id}/stats/history/?hours=24
        
        Restituisce lo storico stats nelle ultime N ore
        """
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        
        stats = self.get_queryset().filter(collected_at__gte=since)
        serializer = self.get_serializer(stats, many=True)
        
        return Response({
            'hours': hours,
            'count': stats.count(),
            'results': serializer.data
        })


class ThreatLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet per visualizzare threats
    
    Endpoints:
    - GET /api/targets/{target_id}/threats/ - Lista threats con filtri
    - GET /api/targets/{target_id}/threats/{id}/ - Threat specifico
    - POST /api/targets/{target_id}/threats/{id}/acknowledge/ - Acknowledge threat
    - GET /api/targets/{target_id}/threats/summary/ - Riepilogo threats
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['classification', 'threat_type', 'acknowledged', 'source_ip']
    
    def get_queryset(self):
        """Filtra threats per target"""
        from threats.models import ThreatLog
        target_id = self.kwargs.get('target_pk')
        return ThreatLog.objects.filter(target_id=target_id).order_by('-detected_at')
    
    def get_serializer_class(self):
        from threats.serializers import ThreatLogSerializer
        return ThreatLogSerializer
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, target_pk=None, pk=None):
        """
        POST /api/targets/{target_id}/threats/{id}/acknowledge/
        
        Marca una minaccia come acknowledged
        """
        threat = self.get_object()
        threat.acknowledged = True
        threat.save()
        
        # Log audit
        from audit.models import AuditLog
        AuditLog.log_action(
            username=request.user.username,
            action='threat.acknowledge',
            target_id=target_pk,
            details={'threat_id': pk, 'source_ip': str(threat.source_ip)},
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        serializer = self.get_serializer(threat)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request, target_pk=None):
        """
        GET /api/targets/{target_id}/threats/summary/?hours=24
        
        Restituisce riepilogo threats per severity
        """
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        
        threats = self.get_queryset().filter(detected_at__gte=since)
        
        summary = {
            'total': threats.count(),
            'by_classification': {
                'critical': threats.filter(classification='CRITICAL').count(),
                'high': threats.filter(classification='HIGH').count(),
                'medium': threats.filter(classification='MEDIUM').count(),
                'low': threats.filter(classification='LOW').count(),
            },
            'acknowledged': threats.filter(acknowledged=True).count(),
            'unacknowledged': threats.filter(acknowledged=False).count(),
            'top_attackers': list(
                threats.values('source_ip')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            )
        }
        
        return Response(summary)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet per visualizzare audit logs
    
    Endpoints:
    - GET /api/logs/audit/ - Lista audit logs
    - GET /api/logs/audit/{id}/ - Log specifico
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['username', 'action', 'target']
    
    def get_queryset(self):
        from audit.models import AuditLog
        return AuditLog.objects.all().order_by('-timestamp')
    
    def get_serializer_class(self):
        from audit.serializers import AuditLogSerializer
        return AuditLogSerializer
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        GET /api/logs/audit/recent/?hours=24&limit=100
        
        Ultimi N audit logs
        """
        hours = int(request.query_params.get('hours', 24))
        limit = int(request.query_params.get('limit', 100))
        since = timezone.now() - timedelta(hours=hours)
        
        logs = self.get_queryset().filter(timestamp__gte=since)[:limit]
        serializer = self.get_serializer(logs, many=True)
        
        return Response({
            'count': logs.count(),
            'results': serializer.data
        })


class NetworkTrafficViewSet(viewsets.ViewSet):
    """
    ViewSet per analisi traffico rete
    
    Endpoints:
    - GET /api/targets/{target_id}/traffic/realtime/ - Dati real-time
    - GET /api/targets/{target_id}/traffic/analyze/ - Analisi traffico
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def realtime(self, request, target_pk=None):
        """
        GET /api/targets/{target_id}/traffic/realtime/
        
        Ottiene stats in tempo reale
        """
        from targets.models import Target
        from api.models import Statistics
        
        try:
            target = Target.objects.get(id=target_pk)
            
            # Ultime 10 statistics per grafico
            recent_stats = Statistics.objects.filter(
                target=target
            ).order_by('-collected_at')[:10]
            
            from api.serializers import StatisticsSerializer
            serializer = StatisticsSerializer(recent_stats, many=True)
            
            return Response({
                'target': {
                    'id': target.id,
                    'hostname': target.hostname,
                    'ip_address': str(target.ip_address),
                    'status': target.status
                },
                'statistics': serializer.data
            })
            
        except Target.DoesNotExist:
            return Response(
                {'error': 'Target not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def analyze(self, request, target_pk=None):
        """
        POST /api/targets/{target_id}/traffic/analyze/
        Body: {"hours": 24}
        
        Triggera analisi traffico sul target
        """
        from targets.models import Target
        from core.ssh_manager import SSHManager, SSHConnectionError
        
        hours = request.data.get('hours', 1)
        
        try:
            target = Target.objects.get(id=target_pk)
            
            if target.status != 'online':
                return Response(
                    {'error': 'Target is not online'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            # Connessione SSH e analisi
            ssh = SSHManager(
                host=target.ip_address,
                port=target.ssh_port,
                username=target.ssh_user
            )
            ssh.connect()
            
            analysis = ssh.analyze_traffic(hours=hours)
            ssh.disconnect()
            
            if not analysis:
                return Response(
                    {'error': 'Analysis failed'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Log audit
            from audit.models import AuditLog
            AuditLog.log_action(
                username=request.user.username,
                action='traffic.analyze',
                target=target,
                details={'hours': hours},
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            return Response(analysis)
            
        except Target.DoesNotExist:
            return Response(
                {'error': 'Target not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except SSHConnectionError as e:
            return Response(
                {'error': f'SSH connection failed: {str(e)}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class PerformanceViewSet(viewsets.ViewSet):
    """
    ViewSet per metriche performance sistema
    
    Endpoints:
    - GET /api/targets/{target_id}/performance/ - Metriche sistema
    """
    permission_classes = [IsAuthenticated]
    
    def list(self, request, target_pk=None):
        """
        GET /api/targets/{target_id}/performance/
        
        Ottiene metriche CPU, RAM, Disk (future implementation)
        """
        # TODO: Implementare quando saranno disponibili i comandi
        # per recuperare metriche sistema dal target
        
        return Response({
            'message': 'Performance monitoring not yet implemented',
            'planned_metrics': [
                'cpu_usage_percent',
                'memory_usage_percent',
                'disk_usage_percent',
                'network_io_bytes'
            ]
        })


# ============================================
# URL ROUTING
# ============================================
# Aggiungi in backend/firedog/urls.py:
#
# from rest_framework_nested import routers
# from api.views import (
#     StatisticsViewSet,
#     ThreatLogViewSet,
#     AuditLogViewSet,
#     NetworkTrafficViewSet,
#     PerformanceViewSet
# )
#
# # Nested router per target-specific endpoints
# targets_router = routers.NestedSimpleRouter(router, r'targets', lookup='target')
# targets_router.register(r'stats', StatisticsViewSet, basename='target-stats')
# targets_router.register(r'threats', ThreatLogViewSet, basename='target-threats')
# targets_router.register(r'traffic', NetworkTrafficViewSet, basename='target-traffic')
# targets_router.register(r'performance', PerformanceViewSet, basename='target-performance')
#
# # Logs endpoints (non nested)
# router.register(r'logs/audit', AuditLogViewSet, basename='audit-logs')
#
# urlpatterns += targets_router.urls

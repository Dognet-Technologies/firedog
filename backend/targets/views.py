"""
Views per l'app Targets - API endpoints per gestione target remoti
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
import logging

from .models import Target
from .serializers import TargetSerializer, TargetListSerializer, TargetCreateSerializer
from core.ssh_manager import SSHManager, SSHConnectionError
from audit.models import AuditLog

logger = logging.getLogger('firedog.targets')


class TargetViewSet(viewsets.ModelViewSet):
    """ViewSet per gestione Target"""
    
    queryset = Target.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'ip_address']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TargetListSerializer
        elif self.action == 'create':
            return TargetCreateSerializer
        return TargetSerializer
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Testa connessione SSH al target"""
        target = self.get_object()
        
        try:
            ssh = SSHManager(host=target.ip_address, port=target.ssh_port, username=target.ssh_user)
            ssh.connect()
            user_exists = ssh.check_user_exists(target.ssh_user)
            exit_code, stdout, stderr = ssh.execute_command('whoami')
            ssh.disconnect()
            
            target.mark_online()
            
            return Response({
                'success': True,
                'message': 'Connessione SSH riuscita',
                'user_exists': user_exists,
                'whoami': stdout.strip()
            })
            
        except SSHConnectionError as e:
            target.mark_offline(str(e))
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def install(self, request, pk=None):
        """Installa pacchetto firedog sul target"""
        target = self.get_object()
        
        # Permetti reinstall se richiesto esplicitamente
        force_reinstall = request.data.get('force_reinstall', False)
        
        if target.status == 'online' and target.firedog_version and not force_reinstall:
            return Response({
                'error': 'Firedog già installato',
                'hint': 'Use force_reinstall=true to reinstall'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Se è una reinstall, logga l'evento
        if target.status == 'online' and target.firedog_version:
            from audit.models import AuditLog
            AuditLog.objects.create(
                username=request.user.username,
                action='target.reinstall',
                target=target,
                details={'previous_version': target.firedog_version},
                ip_address=request.META.get('REMOTE_ADDR')
            )
        
        target.status = 'installing'
        target.save(update_fields=['status'])
        
        # Qui verrà chiamato il task Celery
        from targets.tasks import install_firedog_on_target
        install_firedog_on_target.delay(target.id, request.user.id)
        
        return Response({'success': True, 'message': 'Installazione avviata', 'status': 'installing'})

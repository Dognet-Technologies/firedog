"""
Views per agent_manager app
REST API per gestione agent
"""
import secrets
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import AgentAPIKey, PairingSession, AgentConnection, AgentCommand, AgentHeartbeat
from .serializers import (
    AgentAPIKeySerializer, PairingSessionSerializer,
    AgentConnectionSerializer, AgentCommandSerializer, AgentHeartbeatSerializer
)
from targets.models import Target


class AgentAPIKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet per gestione API Keys
    """
    queryset = AgentAPIKey.objects.all()
    serializer_class = AgentAPIKeySerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Genera una nuova API key
        POST /api/agent/api-keys/generate/
        """
        # Genera chiave raw (64 caratteri)
        raw_key = secrets.token_urlsafe(48)

        # Crea hash
        key_hash = AgentAPIKey.hash_key(raw_key)

        # Crea record nel DB
        api_key = AgentAPIKey.objects.create(
            key_hash=key_hash,
            is_active=True,
            created_by=request.user.username
        )

        serializer = self.get_serializer(api_key)

        # Ritorna la chiave raw SOLO UNA VOLTA
        return Response({
            'api_key': serializer.data,
            'raw_key': raw_key,
            'warning': 'Save this key! It will not be shown again.'
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """
        Disattiva una API key
        POST /api/agent/api-keys/{id}/deactivate/
        """
        api_key = self.get_object()
        api_key.is_active = False
        api_key.save(update_fields=['is_active'])

        serializer = self.get_serializer(api_key)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        Attiva una API key (disattiva tutte le altre)
        POST /api/agent/api-keys/{id}/activate/
        """
        api_key = self.get_object()
        api_key.is_active = True
        api_key.save()  # Il metodo save() già disattiva le altre

        serializer = self.get_serializer(api_key)
        return Response(serializer.data)


class PairingSessionViewSet(viewsets.ModelViewSet):
    """
    ViewSet per gestione sessioni di pairing
    """
    queryset = PairingSession.objects.all()
    serializer_class = PairingSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtra per target se specificato"""
        queryset = super().get_queryset()
        target_id = self.request.query_params.get('target_id')
        if target_id:
            queryset = queryset.filter(target_id=target_id)
        return queryset

    @action(detail=False, methods=['post'])
    def start(self, request):
        """
        Avvia una nuova sessione di pairing
        POST /api/agent/pairing/start/
        Body: {"target_id": 123}
        """
        target_id = request.data.get('target_id')

        if not target_id:
            return Response(
                {'error': 'target_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target = Target.objects.get(pk=target_id)
        except Target.DoesNotExist:
            return Response(
                {'error': 'Target not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verifica che il target abbia identity_hash
        if not target.identity_hash:
            return Response(
                {'error': 'Target does not have identity_hash set. Please configure IP, hostname and MAC address.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crea nuova sessione di pairing
        session = PairingSession.objects.create(
            target=target,
            status='waiting'
        )

        # Aggiorna stato target
        target.status = 'pairing'
        target.save(update_fields=['status'])

        serializer = self.get_serializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        Ottiene lo status di una sessione di pairing
        GET /api/agent/pairing/{id}/status/
        """
        session = self.get_object()

        # Verifica se è scaduta
        if session.is_expired and session.status in ['waiting', 'verifying_api', 'verifying_hash']:
            session.status = 'expired'
            session.save(update_fields=['status'])

            # Reset target status
            session.target.status = 'unpaired'
            session.target.save(update_fields=['status'])

        serializer = self.get_serializer(session)
        return Response(serializer.data)


class AgentConnectionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet per visualizzare connessioni agent (solo lettura)
    """
    queryset = AgentConnection.objects.all()
    serializer_class = AgentConnectionSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def online(self, request):
        """
        Lista agent online
        GET /api/agent/connections/online/
        """
        connections = self.queryset.filter(is_online=True)
        serializer = self.get_serializer(connections, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def offline(self, request):
        """
        Lista agent offline
        GET /api/agent/connections/offline/
        """
        connections = self.queryset.filter(is_online=False)
        serializer = self.get_serializer(connections, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def disconnect(self, request, pk=None):
        """
        Forza disconnessione di un agent
        POST /api/agent/connections/{target_id}/disconnect/
        """
        connection = self.get_object()

        # Invia comando di disconnessione via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.send)(
            connection.websocket_channel,
            {
                'type': 'disconnect_agent',
                'reason': 'Disconnected by admin'
            }
        )

        connection.mark_offline()

        serializer = self.get_serializer(connection)
        return Response(serializer.data)


class AgentCommandViewSet(viewsets.ModelViewSet):
    """
    ViewSet per gestione comandi agent
    """
    queryset = AgentCommand.objects.all()
    serializer_class = AgentCommandSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtra per target se specificato"""
        queryset = super().get_queryset()
        target_id = self.request.query_params.get('target_id')
        if target_id:
            queryset = queryset.filter(target_id=target_id)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    def create(self, request, *args, **kwargs):
        """
        Crea e invia un comando all'agent
        POST /api/agent/commands/
        Body: {
            "target": 123,
            "action": "add_rule",
            "payload": {...},
            "timeout_seconds": 30
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Crea comando
        command = serializer.save()

        # Verifica che l'agent sia online
        try:
            connection = AgentConnection.objects.get(target=command.target, is_online=True)

            # Invia comando via WebSocket
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.send)(
                connection.websocket_channel,
                {
                    'type': 'send_command',
                    'command_id': str(command.command_id),
                    'action': command.action,
                    'payload': command.payload
                }
            )

            command.mark_sent()

        except AgentConnection.DoesNotExist:
            command.mark_failed('Agent is not connected')

        headers = self.get_success_headers(serializer.data)
        return Response(
            self.get_serializer(command).data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """
        Lista comandi pendenti
        GET /api/agent/commands/pending/
        """
        commands = self.queryset.filter(status='pending')
        serializer = self.get_serializer(commands, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """
        Riprova l'esecuzione di un comando fallito
        POST /api/agent/commands/{id}/retry/
        """
        command = self.get_object()

        if command.status not in ['failed', 'timeout']:
            return Response(
                {'error': 'Can only retry failed or timeout commands'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Reset status
        command.status = 'pending'
        command.sent_at = None
        command.completed_at = None
        command.error_message = ''
        command.save()

        # Riprova invio
        try:
            connection = AgentConnection.objects.get(target=command.target, is_online=True)

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.send)(
                connection.websocket_channel,
                {
                    'type': 'send_command',
                    'command_id': str(command.command_id),
                    'action': command.action,
                    'payload': command.payload
                }
            )

            command.mark_sent()

        except AgentConnection.DoesNotExist:
            command.mark_failed('Agent is not connected')

        serializer = self.get_serializer(command)
        return Response(serializer.data)


class AgentHeartbeatViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet per visualizzare heartbeat (solo lettura)
    """
    queryset = AgentHeartbeat.objects.all()
    serializer_class = AgentHeartbeatSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtra per target e limita a ultimi 100"""
        queryset = super().get_queryset()
        target_id = self.request.query_params.get('target_id')
        if target_id:
            queryset = queryset.filter(target_id=target_id)

        # Limita a ultimi 100 record
        return queryset[:100]

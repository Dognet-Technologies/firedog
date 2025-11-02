from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import DiscoveredHost
from .serializers import DiscoveredHostSerializer, DiscoveredHostListSerializer

class DiscoveredHostViewSet(viewsets.ModelViewSet):
    queryset = DiscoveredHost.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return DiscoveredHostListSerializer
        return DiscoveredHostSerializer
    
    @action(detail=False, methods=['post'])
    def scan(self, request):
        from discovery.tasks import discover_network
        discover_network.delay()
        return Response({'success': True, 'message': 'Network scan avviato'})

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import FirewallRule
from .serializers import FirewallRuleSerializer, FirewallRuleListSerializer

class FirewallRuleViewSet(viewsets.ModelViewSet):
    queryset = FirewallRule.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['target', 'chain', 'protocol', 'action', 'is_custom', 'is_synced']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return FirewallRuleListSerializer
        return FirewallRuleSerializer

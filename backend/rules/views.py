"""
Views per Rules API
Gestione regole firewall su DB, dispatchate all'agent via WebSocket
"""

import logging
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from accounts.permissions import IsAdminOrReadOnly
from .models import FirewallRule
from .serializers import FirewallRuleSerializer, FirewallRuleListSerializer
from .services import dispatch_add_rule, dispatch_remove_rule

logger = logging.getLogger("firedog.rules_api")


class FirewallRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet per regole firewall (CRUD su DB)

    Permissions:
    - GET/LIST: Tutti gli utenti autenticati
    - POST/PUT/PATCH/DELETE: Solo Admin
    """

    queryset = FirewallRule.objects.all()
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "target",
        "chain",
        "protocol",
        "action",
        "is_custom",
        "is_synced",
    ]

    def get_serializer_class(self):
        if self.action == "list":
            return FirewallRuleListSerializer
        return FirewallRuleSerializer

    def perform_create(self, serializer):
        """Salva la rule in DB e la dispatcha all'agent del target via WS.

        Se l'agent non è connesso, la rule viene comunque persistita con
        is_synced=False: sarà la successiva snapshot dell'agent a riconciliarla
        (o l'utente potrà ri-applicarla manualmente).
        """
        rule = serializer.save(is_custom=True, is_synced=False)
        dispatch_add_rule(rule)

    def perform_destroy(self, instance):
        """Cancella la rule lato server e chiede all'agent di rimuoverla.

        Per semplicità V1: se l'agent non è connesso, eliminiamo comunque dal DB
        (l'utente potrà fare cleanup manuale o aspettare la prossima snapshot
        che ri-osserverà la rule come is_custom=False).
        """
        target = instance.target
        rule_number = instance.rule_number
        chain = instance.chain
        instance.delete()
        dispatch_remove_rule(target, chain, rule_number)

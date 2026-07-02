"""
View del server MCP:

- MCPView: endpoint JSON-RPC POST /api/mcp, autenticazione Bearer-only con
  API key per-utente. CSRF-exempt per contratto (§3): sicuro perché non si
  affida mai a cookie di sessione.
- MCPAPIKeyViewSet: gestione chiavi dell'utente corrente, esposta sotto
  /api/settings/mcp-keys/ (config utente nella pagina Settings).
"""

import logging

from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import MCPAPIKeyAuthentication
from .jsonrpc import dispatch
from .models import MCPAPIKey
from .serializers import MCPAPIKeySerializer

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class MCPView(APIView):
    """Endpoint MCP: JSON-RPC 2.0, richieste singole e batch."""

    # Bearer-only: nessuna SessionAuthentication, quindi niente CSRF ambient
    authentication_classes = [MCPAPIKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload, http_status = dispatch(request.body, request.user)
        if payload is None:
            # Batch/richiesta di sole notifiche: 202 Accepted, body vuoto
            return HttpResponse(status=http_status)
        return JsonResponse(payload, status=http_status, safe=False)


class MCPAPIKeyViewSet(viewsets.ModelViewSet):
    """
    Gestione API key MCP dell'utente autenticato.

    Endpoints:
    - GET    /api/settings/mcp-keys/           - Lista chiavi proprie
    - POST   /api/settings/mcp-keys/           - Crea chiave (la chiave in chiaro
                                                 è restituita SOLO in questa risposta)
    - DELETE /api/settings/mcp-keys/{id}/      - Elimina chiave
    - POST   /api/settings/mcp-keys/{id}/revoke/ - Revoca (disattiva) chiave
    """

    serializer_class = MCPAPIKeySerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        # Ogni utente vede e gestisce solo le proprie chiavi
        return MCPAPIKey.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance, raw_key = MCPAPIKey.create_for_user(
            user=request.user,
            name=serializer.validated_data["name"],
            expires_at=serializer.validated_data.get("expires_at"),
        )
        logger.info(
            "Creata API key MCP '%s' per l'utente %s", instance.name, request.user
        )

        data = self.get_serializer(instance).data
        # La chiave in chiaro è visibile solo ora: non è mai più recuperabile
        data["key"] = raw_key
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        api_key = self.get_object()
        api_key.is_active = False
        api_key.save(update_fields=["is_active"])
        logger.info(
            "Revocata API key MCP '%s' dell'utente %s", api_key.name, request.user
        )
        return Response(self.get_serializer(api_key).data)

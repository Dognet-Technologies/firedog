"""
Autenticazione Bearer con API key per l'endpoint MCP.

La chiave impersona l'utente proprietario: request.user diventa l'owner
della chiave, quindi RBAC e audit esistenti si applicano invariati.
L'endpoint è Bearer-only: nessuna dipendenza da cookie di sessione,
quindi l'esenzione CSRF è sicura (contratto MCP §3).
"""

import logging

from rest_framework import authentication, exceptions

from .models import MCPAPIKey

logger = logging.getLogger(__name__)

AUTH_SCHEME = "Bearer"


class MCPAPIKeyAuthentication(authentication.BaseAuthentication):
    """Autentica `Authorization: Bearer fd_<...>` contro le MCPAPIKey attive."""

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode(
            "utf-8", errors="ignore"
        )
        if not header or not header.lower().startswith(AUTH_SCHEME.lower() + " "):
            return None

        raw_key = header[len(AUTH_SCHEME) + 1 :].strip()
        if not raw_key:
            raise exceptions.AuthenticationFailed("API key mancante.")

        key_hash = MCPAPIKey.hash_key(raw_key)
        try:
            api_key = MCPAPIKey.objects.select_related("user").get(key_hash=key_hash)
        except MCPAPIKey.DoesNotExist:
            # Messaggio generico: non rivelare se la chiave esiste
            raise exceptions.AuthenticationFailed("API key non valida o scaduta.")

        if not api_key.is_valid():
            raise exceptions.AuthenticationFailed("API key non valida o scaduta.")

        if not api_key.user.is_active:
            raise exceptions.AuthenticationFailed("Utente disabilitato.")

        api_key.mark_used()
        return (api_key.user, api_key)

    def authenticate_header(self, request):
        return AUTH_SCHEME

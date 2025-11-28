"""
Custom Permissions per FireDog
Sistema basato su ruoli: Admin e Reporter
"""
from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Permission: Solo utenti nel gruppo 'Admin' possono accedere

    Admin può:
    - Creare/modificare/eliminare targets
    - Aggiungere/rimuovere regole firewall
    - Bloccare IP
    - Modificare configurazioni
    - Tutto ciò che può fare un Reporter
    """
    message = 'Solo gli amministratori possono eseguire questa azione.'

    def has_permission(self, request, view):
        # Utente deve essere autenticato
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser ha sempre accesso
        if request.user.is_superuser:
            return True

        # Check gruppo Admin
        return request.user.groups.filter(name='Admin').exists()


class IsReporterOrAdmin(permissions.BasePermission):
    """
    Permission: Utenti nel gruppo 'Reporter' o 'Admin'

    Reporter può:
    - Visualizzare targets e stato
    - Visualizzare regole firewall
    - Visualizzare minacce e statistiche
    - Visualizzare logs

    Reporter NON può:
    - Creare/modificare/eliminare risorse
    - Aggiungere/rimuovere regole
    - Modificare configurazioni
    """
    message = 'Accesso negato. Richiesti permessi Reporter o superiori.'

    def has_permission(self, request, view):
        # Utente deve essere autenticato
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser ha sempre accesso
        if request.user.is_superuser:
            return True

        # Check gruppo Reporter o Admin
        return request.user.groups.filter(name__in=['Admin', 'Reporter']).exists()


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission: Admin può tutto, altri solo lettura (GET, HEAD, OPTIONS)

    Usato per API dove:
    - GET/LIST: Tutti gli utenti autenticati
    - POST/PUT/PATCH/DELETE: Solo Admin
    """
    message = 'Solo gli amministratori possono modificare questa risorsa.'

    def has_permission(self, request, view):
        # Utente deve essere autenticato
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser ha sempre accesso
        if request.user.is_superuser:
            return True

        # Metodi safe (GET, HEAD, OPTIONS) per tutti
        if request.method in permissions.SAFE_METHODS:
            return True

        # Metodi di modifica solo per Admin
        return request.user.groups.filter(name='Admin').exists()

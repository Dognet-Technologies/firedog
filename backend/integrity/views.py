from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsAdminOrReadOnly
from .models import FileIntegrity
from .serializers import FileIntegritySerializer, FileIntegrityListSerializer


class FileIntegrityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FileIntegrity.objects.all()
    # `approve` sopprime un alert di integrità file reale — decisione di
    # sicurezza, non lettura: sola lettura per Reporter, approvazione
    # solo Admin (stessa classe del CRITICAL su controllo accessi
    # trovato in code review, 2026-11).
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get_serializer_class(self):
        if self.action == "list":
            return FileIntegrityListSerializer
        return FileIntegritySerializer

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        file_integrity = self.get_object()
        notes = request.data.get("notes", "")
        file_integrity.approve_change(request.user, notes)
        return Response({"success": True, "message": "Modifica approvata"})

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import FileIntegrity
from .serializers import FileIntegritySerializer, FileIntegrityListSerializer

class FileIntegrityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FileIntegrity.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return FileIntegrityListSerializer
        return FileIntegritySerializer
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        file_integrity = self.get_object()
        notes = request.data.get('notes', '')
        file_integrity.approve_change(request.user, notes)
        return Response({'success': True, 'message': 'Modifica approvata'})

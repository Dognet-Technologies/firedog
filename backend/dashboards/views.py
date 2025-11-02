from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Dashboard, Widget
from .serializers import DashboardSerializer, DashboardListSerializer, WidgetSerializer

class DashboardViewSet(viewsets.ModelViewSet):
    queryset = Dashboard.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'list':
            return DashboardListSerializer
        return DashboardSerializer
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class WidgetViewSet(viewsets.ModelViewSet):
    queryset = Widget.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = WidgetSerializer
    
    def get_queryset(self):
        return self.queryset.filter(dashboard__user=self.request.user)

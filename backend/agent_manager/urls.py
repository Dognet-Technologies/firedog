"""
URL routing per agent_manager app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AgentAPIKeyViewSet, PairingSessionViewSet,
    AgentConnectionViewSet, AgentCommandViewSet, AgentHeartbeatViewSet,
    TargetGroupsViewSet
)

router = DefaultRouter()
router.register(r'api-keys', AgentAPIKeyViewSet, basename='agent-apikey')
router.register(r'pairing', PairingSessionViewSet, basename='agent-pairing')
router.register(r'connections', AgentConnectionViewSet, basename='agent-connection')
router.register(r'commands', AgentCommandViewSet, basename='agent-command')
router.register(r'heartbeats', AgentHeartbeatViewSet, basename='agent-heartbeat')
router.register(r'groups', TargetGroupsViewSet, basename='agent-groups')

urlpatterns = [
    path('', include(router.urls)),
]

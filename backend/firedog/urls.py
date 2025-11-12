"""
URL Configuration per FireDog
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# Import ViewSets
from targets.views import TargetViewSet
from rules.views import FirewallRuleViewSet
from threats.views import ThreatLogViewSet
from dashboards.views import DashboardViewSet, WidgetViewSet
from integrity.views import FileIntegrityViewSet
from discovery.views import DiscoveredHostViewSet
from audit.views import AuditLogViewSet

# from rest_framework_nested import routers
# from api.views import (
#     StatisticsViewSet,
#     ThreatLogViewSet,
#     AuditLogViewSet,
#     NetworkTrafficViewSet,
#     PerformanceViewSet
# )

# # Nested router per target-specific endpoints
# targets_router = routers.NestedSimpleRouter(router, r'targets', lookup='target')
# targets_router.register(r'stats', StatisticsViewSet, basename='target-stats')
# targets_router.register(r'threats', ThreatLogViewSet, basename='target-threats')
# targets_router.register(r'traffic', NetworkTrafficViewSet, basename='target-traffic')
# targets_router.register(r'performance', PerformanceViewSet, basename='target-performance')

# # Logs endpoints (non nested)
# router.register(r'logs/audit', AuditLogViewSet, basename='audit-logs')

# urlpatterns += targets_router.urls

# Router per API REST
router = DefaultRouter()
router.register(r'targets', TargetViewSet, basename='target')
router.register(r'rules', FirewallRuleViewSet, basename='firewallrule')
router.register(r'threats', ThreatLogViewSet, basename='threatlog')
router.register(r'dashboards', DashboardViewSet, basename='dashboard')
router.register(r'widgets', WidgetViewSet, basename='widget')
router.register(r'integrity', FileIntegrityViewSet, basename='fileintegrity')
router.register(r'discovery', DiscoveredHostViewSet, basename='discoveredhost')
router.register(r'audit', AuditLogViewSet, basename='auditlog')

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # JWT Authentication
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Gruppi
    path('api/', include('targets.urls_groups')),

    # API endpoints
    path('api/', include(router.urls)),
]

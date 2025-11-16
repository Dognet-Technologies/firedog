"""
URL Configuration per FireDog
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# Import ViewSets
from rules.views import FirewallRuleViewSet
from threats.views import ThreatLogViewSet
from dashboards.views import DashboardViewSet, WidgetViewSet
from integrity.views import FileIntegrityViewSet
from discovery.views import DiscoveredHostViewSet
from audit.views import AuditLogViewSet
from targets.views import WhitelistEntryViewSet, BlockedIPViewSet, TargetViewSet
from settings.views import SystemSettingsViewSet, SSHKeyViewSet, DatabaseManagementViewSet, NotificationViewSet, UserManagementViewSet

# Import Log Views
from api.views import LogAPIView, LogSourcesAPIView

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
router.register(r'whitelist', WhitelistEntryViewSet, basename='whitelist')
router.register(r'blocked-ips', BlockedIPViewSet, basename='blocked-ip')

# Settings ViewSets  ← AGGIUNGI
router.register(r'settings/settings', SystemSettingsViewSet, basename='systemsettings')
router.register(r'settings/ssh-keys', SSHKeyViewSet, basename='sshkey')
router.register(r'settings/database', DatabaseManagementViewSet, basename='database')
router.register(r'settings/notifications', NotificationViewSet, basename='notifications')
router.register(r'settings/user', UserManagementViewSet, basename='user')

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # JWT Authentication
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Log APIs
    path('api/logs/', LogAPIView.as_view(), name='logs'),
    path('api/logs/sources/', LogSourcesAPIView.as_view(), name='logs-sources'),
    
    # Gruppi
    path('api/', include('targets.urls_groups')),

    # Settings
#    path('api/settings/', include('settings.urls')),

    # API endpoints
    path('api/', include(router.urls)),
]
"""
URL Configuration per Settings App
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SystemSettingsViewSet,
    SSHKeyViewSet,
    DatabaseManagementViewSet,
    NotificationViewSet,
    UserManagementViewSet,
)


app_name = 'settings'

router = DefaultRouter()
router.register(r'settings', SystemSettingsViewSet, basename='systemsettings')
router.register(r'settings/ssh-keys', SSHKeyViewSet, basename='sshkey')
router.register(r'settings/database', DatabaseManagementViewSet, basename='database')
#router.register(r'ssh-keys', SSHKeyViewSet, basename='sshkey')
#router.register(r'database', DatabaseManagementViewSet, basename='database')
router.register(r'notifications', NotificationViewSet, basename='notifications')
router.register(r'user', UserManagementViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
]

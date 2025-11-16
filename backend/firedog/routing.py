"""
ASGI Routing Configuration per WebSocket
"""
from django.urls import re_path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from targets.consumers import SSHTerminalConsumer
from targets.install_consumer import InstallConsumer
from firedog.consumers import LogStreamConsumer, LogHistoryConsumer


websocket_urlpatterns = [
    re_path(r'ws/terminal/$', SSHTerminalConsumer.as_asgi()),
    re_path(r'ws/install/$', InstallConsumer.as_asgi()),
    re_path(r'ws/logs/stream/$', LogStreamConsumer.as_asgi()),
    re_path(r'ws/logs/history/$', LogHistoryConsumer.as_asgi()),
]
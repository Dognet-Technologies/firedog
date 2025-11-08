"""
ASGI Routing Configuration per WebSocket
"""
from django.urls import re_path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from targets.consumers import SSHTerminalConsumer


websocket_urlpatterns = [
    re_path(r'ws/terminal/$', SSHTerminalConsumer.as_asgi()),
]


application = ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})

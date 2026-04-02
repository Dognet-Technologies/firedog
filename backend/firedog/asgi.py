"""
ASGI config for firedog project.
Supporta HTTP (Django) e WebSocket (Channels)
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Imposta variabile ambiente Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firedog.settings")

# Inizializza Django ASGI application PRIMA di importare routing
django_asgi_app = get_asgi_application()

# Ora è sicuro importare il routing
from firedog.routing import websocket_urlpatterns

# ASGI application con supporto HTTP e WebSocket
application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)

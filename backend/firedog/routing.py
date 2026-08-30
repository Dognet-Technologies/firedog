"""
ASGI Routing Configuration per WebSocket
"""

from django.urls import re_path
from firedog.consumers import LogStreamConsumer, LogHistoryConsumer
from agent_manager.consumers import AgentConsumer

websocket_urlpatterns = [
    re_path(r"ws/logs/stream/$", LogStreamConsumer.as_asgi()),
    re_path(r"ws/logs/history/$", LogHistoryConsumer.as_asgi()),
    re_path(r"ws/agent/$", AgentConsumer.as_asgi()),  # Dog Agent WebSocket
]

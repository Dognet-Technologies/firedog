"""
Helpers per dispatchare comandi dall'API REST agli agent connessi via WebSocket.

Pattern:
    cmd = dispatch_command_to_agent(
        target, "add_rule",
        {"chain": "INPUT", ...},
        meta={"rule_id": 42},
    )
    # cmd è un AgentCommand persistito con status="pending".
    # Quando l'agent risponderà, handle_command_response aggiornerà lo status
    # e potrà rileggere `meta` da AgentCommand.payload["_meta"] per riconciliare.

Il dict `_meta` viene incluso nel payload inviato all'agent ma l'agent lo ignora
(deserializzazione tollerante ai campi sconosciuti), e ce lo ritroviamo intatto
in AgentCommand.payload via command_id.
"""

from __future__ import annotations

import uuid
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import AgentCommand, AgentConnection


class AgentNotConnected(Exception):
    """Sollevata quando un target non ha una connessione agent attiva."""


def dispatch_command_to_agent(
    target,
    action: str,
    payload: dict[str, Any],
    *,
    meta: dict[str, Any] | None = None,
) -> AgentCommand:
    """Invia un comando all'agent del target via channel layer."""
    connection = AgentConnection.objects.filter(target=target, is_online=True).first()
    if not connection or not connection.websocket_channel:
        raise AgentNotConnected(
            f"Target {target.id} ({target.hostname or target.ip_address}) non ha un agent connesso"
        )

    command_id = uuid.uuid4()
    full_payload = dict(payload)
    if meta:
        full_payload["_meta"] = meta

    command = AgentCommand.objects.create(
        target=target,
        action=action,
        payload=full_payload,
        status="pending",
        command_id=command_id,
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.send)(
        connection.websocket_channel,
        {
            "type": "send_command",
            "command_id": str(command_id),
            "action": action,
            "payload": full_payload,
        },
    )
    return command

"""
WebSocket Client per Dog Agent
Gestisce connessione WebSocket al server FireDog
"""
import asyncio
import json
import logging
import websockets
from typing import Callable, Dict

logger = logging.getLogger(__name__)


class WebSocketClient:
    """Client WebSocket per comunicazione con server"""

    def __init__(self, server_url: str, api_key: str, verify_ssl: bool = True):
        """
        Inizializza WebSocket client
        Args:
            server_url: URL server (es: https://firedog.example.com)
            api_key: API key per autenticazione
            verify_ssl: Verifica certificato SSL
        """
        # Converti HTTPS in WSS
        self.server_url = server_url.replace('https://', 'wss://').replace('http://', 'ws://')
        self.ws_url = f"{self.server_url}/ws/agent/"
        self.api_key = api_key
        self.verify_ssl = verify_ssl

        self.websocket = None
        self.connected = False
        self.handlers = {}
        self.receive_task = None

    async def connect(self) -> bool:
        """Connette al server WebSocket"""
        try:
            ssl_context = None if not self.verify_ssl else True
            self.websocket = await websockets.connect(self.ws_url, ssl=ssl_context)
            self.connected = True
            self.receive_task = asyncio.create_task(self.receive_loop())
            logger.info(f"Connected to {self.ws_url}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnette dal server"""
        self.connected = False
        if self.receive_task:
            self.receive_task.cancel()
        if self.websocket:
            await self.websocket.close()
        logger.info("Disconnected from server")

    async def send(self, data: Dict) -> bool:
        """
        Invia messaggio al server
        Args:
            data: Dizionario da inviare (verrà convertito in JSON)
        """
        if not self.connected or not self.websocket:
            logger.warning("Cannot send: not connected")
            return False

        try:
            message = json.dumps(data)
            await self.websocket.send(message)
            logger.debug(f"Sent message type: {data.get('type')}")
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    async def receive_loop(self):
        """Loop ricezione messaggi"""
        while self.connected:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                message_type = data.get('type')

                logger.debug(f"Received message type: {message_type}")

                # Chiama handler se registrato
                if message_type in self.handlers:
                    await self.handlers[message_type](data)

            except websockets.exceptions.ConnectionClosed:
                self.connected = False
                logger.warning("Connection closed by server")
                break
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")

    def on_message(self, message_type: str, handler: Callable):
        """
        Registra handler per tipo messaggio
        Args:
            message_type: Tipo messaggio (es: 'pairing_status')
            handler: Funzione async da chiamare quando riceve il messaggio
        """
        self.handlers[message_type] = handler

    @property
    def is_connected(self) -> bool:
        """Verifica se connesso"""
        return self.connected and self.websocket is not None

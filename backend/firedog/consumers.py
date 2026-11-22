"""
WebSocket Consumers per FireDog
Log Streaming in tempo reale
"""

import json
import asyncio
import logging
import os
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings

logger = logging.getLogger(__name__)

LOG_VIEWER_GROUPS = ("Admin", "Reporter")
MAX_HISTORY_LINES = 5000


def _token_from_scope(scope):
    query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
    values = query.get("token") or []
    return values[0] if values else None


@database_sync_to_async
def _load_log_viewer(user_id):
    from django.contrib.auth.models import User

    user = User.objects.filter(id=user_id, is_active=True).first()
    if user is None:
        return None
    if user.is_superuser or user.groups.filter(name__in=LOG_VIEWER_GROUPS).exists():
        return user
    return None


async def authenticate_ws(scope):
    """Utente attivo con ruolo Admin/Reporter dal JWT in query string, o None.

    Il token non viene mai scritto nei log (prima finivano su stdout, quindi
    nel journal, sia la query string sia i primi 20 caratteri del token).
    """
    token = _token_from_scope(scope)
    if not token:
        return None
    try:
        from rest_framework_simplejwt.tokens import AccessToken

        user_id = AccessToken(token)["user_id"]
    except Exception:
        logger.info("log WS: token non valido o scaduto")
        return None
    user = await _load_log_viewer(user_id)
    if user is None:
        logger.info("log WS: utente %s inattivo o senza ruolo", user_id)
    return user


class LogStreamConsumer(AsyncWebsocketConsumer):
    """
    Consumer per streaming real-time dei log
    """

    async def connect(self):
        """Accetta connessione WebSocket"""
        user = await authenticate_ws(self.scope)
        if user is None:
            await self.close()
            return
        self.scope["user"] = user

        await self.accept()

        # Invia messaggio di benvenuto
        await self.send(
            text_data=json.dumps(
                {"type": "connection", "message": "Connected to log stream"}
            )
        )

        # Avvia streaming
        self.streaming = True
        asyncio.create_task(self.stream_logs())

    async def disconnect(self, close_code):
        """Chiude connessione"""
        self.streaming = False

    async def receive(self, text_data):
        """Riceve comandi dal client"""
        try:
            data = json.loads(text_data)
            command = data.get("command")

            if command == "pause":
                self.streaming = False
            elif command == "resume":
                self.streaming = True
                asyncio.create_task(self.stream_logs())
            elif command == "clear":
                # Invia comando per pulire il client
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "clear",
                        }
                    )
                )
        except json.JSONDecodeError:
            pass

    async def stream_logs(self):
        """Stream dei log in tempo reale"""
        logs_dir = settings.LOGS_DIR

        # File di log da monitorare
        log_files = {
            "django": logs_dir / "django.log",
            "celery": logs_dir / "celery.log",
            "application": logs_dir / "application.log",
        }

        # Posizioni correnti nei file
        positions = {}
        for source, file_path in log_files.items():
            if os.path.exists(file_path):
                # Inizia dalla fine del file
                with open(file_path, "r") as f:
                    f.seek(0, 2)  # Vai alla fine
                    positions[source] = f.tell()
            else:
                positions[source] = 0

        while self.streaming:
            try:
                # Leggi nuove righe da ogni file
                for source, file_path in log_files.items():
                    if not os.path.exists(file_path):
                        continue

                    with open(file_path, "r") as f:
                        f.seek(positions[source])
                        new_lines = f.readlines()
                        positions[source] = f.tell()

                        # Invia ogni nuova riga
                        for line in new_lines:
                            line = line.strip()
                            if line:
                                await self.send(
                                    text_data=json.dumps(
                                        {
                                            "type": "log",
                                            "source": source,
                                            "message": line,
                                            "timestamp": None,  # Il timestamp è già nella riga
                                        }
                                    )
                                )

                # Attendi prima di controllare nuovi log
                await asyncio.sleep(0.5)

            except Exception:
                logger.exception("log stream: errore di lettura")
                await self.send(
                    text_data=json.dumps({"type": "error", "message": "Log read error"})
                )
                await asyncio.sleep(1)


class LogHistoryConsumer(AsyncWebsocketConsumer):
    """
    Consumer per recuperare storico log
    """

    async def connect(self):
        """Accetta connessione"""
        user = await authenticate_ws(self.scope)
        if user is None:
            await self.close()
            return
        self.scope["user"] = user

        await self.accept()

    async def disconnect(self, close_code):
        """Chiude connessione"""

    async def receive(self, text_data):
        """Riceve richieste di storico"""
        try:
            data = json.loads(text_data)
            source = data.get("source", "django")
            lines = max(1, min(int(data.get("lines", 100)), MAX_HISTORY_LINES))

            # Leggi ultime N righe
            logs = await self.get_last_lines(source, lines)

            await self.send(
                text_data=json.dumps(
                    {"type": "history", "source": source, "logs": logs}
                )
            )

        except Exception:
            logger.exception("log history: richiesta non valida")
            await self.send(text_data=json.dumps({"type": "error", "message": "Invalid request"}))

    async def get_last_lines(self, source, n=100):
        """Recupera ultime N righe da un file di log"""
        logs_dir = settings.LOGS_DIR

        log_files = {
            "django": logs_dir / "django.log",
            "celery": logs_dir / "celery.log",
            "application": logs_dir / "application.log",
        }

        file_path = log_files.get(source)

        if not file_path or not os.path.exists(file_path):
            return []

        try:
            # Leggi file in modo efficiente (ultime N righe)
            with open(file_path, "r") as f:
                lines = f.readlines()
                return [line.strip() for line in lines[-n:] if line.strip()]
        except Exception:
            return []

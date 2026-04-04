"""
WebSocket Consumers per FireDog
Log Streaming in tempo reale
"""

import json
import asyncio
import os
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
from pathlib import Path


class LogStreamConsumer(AsyncWebsocketConsumer):
    """
    Consumer per streaming real-time dei log
    """

    async def connect(self):
        """Accetta connessione WebSocket"""
        print("WebSocket connection attempt...")

        # Estrai token dall'URL
        query_string = self.scope.get("query_string", b"").decode()
        print(f"Query string: {query_string}")

        params = {}
        if query_string:
            for param in query_string.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    params[key] = value

        token = params.get("token")
        print(f"Token received: {token[:20] if token else 'None'}...")

        if not token:
            print("No token provided, closing connection")
            await self.close()
            return

        # Valida il token JWT
        try:
            from rest_framework_simplejwt.tokens import AccessToken

            access_token = AccessToken(token)
            user_id = access_token["user_id"]
            print(f"Token valid, user_id: {user_id}")

            user = await self.get_user(user_id)

            if not user:
                print("User not found, closing connection")
                await self.close()
                return

            self.scope["user"] = user
            print(f"User authenticated: {user.username}")

        except Exception as e:
            print(f"WebSocket auth failed: {e}")
            await self.close()
            return

        await self.accept()
        print("WebSocket connection accepted!")

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
        print(f"WebSocket disconnected: {close_code}")
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

            except Exception as e:
                await self.send(
                    text_data=json.dumps({"type": "error", "message": str(e)})
                )
                await asyncio.sleep(1)

    @database_sync_to_async
    def get_user(self, user_id):
        """Recupera utente dal database"""
        from django.contrib.auth.models import User

        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None


class LogHistoryConsumer(AsyncWebsocketConsumer):
    """
    Consumer per recuperare storico log
    """

    async def connect(self):
        """Accetta connessione"""
        # Estrai token dall'URL
        query_string = self.scope.get("query_string", b"").decode()
        params = {}
        if query_string:
            for param in query_string.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    params[key] = value

        token = params.get("token")

        if not token:
            await self.close()
            return

        try:
            from rest_framework_simplejwt.tokens import AccessToken

            access_token = AccessToken(token)
            user_id = access_token["user_id"]
            user = await self.get_user(user_id)

            if not user:
                await self.close()
                return

            self.scope["user"] = user

        except Exception:
            await self.close()
            return

        await self.accept()

    async def disconnect(self, close_code):
        """Chiude connessione"""
        pass

    async def receive(self, text_data):
        """Riceve richieste di storico"""
        try:
            data = json.loads(text_data)
            source = data.get("source", "django")
            lines = data.get("lines", 100)

            # Leggi ultime N righe
            logs = await self.get_last_lines(source, lines)

            await self.send(
                text_data=json.dumps(
                    {"type": "history", "source": source, "logs": logs}
                )
            )

        except Exception as e:
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

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

    @database_sync_to_async
    def get_user(self, user_id):
        """Recupera utente dal database"""
        from django.contrib.auth.models import User

        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

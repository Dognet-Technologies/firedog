"""
WebSocket Consumer per Terminale SSH Interattivo
Gestisce comunicazione bidirezionale tra frontend e sessione SSH PTY
"""
import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

logger = logging.getLogger('firedog.terminal_consumer')


class SSHTerminalConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket per terminale SSH interattivo
    
    Messaggi ricevuti dal client (frontend):
    - {"type": "connect", "target_id": 1, "width": 80, "height": 24}
    - {"type": "input", "data": "ls\n"}
    - {"type": "resize", "width": 100, "height": 30}
    - {"type": "disconnect"}
    
    Messaggi inviati al client:
    - {"type": "connected", "message": "Connected to target"}
    - {"type": "output", "data": "command output"}
    - {"type": "error", "message": "Error description"}
    - {"type": "disconnected", "message": "Session closed"}
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target = None
        self.ssh_manager = None
        self.read_task = None
        self.is_connected = False
    
    async def connect(self):
        """Gestisce connessione WebSocket dal client"""
        # Accetta connessione WebSocket
        await self.accept()
        
        logger.info(f"WebSocket connesso: {self.channel_name}")
    
    async def disconnect(self, close_code):
        """Gestisce disconnessione WebSocket"""
        logger.info(f"WebSocket disconnesso: {self.channel_name}, code: {close_code}")
        
        # Ferma task di lettura
        if self.read_task:
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass
        
        # Chiudi connessione SSH
        if self.ssh_manager:
            await sync_to_async(self.ssh_manager.disconnect)()
    
    async def receive(self, text_data):
        """
        Riceve messaggi dal client WebSocket
        
        Args:
            text_data: JSON string con comando
        """
        try:
            message = json.loads(text_data)
            msg_type = message.get('type')
            
            if msg_type == 'connect':
                await self.handle_connect(message)
            
            elif msg_type == 'input':
                await self.handle_input(message)
            
            elif msg_type == 'resize':
                await self.handle_resize(message)
            
            elif msg_type == 'disconnect':
                await self.handle_disconnect()
            
            else:
                logger.warning(f"Tipo messaggio sconosciuto: {msg_type}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Errore parsing JSON: {e}")
            await self.send_error("Invalid JSON format")
        
        except Exception as e:
            logger.exception(f"Errore gestione messaggio: {e}")
            await self.send_error(str(e))
    
    async def handle_connect(self, message):
        """
        Gestisce richiesta di connessione SSH al target
        
        Args:
            message: Dict con target_id, width, height
        """
        target_id = message.get('target_id')
        width = message.get('width', 80)
        height = message.get('height', 24)
        
        if not target_id:
            await self.send_error("Target ID mancante")
            return
        
        try:
            # Carica target dal database
            self.target = await self.get_target(target_id)
            
            if not self.target:
                await self.send_error(f"Target {target_id} non trovato")
                return
            
            # Importa SSHTerminalManager (import lazy per evitare problemi)
            from core.ssh_terminal_manager import SSHTerminalManager
            
            # Crea manager SSH
            self.ssh_manager = SSHTerminalManager(
                host=self.target.ip_address,
                port=self.target.ssh_port,
                username=self.target.ssh_user
            )
            
            # Connetti SSH
            connected = await sync_to_async(self.ssh_manager.connect)()
            
            if not connected:
                await self.send_error("Connessione SSH fallita")
                return
            
            # Avvia shell interattiva
            shell_started = await sync_to_async(
                self.ssh_manager.start_shell
            )(width=width, height=height)
            
            if not shell_started:
                await self.send_error("Avvio shell fallito")
                await sync_to_async(self.ssh_manager.disconnect)()
                return
            
            self.is_connected = True
            
            # Invia conferma connessione
            await self.send(text_data=json.dumps({
                'type': 'connected',
                'message': f'Connesso a {self.target.hostname} ({self.target.ip_address})'
            }))
            
            # Avvia task di lettura output SSH
            self.read_task = asyncio.create_task(self.read_ssh_output())
            
            logger.info(f"Terminale SSH avviato per target {target_id}")
        
        except Exception as e:
            logger.exception(f"Errore connessione target {target_id}: {e}")
            await self.send_error(f"Errore: {str(e)}")
    
    async def handle_input(self, message):
        """
        Gestisce input utente da inviare al terminale remoto
        
        Args:
            message: Dict con 'data' (stringa da inviare)
        """
        if not self.is_connected or not self.ssh_manager:
            await self.send_error("Non connesso al target")
            return
        
        data = message.get('data', '')
        
        try:
            # Invia dati al terminale remoto
            await sync_to_async(self.ssh_manager.send_data)(data)
        
        except Exception as e:
            logger.error(f"Errore invio input: {e}")
            await self.send_error(f"Errore invio: {str(e)}")
    
    async def handle_resize(self, message):
        """
        Gestisce ridimensionamento terminale
        
        Args:
            message: Dict con 'width' e 'height'
        """
        if not self.ssh_manager:
            return
        
        width = message.get('width', 80)
        height = message.get('height', 24)
        
        try:
            await sync_to_async(
                self.ssh_manager.resize_terminal
            )(width, height)
        
        except Exception as e:
            logger.error(f"Errore ridimensionamento: {e}")
    
    async def handle_disconnect(self):
        """Gestisce richiesta esplicita di disconnessione"""
        if self.ssh_manager:
            await sync_to_async(self.ssh_manager.disconnect)()
            self.is_connected = False
        
        await self.send(text_data=json.dumps({
            'type': 'disconnected',
            'message': 'Sessione terminata'
        }))
    
    async def read_ssh_output(self):
        """
        Task asincrono che legge continuamente output dal terminale SSH
        e lo invia al client WebSocket
        """
        try:
            while self.is_connected and self.ssh_manager:
                # Verifica se canale ancora attivo
                is_active = await sync_to_async(self.ssh_manager.is_active)()
                
                if not is_active:
                    logger.info("Canale SSH chiuso")
                    await self.send(text_data=json.dumps({
                        'type': 'disconnected',
                        'message': 'Connessione SSH chiusa'
                    }))
                    break
                
                # Leggi dati disponibili
                data = await sync_to_async(
                    self.ssh_manager.receive_data
                )(timeout=0.1)
                
                if data:
                    # Invia output al client
                    await self.send(text_data=json.dumps({
                        'type': 'output',
                        'data': data
                    }))
                
                # Piccolo delay per evitare busy-waiting
                await asyncio.sleep(0.05)
        
        except asyncio.CancelledError:
            logger.info("Task lettura SSH cancellato")
        
        except Exception as e:
            logger.exception(f"Errore lettura SSH output: {e}")
            await self.send_error(f"Errore lettura: {str(e)}")
    
    async def send_error(self, error_message: str):
        """
        Invia messaggio di errore al client
        
        Args:
            error_message: Descrizione errore
        """
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message
        }))
    
    @database_sync_to_async
    def get_target(self, target_id: int):
        """
        Carica target dal database (async wrapper)
        
        Args:
            target_id: ID del target
            
        Returns:
            Target instance o None
        """
        from targets.models import Target
        
        try:
            return Target.objects.get(id=target_id)
        except Target.DoesNotExist:
            return None

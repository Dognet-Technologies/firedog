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

        # Se c'era un'installazione in corso, verifica il risultato finale
        if self.target and self.target.status == 'installing':
            await self.verify_installation_result()

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

            elif msg_type == 'install_firedog':
                await self.handle_install_firedog(message)

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

    async def handle_install_firedog(self, message):
        """
        Gestisce installazione automatica di FireDog sul target
        Usa terminale PTY interattivo per permettere input password sudo

        Args:
            message: Dict con target_id, width, height, password (optional)
        """
        target_id = message.get('target_id')
        width = message.get('width', 80)
        height = message.get('height', 24)
        ssh_password = message.get('password')  # Password SSH per prima installazione

        if not target_id:
            await self.send_error("Target ID mancante")
            return

        try:
            # Carica target dal database
            self.target = await self.get_target(target_id)

            if not self.target:
                await self.send_error(f"Target {target_id} non trovato")
                return

            # Invia messaggio di benvenuto
            await self.send_output("\r\n\x1b[1;36m╔══════════════════════════════════════════════════════════╗\x1b[0m\r\n")
            await self.send_output("\x1b[1;36m║\x1b[0m    \x1b[1;33mFireDog Installation Wizard\x1b[0m                        \x1b[1;36m║\x1b[0m\r\n")
            await self.send_output("\x1b[1;36m╚══════════════════════════════════════════════════════════╝\x1b[0m\r\n\r\n")
            await self.send_output(f"Target: \x1b[1m{self.target.hostname or self.target.ip_address}\x1b[0m ({self.target.ip_address})\r\n")
            await self.send_output(f"User: \x1b[1m{self.target.ssh_user}\x1b[0m\r\n")

            # Mostra metodo autenticazione
            if ssh_password:
                await self.send_output(f"Auth: \x1b[1;33mPassword\x1b[0m (prima installazione)\r\n\r\n")
            else:
                await self.send_output(f"Auth: \x1b[1;32mPublic Key\x1b[0m\r\n\r\n")

            # Aggiorna status del target
            await self.update_target_status('installing', 'Starting installation...')

            # STEP 1: Connessione SSH con terminale PTY interattivo
            await self.send_output("\x1b[1;34m[1/8]\x1b[0m Connessione SSH al target...\r\n")

            from core.ssh_terminal_manager import SSHTerminalManager

            self.ssh_manager = SSHTerminalManager(
                host=self.target.ip_address,
                port=self.target.ssh_port,
                username=self.target.ssh_user,
                password=ssh_password  # Usa password se fornita, altrimenti chiave pubblica
            )

            # Tenta connessione
            try:
                connected = await sync_to_async(self.ssh_manager.connect)()
                if not connected:
                    await self.send_error("Connessione SSH fallita")
                    await self.update_target_status('error', 'Connection failed')
                    return

                await self.send_output("\x1b[32m  ✓ Connessione SSH stabilita\x1b[0m\r\n\r\n")
            except Exception as e:
                await self.send_error(f"Connessione SSH fallita: {str(e)}")
                await self.update_target_status('error', f'Connection failed: {str(e)}')
                return

            # Avvia shell interattiva PTY
            shell_started = await sync_to_async(
                self.ssh_manager.start_shell
            )(width=width, height=height)

            if not shell_started:
                await self.send_error("Avvio shell interattiva fallito")
                await sync_to_async(self.ssh_manager.disconnect)()
                await self.update_target_status('error', 'Shell start failed')
                return

            self.is_connected = True

            # Avvia task di lettura output in tempo reale
            self.read_task = asyncio.create_task(self.read_ssh_output())

            # Attendi che il prompt sia pronto
            await asyncio.sleep(1.0)

            # STEP 2: Configurazione chiave SSH (se autenticazione con password)
            if ssh_password:
                await self.send_output("\r\n\x1b[1;34m[2/8]\x1b[0m Configurazione chiave SSH pubblica...\r\n")
                await self.send_output("\x1b[33m🔑 Configurando autenticazione con chiave pubblica per futuri accessi...\x1b[0m\r\n")

                # Configura chiave SSH pubblica
                key_configured = await self.configure_ssh_key()

                if key_configured:
                    await self.send_output("\x1b[32m  ✓ Chiave SSH configurata con successo\x1b[0m\r\n")
                    await self.send_output("\x1b[32m  ✓ Prossime connessioni useranno la chiave pubblica\x1b[0m\r\n\r\n")
                else:
                    await self.send_output("\x1b[33m  ⚠ Configurazione chiave SSH fallita, continuo con password\x1b[0m\r\n\r\n")
            else:
                await self.send_output("\r\n\x1b[1;34m[2/8]\x1b[0m Chiave SSH già configurata, skip...\r\n\r\n")

            # STEP 3: Verifica prerequisiti e upload pacchetto
            await self.send_output("\x1b[1;34m[3/8]\x1b[0m Preparazione installazione...\r\n")
            await self.send_output("\x1b[33m💡 L'installazione richiederà la tua password sudo. Preparati a inserirla quando richiesto.\x1b[0m\r\n\r\n")

            # STEP 4: Upload pacchetto FireDog (usa SSHManager separato per SFTP)
            await self.send_output("\x1b[1;34m[4/8]\x1b[0m Upload pacchetto FireDog...\r\n")

            from django.conf import settings
            from core.ssh_manager import SSHManager

            package_local_path = '/opt/firedog/firedog-package'
            package_remote_path = '/tmp/firedog-package'

            # Crea connessione separata per SFTP (usa chiave se configurata, altrimenti password)
            sftp_ssh = SSHManager(
                host=self.target.ip_address,
                port=self.target.ssh_port,
                username=self.target.ssh_user,
                password=ssh_password if ssh_password else None
            )

            try:
                await sync_to_async(sftp_ssh.connect)()

                # Crea directory remota
                await sync_to_async(sftp_ssh.execute_command)(f"mkdir -p {package_remote_path}")

                # Upload package
                success, message = await sync_to_async(sftp_ssh.upload_directory)(package_local_path, package_remote_path)

                await sync_to_async(sftp_ssh.disconnect)()

                if not success:
                    await self.send_error(f"Upload fallito: {message}")
                    await self.update_target_status('error', 'Upload failed')
                    return

                await self.send_output("\x1b[32m  ✓ Pacchetto caricato con successo\x1b[0m\r\n\r\n")
            except Exception as e:
                await self.send_error(f"Errore upload: {str(e)}")
                await self.update_target_status('error', f'Upload failed: {str(e)}')
                return

            # STEP 5: Configura permessi esecuzione
            await self.send_output("\x1b[1;34m[5/8]\x1b[0m Configurazione permessi...\r\n")
            await sync_to_async(self.ssh_manager.send_data)(f"chmod +x {package_remote_path}/*.sh {package_remote_path}/bin/* 2>&1\n")
            await asyncio.sleep(0.5)
            await self.send_output("\x1b[32m  ✓ Permessi configurati\x1b[0m\r\n\r\n")

            # STEP 6: Informazioni pre-installazione
            await self.send_output("\x1b[1;34m[6/8]\x1b[0m Preparazione script di installazione...\r\n")
            await self.send_output("\x1b[33m⚠️  ATTENZIONE: Tra poco verrà richiesta la password sudo\x1b[0m\r\n")
            await self.send_output("\x1b[33m⚠️  La password NON verrà visualizzata mentre la digiti (è normale)\x1b[0m\r\n\r\n")
            await asyncio.sleep(2.0)

            # STEP 7: Esecuzione install.sh INTERATTIVO
            await self.send_output("\x1b[1;34m[7/8]\x1b[0m Esecuzione script di installazione...\x1b[0m\r\n")
            await self.send_output("\x1b[2m" + "─" * 60 + "\x1b[0m\r\n\r\n")

            # Invia comando install.sh - L'utente potrà interagire tramite il terminale
            await sync_to_async(self.ssh_manager.send_data)(
                f"cd {package_remote_path} && sudo bash install.sh\n"
            )

            # Informazione per l'utente
            await self.send_output("\r\n\x1b[1;33m>>> Script di installazione avviato <<<\x1b[0m\r\n")
            await self.send_output("\x1b[33m>>> Se richiesto, inserisci la password sudo e premi INVIO <<<\x1b[0m\r\n\r\n")

            # Da questo punto in poi, l'utente può interagire liberamente con il terminale
            # Il task read_ssh_output() continuerà a streamare l'output
            # L'utente può digitare la password quando richiesta tramite handle_input()

            logger.info(f"Installation script started for target {target_id} - waiting for user interaction")

        except asyncio.CancelledError:
            logger.info(f"Installation cancelled for target {target_id}")
            await self.update_target_status('error', 'Installation cancelled')
            raise

        except Exception as e:
            logger.exception(f"Errore durante installazione target {target_id}: {e}")
            await self.send_error(f"Errore: {str(e)}")
            await self.update_target_status('error', str(e))

    async def send_output(self, data: str):
        """Invia output al terminale frontend"""
        await self.send(text_data=json.dumps({
            'type': 'output',
            'data': data
        }))

    @database_sync_to_async
    def update_target_status(self, status: str, installation_status: str = None, version: str = None):
        """Aggiorna status del target nel database"""
        if self.target:
            self.target.status = status
            if installation_status:
                self.target.installation_status = installation_status
            if version:
                self.target.firedog_version = version
            if status == 'online':
                from django.utils.timezone import now
                self.target.last_seen = now()
            self.target.save()

    async def verify_installation_result(self):
        """Verifica se l'installazione di FireDog è andata a buon fine"""
        try:
            from core.ssh_manager import SSHManager

            logger.info(f"Verifying installation result for target {self.target.id}")

            # Crea nuova connessione SSH per verifica
            ssh = SSHManager(
                host=self.target.ip_address,
                port=self.target.ssh_port,
                username=self.target.ssh_user
            )

            await sync_to_async(ssh.connect)()

            # Verifica se firewall-manager è installato
            exit_code, stdout, stderr = await sync_to_async(ssh.execute_command)(
                "/usr/local/bin/firewall-manager --version 2>&1 || echo 'NOT_INSTALLED'"
            )

            await sync_to_async(ssh.disconnect)()

            if exit_code == 0 and 'NOT_INSTALLED' not in stdout:
                # Installazione completata con successo
                version = stdout.strip() or '1.0.0'
                await self.update_target_status('online', 'Installation completed', version)
                logger.info(f"Installation verified successfully for target {self.target.id}: v{version}")
            else:
                # Installazione non completata o fallita
                await self.update_target_status('error', 'Installation incomplete or failed')
                logger.warning(f"Installation verification failed for target {self.target.id}")

        except Exception as e:
            logger.exception(f"Error verifying installation for target {self.target.id}: {e}")
            await self.update_target_status('error', f'Verification failed: {str(e)}')

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
    
    async def configure_ssh_key(self) -> bool:
        """
        Configura chiave SSH pubblica sul target per autenticazione passwordless

        Returns:
            bool: True se configurazione riuscita
        """
        try:
            from django.conf import settings
            from pathlib import Path

            # Path chiave pubblica
            pub_key_path = f"{settings.FIREDOG_SSH_KEY_PATH}.pub"

            if not Path(pub_key_path).exists():
                logger.error(f"Chiave pubblica non trovata: {pub_key_path}")
                return False

            # Leggi chiave pubblica
            with open(pub_key_path, 'r') as f:
                pub_key = f.read().strip()

            # Crea directory .ssh e authorized_keys tramite terminale interattivo
            # STEP 1: Crea directory .ssh
            await sync_to_async(self.ssh_manager.send_data)("mkdir -p ~/.ssh && chmod 700 ~/.ssh\n")
            await asyncio.sleep(0.5)

            # STEP 2: Aggiungi chiave a authorized_keys (se non già presente)
            # Usa grep per verificare se chiave è già presente
            cmd = f"grep -q '{pub_key[:50]}' ~/.ssh/authorized_keys 2>/dev/null || echo '{pub_key}' >> ~/.ssh/authorized_keys\n"
            await sync_to_async(self.ssh_manager.send_data)(cmd)
            await asyncio.sleep(0.5)

            # STEP 3: Imposta permessi corretti
            await sync_to_async(self.ssh_manager.send_data)("chmod 600 ~/.ssh/authorized_keys\n")
            await asyncio.sleep(0.5)

            logger.info(f"Chiave SSH configurata su {self.target.ip_address}")
            return True

        except Exception as e:
            logger.exception(f"Errore configurazione chiave SSH: {e}")
            return False

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

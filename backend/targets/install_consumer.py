"""
WebSocket Consumer per Installazione Interattiva FireDog
Gestisce installazione sui target con supporto per input password e streaming output
"""
import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.conf import settings

logger = logging.getLogger('firedog.install_consumer')


class InstallConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket per installazione interattiva FireDog

    Messaggi ricevuti dal client (frontend):
    - {"type": "start_install", "target_id": 1, "use_password": false}
    - {"type": "start_group_install", "group_id": 1}
    - {"type": "password_input", "password": "secret"}
    - {"type": "cancel"}

    Messaggi inviati al client:
    - {"type": "status", "message": "Connecting to target..."}
    - {"type": "output", "data": "command output"}
    - {"type": "password_required"}
    - {"type": "error", "message": "Error description"}
    - {"type": "success", "message": "Installation completed"}
    - {"type": "progress", "step": 1, "total": 7, "description": "Installing dependencies..."}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target = None
        self.targets = []  # For group installation
        self.ssh_manager = None
        self.installation_task = None
        self.use_password = False
        self.password = None
        self.is_group = False

    async def connect(self):
        """Gestisce connessione WebSocket dal client"""
        await self.accept()
        logger.info(f"WebSocket connesso per installazione: {self.channel_name}")

    async def disconnect(self, close_code):
        """Gestisce disconnessione WebSocket"""
        logger.info(f"WebSocket disconnesso: {self.channel_name}, code: {close_code}")

        # Cancella task in corso
        if self.installation_task:
            self.installation_task.cancel()
            try:
                await self.installation_task
            except asyncio.CancelledError:
                pass

        # Chiudi connessione SSH se aperta
        if self.ssh_manager:
            await sync_to_async(self.ssh_manager.disconnect)()

    async def receive(self, text_data):
        """Riceve messaggi dal client WebSocket"""
        try:
            message = json.loads(text_data)
            msg_type = message.get('type')

            if msg_type == 'start_install':
                await self.handle_start_install(message)

            elif msg_type == 'start_group_install':
                await self.handle_start_group_install(message)

            elif msg_type == 'password_input':
                await self.handle_password_input(message)

            elif msg_type == 'cancel':
                await self.handle_cancel()

            else:
                logger.warning(f"Tipo messaggio sconosciuto: {msg_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Errore parsing JSON: {e}")
            await self.send_error("Invalid JSON format")

        except Exception as e:
            logger.exception(f"Errore gestione messaggio: {e}")
            await self.send_error(str(e))

    async def handle_start_install(self, message):
        """
        Gestisce richiesta di installazione singolo target

        Args:
            message: Dict con target_id e use_password
        """
        target_id = message.get('target_id')
        self.use_password = message.get('use_password', False)

        if not target_id:
            await self.send_error("Target ID mancante")
            return

        try:
            # Carica target dal database
            self.target = await self.get_target(target_id)

            if not self.target:
                await self.send_error(f"Target {target_id} non trovato")
                return

            # Avvia task di installazione
            await self.send_status(f"Avvio installazione su {self.target.hostname or self.target.ip_address}...")
            self.installation_task = asyncio.create_task(self.run_installation())

        except Exception as e:
            logger.exception(f"Errore avvio installazione: {e}")
            await self.send_error(str(e))

    async def handle_start_group_install(self, message):
        """
        Gestisce richiesta di installazione gruppo di target

        Args:
            message: Dict con group_id
        """
        group_id = message.get('group_id')
        self.use_password = message.get('use_password', False)

        if not group_id:
            await self.send_error("Group ID mancante")
            return

        try:
            # Carica targets del gruppo
            self.targets = await self.get_group_targets(group_id)

            if not self.targets:
                await self.send_error(f"Nessun target trovato nel gruppo {group_id}")
                return

            self.is_group = True

            # Avvia task di installazione gruppo
            await self.send_status(f"Avvio installazione su {len(self.targets)} target...")
            self.installation_task = asyncio.create_task(self.run_group_installation())

        except Exception as e:
            logger.exception(f"Errore avvio installazione gruppo: {e}")
            await self.send_error(str(e))

    async def handle_password_input(self, message):
        """
        Gestisce input password dall'utente

        Args:
            message: Dict con password
        """
        self.password = message.get('password', '')
        logger.info("Password ricevuta dall'utente")

        # Se c'è un task in attesa, lo notifica
        # (implementazione dipende da come gestiamo l'attesa password)

    async def handle_cancel(self):
        """Gestisce cancellazione installazione"""
        if self.installation_task:
            self.installation_task.cancel()

        await self.send_status("Installazione annullata")
        await self.close()

    async def run_installation(self):
        """
        Esegue installazione su singolo target
        Gestisce i 7 step dell'installazione con streaming output
        """
        try:
            from core.ssh_terminal_manager import SSHTerminalManager

            # STEP 1: Connessione SSH
            await self.send_progress(1, 7, f"Connessione a {self.target.ip_address}...")

            self.ssh_manager = SSHTerminalManager(
                host=self.target.ip_address,
                port=self.target.ssh_port,
                username=self.target.ssh_user
            )

            connected = await sync_to_async(self.ssh_manager.connect)()

            if not connected:
                # Se fallisce con chiave, potrebbe richiedere password
                if self.use_password:
                    await self.send_message('password_required', {})
                    # Attendere password (implementazione da completare)
                    # Per ora fallisce
                    await self.send_error("Connessione SSH fallita")
                    return
                else:
                    await self.send_error("Connessione SSH fallita")
                    return

            await self.send_status("✓ Connessione stabilita")

            # STEP 2: Upload firedog-package
            await self.send_progress(2, 7, "Caricamento pacchetto FireDog...")

            package_local = settings.FIREDOG_PACKAGE_PATH
            package_remote = '/tmp/firedog-package'

            # Crea directory remota
            await self.execute_command(f"mkdir -p {package_remote}")

            # Upload file tramite SFTP
            upload_success = await self.upload_package(package_local, package_remote)

            if not upload_success:
                await self.send_error("Caricamento pacchetto fallito")
                return

            await self.send_status("✓ Pacchetto caricato")

            # STEP 3: Configurazione SSH (se richiesto)
            if self.use_password:
                await self.send_progress(3, 7, "Configurazione chiave SSH...")
                await self.configure_ssh_key()
                await self.send_status("✓ Chiave SSH configurata")
            else:
                await self.send_progress(3, 7, "Chiave SSH già configurata")

            # STEP 4: Configurazione sudoers (se richiesto)
            if self.use_password:
                await self.send_progress(4, 7, "Configurazione sudoers...")
                await self.configure_sudoers()
                await self.send_status("✓ Sudoers configurato")
            else:
                await self.send_progress(4, 7, "Sudoers già configurato")

            # STEP 5: Hardening SSH (se richiesto)
            if self.use_password:
                await self.send_progress(5, 7, "Hardening configurazione SSH...")
                await self.harden_ssh()
                await self.send_status("✓ SSH hardening completato")
            else:
                await self.send_progress(5, 7, "SSH già hardened")

            # STEP 6: Esecuzione install.sh
            await self.send_progress(6, 7, "Esecuzione script di installazione...")

            install_success = await self.run_install_script(package_remote)

            if not install_success:
                await self.send_error("Installazione fallita")
                return

            await self.send_status("✓ Installazione completata")

            # STEP 7: Verifica installazione
            await self.send_progress(7, 7, "Verifica installazione...")

            version = await self.verify_installation()

            if not version:
                await self.send_error("Verifica installazione fallita")
                return

            await self.send_status(f"✓ FireDog {version} installato correttamente")

            # Aggiorna target nel database
            await self.update_target_status('online', version)

            # Invia messaggio di successo
            await self.send_success(f"Installazione completata su {self.target.hostname or self.target.ip_address}")

        except asyncio.CancelledError:
            logger.info("Installazione cancellata")
            await self.send_status("Installazione cancellata")

        except Exception as e:
            logger.exception(f"Errore durante installazione: {e}")
            await self.send_error(f"Errore: {str(e)}")
            await self.update_target_status('error', None, str(e))

    async def run_group_installation(self):
        """Esegue installazione su gruppo di target (sequenziale)"""
        total = len(self.targets)

        for idx, target in enumerate(self.targets, 1):
            self.target = target

            await self.send_status(f"\n{'='*60}\nTarget {idx}/{total}: {target.hostname or target.ip_address}\n{'='*60}")

            # Esegui installazione singola
            await self.run_installation()

            # Piccola pausa tra un target e l'altro
            await asyncio.sleep(1)

        await self.send_success(f"Installazione gruppo completata: {total} target")

    async def execute_command(self, command, stream_output=True):
        """
        Esegue comando SSH e stream output

        Args:
            command: Comando da eseguire
            stream_output: Se True, stream output in tempo reale

        Returns:
            Tuple (exit_code, stdout, stderr)
        """
        # Implementazione semplificata - usa SSHTerminalManager
        # Per comando non interattivo
        from core.ssh_manager import SSHManager

        ssh = SSHManager(
            host=self.target.ip_address,
            port=self.target.ssh_port,
            username=self.target.ssh_user
        )

        await sync_to_async(ssh.connect)()
        exit_code, stdout, stderr = await sync_to_async(ssh.execute_command)(command)
        await sync_to_async(ssh.disconnect)()

        if stream_output and stdout:
            await self.send_output(stdout)

        if stderr:
            await self.send_output(f"[STDERR] {stderr}")

        return exit_code, stdout, stderr

    async def upload_package(self, local_path, remote_path):
        """Upload firedog-package via SFTP"""
        try:
            from core.ssh_manager import SSHManager

            ssh = SSHManager(
                host=self.target.ip_address,
                port=self.target.ssh_port,
                username=self.target.ssh_user
            )

            await sync_to_async(ssh.connect)()
            success, message = await sync_to_async(ssh.upload_directory)(local_path, remote_path)
            await sync_to_async(ssh.disconnect)()

            if not success:
                await self.send_error(f"Upload failed: {message}")

            return success

        except Exception as e:
            logger.exception(f"Errore upload package: {e}")
            return False

    async def run_install_script(self, package_remote):
        """Esegue lo script install.sh"""
        try:
            # Rendi eseguibili gli script
            await self.execute_command(f"chmod +x {package_remote}/*.sh {package_remote}/bin/*", stream_output=False)

            # Esegui install.sh
            await self.send_output("\n--- Esecuzione install.sh ---\n")
            exit_code, stdout, stderr = await self.execute_command(
                f"cd {package_remote} && sudo bash install.sh",
                stream_output=True
            )

            return exit_code == 0

        except Exception as e:
            logger.exception(f"Errore esecuzione install.sh: {e}")
            return False

    async def verify_installation(self):
        """Verifica che firedog sia installato correttamente"""
        try:
            exit_code, stdout, stderr = await self.execute_command(
                "/usr/local/bin/firewall-manager --version",
                stream_output=False
            )

            if exit_code == 0 and stdout:
                # Estrai versione dall'output
                version = stdout.strip().split()[-1] if stdout else "1.0.0"
                return version

            return None

        except Exception as e:
            logger.exception(f"Errore verifica installazione: {e}")
            return None

    async def configure_ssh_key(self):
        """
        Configura chiave SSH pubblica sul target
        Copia la chiave pubblica in ~/.ssh/authorized_keys
        """
        try:
            from pathlib import Path

            # Path chiave pubblica
            pub_key_path = f"{settings.FIREDOG_SSH_KEY_PATH}.pub"

            if not Path(pub_key_path).exists():
                await self.send_error(f"Public key not found: {pub_key_path}")
                return False

            # Leggi chiave pubblica
            with open(pub_key_path, 'r') as f:
                pub_key = f.read().strip()

            await self.send_output("Configuring SSH key authentication...")

            # Crea directory .ssh
            await self.execute_command("mkdir -p ~/.ssh && chmod 700 ~/.ssh", stream_output=False)

            # Aggiungi chiave a authorized_keys
            cmd = f'echo "{pub_key}" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
            exit_code, stdout, stderr = await self.execute_command(cmd, stream_output=False)

            if exit_code != 0:
                await self.send_error(f"Failed to configure SSH key: {stderr}")
                return False

            await self.send_output("✓ SSH key configured")
            return True

        except Exception as e:
            logger.exception(f"Error configuring SSH key: {e}")
            await self.send_error(f"SSH key configuration failed: {str(e)}")
            return False

    async def configure_sudoers(self):
        """
        Configura sudoers per NOPASSWD usando template
        Copia file da /opt/firedog/file_config/sudoers-microcyber
        """
        try:
            from pathlib import Path

            # Path file template sudoers
            sudoers_template = Path(settings.FIREDOG_FILE_CONFIG_PATH) / "sudoers-microcyber"

            if not sudoers_template.exists():
                await self.send_error(f"Sudoers template not found: {sudoers_template}")
                return False

            await self.send_output("Configuring sudoers for NOPASSWD...")

            # Upload file sudoers temporaneo
            from core.ssh_manager import SSHManager

            ssh = SSHManager(
                host=self.target.ip_address,
                port=self.target.ssh_port,
                username=self.target.ssh_user
            )

            await sync_to_async(ssh.connect)()

            # Upload file
            success, message = await sync_to_async(ssh.upload_file)(
                str(sudoers_template),
                f"/tmp/sudoers-{self.target.ssh_user}"
            )

            if not success:
                await self.send_error(f"Failed to upload sudoers: {message}")
                await sync_to_async(ssh.disconnect)()
                return False

            # Installa file sudoers (richiede password sudo)
            if self.password:
                # Usa password per sudo
                cmd = f'echo "{self.password}" | sudo -S mv /tmp/sudoers-{self.target.ssh_user} /etc/sudoers.d/{self.target.ssh_user}'
            else:
                # Prova senza password (se già configurato)
                cmd = f'sudo mv /tmp/sudoers-{self.target.ssh_user} /etc/sudoers.d/{self.target.ssh_user}'

            exit_code, stdout, stderr = await sync_to_async(ssh.execute_command)(cmd)

            if exit_code != 0:
                await self.send_error(f"Failed to install sudoers: {stderr}")
                await sync_to_async(ssh.disconnect)()
                return False

            # Imposta permessi
            cmd = f'sudo chmod 440 /etc/sudoers.d/{self.target.ssh_user}'
            exit_code, stdout, stderr = await sync_to_async(ssh.execute_command)(cmd)

            await sync_to_async(ssh.disconnect)()

            if exit_code != 0:
                await self.send_error(f"Failed to set sudoers permissions: {stderr}")
                return False

            await self.send_output("✓ Sudoers configured")
            return True

        except Exception as e:
            logger.exception(f"Error configuring sudoers: {e}")
            await self.send_error(f"Sudoers configuration failed: {str(e)}")
            return False

    async def harden_ssh(self):
        """
        Applica hardening SSH usando template
        Copia file da /opt/firedog/file_config/sshd_config.hardened
        """
        try:
            from pathlib import Path

            # Path file template sshd_config
            sshd_template = Path(settings.FIREDOG_FILE_CONFIG_PATH) / "sshd_config.hardened"

            if not sshd_template.exists():
                await self.send_error(f"SSHD template not found: {sshd_template}")
                return False

            await self.send_output("Applying SSH hardening configuration...")

            # Upload file sshd_config
            from core.ssh_manager import SSHManager

            ssh = SSHManager(
                host=self.target.ip_address,
                port=self.target.ssh_port,
                username=self.target.ssh_user
            )

            await sync_to_async(ssh.connect)()

            # Backup sshd_config originale
            backup_cmd = 'sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup.$(date +%Y%m%d_%H%M%S)'
            await sync_to_async(ssh.execute_command)(backup_cmd)

            # Upload nuovo config
            success, message = await sync_to_async(ssh.upload_file)(
                str(sshd_template),
                "/tmp/sshd_config.hardened"
            )

            if not success:
                await self.send_error(f"Failed to upload sshd_config: {message}")
                await sync_to_async(ssh.disconnect)()
                return False

            # Test configurazione
            test_cmd = 'sudo sshd -t -f /tmp/sshd_config.hardened'
            exit_code, stdout, stderr = await sync_to_async(ssh.execute_command)(test_cmd)

            if exit_code != 0:
                await self.send_error(f"SSHD config validation failed: {stderr}")
                await sync_to_async(ssh.disconnect)()
                return False

            # Applica configurazione
            apply_cmd = 'sudo mv /tmp/sshd_config.hardened /etc/ssh/sshd_config'
            exit_code, stdout, stderr = await sync_to_async(ssh.execute_command)(apply_cmd)

            if exit_code != 0:
                await self.send_error(f"Failed to apply sshd_config: {stderr}")
                await sync_to_async(ssh.disconnect)()
                return False

            # Riavvia SSH daemon
            restart_cmd = 'sudo systemctl restart sshd || sudo service ssh restart'
            await sync_to_async(ssh.execute_command)(restart_cmd)

            await sync_to_async(ssh.disconnect)()

            await self.send_output("✓ SSH hardening applied")
            await self.send_output("⚠ Password authentication is now DISABLED")

            return True

        except Exception as e:
            logger.exception(f"Error hardening SSH: {e}")
            await self.send_error(f"SSH hardening failed: {str(e)}")
            return False

    # Helper methods per inviare messaggi al client

    async def send_status(self, message):
        """Invia messaggio di status"""
        await self.send(text_data=json.dumps({
            'type': 'status',
            'message': message
        }))

    async def send_output(self, data):
        """Invia output comando"""
        await self.send(text_data=json.dumps({
            'type': 'output',
            'data': data
        }))

    async def send_error(self, message):
        """Invia messaggio di errore"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))

    async def send_success(self, message):
        """Invia messaggio di successo"""
        await self.send(text_data=json.dumps({
            'type': 'success',
            'message': message
        }))

    async def send_progress(self, step, total, description):
        """Invia aggiornamento progresso"""
        await self.send(text_data=json.dumps({
            'type': 'progress',
            'step': step,
            'total': total,
            'description': description,
            'percentage': int((step / total) * 100)
        }))

    async def send_message(self, msg_type, data):
        """Invia messaggio generico"""
        await self.send(text_data=json.dumps({
            'type': msg_type,
            **data
        }))

    # Database operations

    @database_sync_to_async
    def get_target(self, target_id):
        """Carica target dal database"""
        from targets.models import Target

        try:
            return Target.objects.get(id=target_id)
        except Target.DoesNotExist:
            return None

    @database_sync_to_async
    def get_group_targets(self, group_id):
        """Carica tutti i target di un gruppo"""
        from targets.models import TargetGroup

        try:
            group = TargetGroup.objects.get(id=group_id)
            return list(group.targets.all())
        except TargetGroup.DoesNotExist:
            return []

    @database_sync_to_async
    def update_target_status(self, status, version=None, error=None):
        """Aggiorna status target nel database"""
        if self.target:
            self.target.status = status
            if version:
                self.target.firedog_version = version
            if error:
                self.target.error_message = error
            self.target.save()

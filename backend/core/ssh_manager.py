"""
SSH Manager per FireDog
Gestione connessioni SSH e trasferimento file via SCP
Conforme a OWASP/NIST security standards
"""
import paramiko
import socket
import logging
import os
from pathlib import Path
from typing import Optional, Tuple, List
from django.conf import settings
from contextlib import contextmanager

logger = logging.getLogger('firedog.ssh')


class SSHConnectionError(Exception):
    """Errore di connessione SSH"""
    pass


class SSHCommandError(Exception):
    """Errore durante esecuzione comando SSH"""
    pass


class SSHManager:
    """
    Gestore connessioni SSH con supporto SCP
    Utilizza chiavi Ed25519 per autenticazione sicura
    """
    
    def __init__(self, host: str, port: int = 22, username: str = 'microcyber',
                 key_path: Optional[str] = None, timeout: int = 30):
        """
        Inizializza SSHManager
        
        Args:
            host: Hostname o IP del target
            port: Porta SSH (default 22)
            username: Username SSH (default 'microcyber')
            key_path: Path alla chiave privata SSH (default da settings)
            timeout: Timeout connessione in secondi
        """
        self.host = host
        self.port = port
        self.username = username
        self.timeout = timeout
        self.key_path = key_path or settings.FIREDOG_SSH_KEY_PATH
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
        
        # Validazione parametri
        if not self.host:
            raise ValueError("Host non può essere vuoto")
        
        if not os.path.exists(self.key_path):
            raise FileNotFoundError(f"Chiave SSH non trovata: {self.key_path}")
    
    def connect(self) -> bool:
        """
        Stabilisce connessione SSH
        
        Returns:
            bool: True se connessione riuscita
            
        Raises:
            SSHConnectionError: Se connessione fallisce
        """
        try:
            # Crea client SSH
            self.client = paramiko.SSHClient()
            
            # Carica chiavi host conosciute (se esistono)
            known_hosts_path = os.path.expanduser('~/.ssh/known_hosts')
            if os.path.exists(known_hosts_path):
                self.client.load_host_keys(known_hosts_path)
            
            # Policy per chiavi host sconosciute
            # In produzione: usare RejectPolicy e gestire known_hosts
            # Per sviluppo: AutoAddPolicy
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Carica chiave privata
            try:
                private_key = paramiko.Ed25519Key.from_private_key_file(self.key_path)
            except Exception as e:
                logger.error(f"Errore caricamento chiave SSH: {e}")
                raise SSHConnectionError(f"Impossibile caricare chiave SSH: {e}")
            
            # Connessione
            logger.info(f"Connessione a {self.username}@{self.host}:{self.port}")
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                pkey=private_key,
                timeout=self.timeout,
                allow_agent=False,  # Sicurezza: non usare SSH agent
                look_for_keys=False,  # Sicurezza: usa solo la chiave specificata
                compress=True
            )
            
            logger.info(f"Connessione stabilita con {self.host}")
            return True
            
        except paramiko.AuthenticationException as e:
            logger.error(f"Autenticazione fallita per {self.host}: {e}")
            raise SSHConnectionError(f"Autenticazione fallita: {e}")
        except socket.timeout:
            logger.error(f"Timeout connessione a {self.host}")
            raise SSHConnectionError(f"Timeout connessione a {self.host}")
        except socket.error as e:
            logger.error(f"Errore rete connettendo a {self.host}: {e}")
            raise SSHConnectionError(f"Errore rete: {e}")
        except Exception as e:
            logger.error(f"Errore imprevisto connettendo a {self.host}: {e}")
            raise SSHConnectionError(f"Errore connessione: {e}")
    
    def disconnect(self):
        """Chiude connessione SSH e SFTP"""
        if self.sftp:
            try:
                self.sftp.close()
            except:
                pass
            self.sftp = None
        
        if self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None
        
        logger.info(f"Disconnesso da {self.host}")
    
    def execute_command(self, command: str, sudo: bool = False) -> Tuple[int, str, str]:
        """
        Esegue comando sul target
        
        Args:
            command: Comando da eseguire
            sudo: Esegui con sudo (default False)
            
        Returns:
            Tuple[int, str, str]: (exit_code, stdout, stderr)
            
        Raises:
            SSHCommandError: Se comando fallisce
        """
        if not self.client:
            raise SSHConnectionError("Non connesso. Chiamare connect() prima.")
        
        try:
            # Aggiungi sudo se richiesto
            if sudo:
                command = f"sudo {command}"
            
            logger.debug(f"Eseguo comando: {command}")
            
            # Esegui comando
            stdin, stdout, stderr = self.client.exec_command(
                command,
                timeout=self.timeout
            )
            
            # Leggi output
            exit_code = stdout.channel.recv_exit_status()
            stdout_data = stdout.read().decode('utf-8', errors='replace')
            stderr_data = stderr.read().decode('utf-8', errors='replace')
            
            if exit_code != 0:
                logger.warning(f"Comando fallito (exit {exit_code}): {stderr_data}")
            else:
                logger.debug(f"Comando completato con successo")
            
            return exit_code, stdout_data, stderr_data
            
        except socket.timeout:
            raise SSHCommandError(f"Timeout esecuzione comando: {command}")
        except Exception as e:
            raise SSHCommandError(f"Errore esecuzione comando: {e}")
    
    def _get_sftp(self) -> paramiko.SFTPClient:
        """Ottiene client SFTP (lazy initialization)"""
        if not self.client:
            raise SSHConnectionError("Non connesso. Chiamare connect() prima.")
        
        if not self.sftp:
            self.sftp = self.client.open_sftp()
        
        return self.sftp
    
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """
        Carica file sul target via SCP
        
        Args:
            local_path: Path del file locale
            remote_path: Path di destinazione sul target
            
        Returns:
            bool: True se upload riuscito
        """
        try:
            sftp = self._get_sftp()
            
            logger.info(f"Upload {local_path} -> {self.host}:{remote_path}")
            sftp.put(local_path, remote_path)
            logger.info(f"Upload completato")
            
            return True
            
        except FileNotFoundError as e:
            logger.error(f"File non trovato: {e}")
            raise
        except Exception as e:
            logger.error(f"Errore upload file: {e}")
            raise SSHCommandError(f"Errore upload: {e}")
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """
        Scarica file dal target via SCP
        
        Args:
            remote_path: Path del file sul target
            local_path: Path di destinazione locale
            
        Returns:
            bool: True se download riuscito
        """
        try:
            sftp = self._get_sftp()
            
            logger.info(f"Download {self.host}:{remote_path} -> {local_path}")
            sftp.get(remote_path, local_path)
            logger.info(f"Download completato")
            
            return True
            
        except FileNotFoundError as e:
            logger.error(f"File remoto non trovato: {e}")
            raise
        except Exception as e:
            logger.error(f"Errore download file: {e}")
            raise SSHCommandError(f"Errore download: {e}")
    
    def upload_directory(self, local_dir: str, remote_dir: str) -> bool:
        """
        Carica directory ricorsivamente sul target
        
        Args:
            local_dir: Path directory locale
            remote_dir: Path directory remota
            
        Returns:
            bool: True se upload riuscito
        """
        try:
            sftp = self._get_sftp()
            local_path = Path(local_dir)
            
            if not local_path.exists():
                raise FileNotFoundError(f"Directory locale non trovata: {local_dir}")
            
            logger.info(f"Upload directory {local_dir} -> {self.host}:{remote_dir}")
            
            # Crea directory remota se non esiste
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                sftp.mkdir(remote_dir)
            
            # Upload ricorsivo
            for item in local_path.rglob('*'):
                if item.is_file():
                    # Calcola path relativo
                    rel_path = item.relative_to(local_path)
                    remote_file_path = os.path.join(remote_dir, str(rel_path)).replace('\\', '/')
                    
                    # Crea directory intermedie
                    remote_file_dir = os.path.dirname(remote_file_path)
                    self._ensure_remote_dir(sftp, remote_file_dir)
                    
                    # Upload file
                    logger.debug(f"Upload {item} -> {remote_file_path}")
                    sftp.put(str(item), remote_file_path)
            
            logger.info(f"Upload directory completato")
            return True
            
        except Exception as e:
            logger.error(f"Errore upload directory: {e}")
            raise SSHCommandError(f"Errore upload directory: {e}")
    
    def _ensure_remote_dir(self, sftp: paramiko.SFTPClient, remote_dir: str):
        """Crea directory remota ricorsivamente se non esiste"""
        dirs = []
        dir_path = remote_dir
        
        # Trova directory da creare
        while dir_path and dir_path != '/':
            try:
                sftp.stat(dir_path)
                break
            except FileNotFoundError:
                dirs.append(dir_path)
                dir_path = os.path.dirname(dir_path)
        
        # Crea directory in ordine
        for dir_to_create in reversed(dirs):
            try:
                sftp.mkdir(dir_to_create)
            except:
                pass
    
    def file_exists(self, remote_path: str) -> bool:
        """Verifica se file esiste sul target"""
        try:
            sftp = self._get_sftp()
            sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Errore verifica esistenza file: {e}")
            return False
    
    def check_user_exists(self, username: str) -> bool:
        """
        Verifica se utente esiste sul target
        
        Args:
            username: Nome utente da verificare
            
        Returns:
            bool: True se utente esiste
        """
        try:
            exit_code, stdout, stderr = self.execute_command(f"id {username}")
            return exit_code == 0
        except:
            return False
    
    def __enter__(self):
        """Context manager: connessione automatica"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: disconnessione automatica"""
        self.disconnect()
        return False


@contextmanager
def ssh_connection(host: str, port: int = 22, username: str = 'microcyber',
                   key_path: Optional[str] = None, timeout: int = 30):
    """
    Context manager per connessioni SSH
    
    Usage:
        with ssh_connection('192.168.1.100') as ssh:
            ssh.execute_command('ls -la')
    """
    manager = SSHManager(host, port, username, key_path, timeout)
    try:
        manager.connect()
        yield manager
    finally:
        manager.disconnect()

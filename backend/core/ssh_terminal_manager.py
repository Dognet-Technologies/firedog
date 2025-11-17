"""
SSH Terminal Manager - Gestione terminale interattivo PTY
Utilizzato per installazioni che richiedono input utente (password sudo, conferme)
"""
import paramiko
import socket
import select
import logging
from typing import Callable, Optional
from django.conf import settings

logger = logging.getLogger('firedog.ssh_terminal')


class SSHTerminalManager:
    """
    Gestore terminale SSH interattivo con supporto PTY
    Permette input/output bidirezionale per sessioni interattive
    """
    
    def __init__(self, host: str, port: int = 22, username: str = 'microcyber',
                 key_path: Optional[str] = None, password: Optional[str] = None,
                 timeout: int = 30):
        """
        Inizializza SSH Terminal Manager

        Args:
            host: IP o hostname del target
            port: Porta SSH (default 22)
            username: Username SSH (default 'microcyber')
            key_path: Path chiave privata (default da settings)
            password: Password SSH per prima installazione (optional)
            timeout: Timeout connessione
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.key_path = key_path or settings.FIREDOG_SSH_KEY_PATH
        self.client: Optional[paramiko.SSHClient] = None
        self.channel: Optional[paramiko.Channel] = None
        
    def connect(self) -> bool:
        """
        Stabilisce connessione SSH
        Supporta autenticazione con password (per prima installazione) o chiave pubblica

        Returns:
            bool: True se connessione riuscita
        """
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Determina metodo autenticazione
            if self.password:
                # Autenticazione con password (prima installazione)
                logger.info(f"Connessione terminale SSH a {self.username}@{self.host}:{self.port} (password auth)")
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=self.timeout,
                    allow_agent=False,
                    look_for_keys=False,
                    compress=True
                )
            else:
                # Autenticazione con chiave pubblica (normale)
                try:
                    private_key = paramiko.Ed25519Key.from_private_key_file(self.key_path)
                except Exception as e:
                    logger.error(f"Errore caricamento chiave: {e}")
                    return False

                logger.info(f"Connessione terminale SSH a {self.username}@{self.host}:{self.port} (key auth)")
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    pkey=private_key,
                    timeout=self.timeout,
                    allow_agent=False,
                    look_for_keys=False,
                    compress=True
                )

            logger.info(f"Connessione terminale stabilita con {self.host}")
            return True

        except Exception as e:
            logger.error(f"Errore connessione terminale: {e}")
            return False
    
    def start_shell(self, term_type: str = 'xterm-256color', 
                   width: int = 80, height: int = 24) -> bool:
        """
        Avvia shell interattiva con PTY
        
        Args:
            term_type: Tipo terminale (default xterm-256color)
            width: Larghezza terminale in caratteri
            height: Altezza terminale in righe
            
        Returns:
            bool: True se shell avviata con successo
        """
        if not self.client:
            logger.error("Client SSH non connesso")
            return False
        
        try:
            # Ottieni canale per shell interattiva
            transport = self.client.get_transport()
            self.channel = transport.open_session()
            
            # Richiedi PTY (pseudo-terminal)
            self.channel.get_pty(term=term_type, width=width, height=height)
            
            # Avvia shell
            self.channel.invoke_shell()
            
            # Imposta modalità non-blocking per select()
            self.channel.setblocking(0)
            
            logger.info("Shell interattiva avviata")
            return True
            
        except Exception as e:
            logger.error(f"Errore avvio shell: {e}")
            return False
    
    def send_data(self, data: str):
        """
        Invia dati al terminale remoto
        
        Args:
            data: Stringa da inviare (input utente, comandi)
        """
        if not self.channel:
            logger.error("Canale non disponibile")
            return
        
        try:
            self.channel.send(data)
            logger.debug(f"Inviati {len(data)} bytes al terminale")
        except Exception as e:
            logger.error(f"Errore invio dati: {e}")
    
    def receive_data(self, timeout: float = 0.5) -> Optional[str]:
        """
        Riceve dati dal terminale remoto (non-blocking)
        
        Args:
            timeout: Timeout in secondi per select() (default 0.5s)
            
        Returns:
            str: Dati ricevuti o None se nessun dato disponibile
        """
        if not self.channel:
            return None
        
        try:
            # Usa select per check non-blocking
            readable, _, _ = select.select([self.channel], [], [], timeout)
            
            if readable:
                # Dati disponibili
                if self.channel.recv_ready():
                    data = self.channel.recv(4096).decode('utf-8', errors='replace')
                    return data
                
                # Check stderr
                if self.channel.recv_stderr_ready():
                    data = self.channel.recv_stderr(4096).decode('utf-8', errors='replace')
                    return data
            
            return None
            
        except Exception as e:
            logger.error(f"Errore ricezione dati: {e}")
            return None
    
    def resize_terminal(self, width: int, height: int):
        """
        Ridimensiona terminale remoto
        
        Args:
            width: Nuova larghezza in caratteri
            height: Nuova altezza in righe
        """
        if self.channel:
            try:
                self.channel.resize_pty(width=width, height=height)
                logger.debug(f"Terminale ridimensionato: {width}x{height}")
            except Exception as e:
                logger.error(f"Errore ridimensionamento: {e}")
    
    def is_active(self) -> bool:
        """
        Verifica se il canale è ancora attivo
        
        Returns:
            bool: True se canale attivo
        """
        if not self.channel:
            return False
        
        return not self.channel.closed and self.channel.active
    
    def disconnect(self):
        """Chiude connessione e canale"""
        if self.channel:
            try:
                self.channel.close()
            except:
                pass
            self.channel = None
        
        if self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None
        
        logger.info(f"Terminale disconnesso da {self.host}")
    
    def __enter__(self):
        """Context manager support"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.disconnect()

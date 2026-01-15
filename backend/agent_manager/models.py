"""
Models per l'app Agent Manager
Gestione dell'agent Dog Agent per comunicazione con i target
"""
import hashlib
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from targets.models import Target
from cryptography.fernet import Fernet
import uuid
import base64


def get_encryption_key():
    """Ottiene la chiave di crittografia dal SECRET_KEY di Django"""
    # Usa i primi 32 bytes del SECRET_KEY e codifica in base64 per Fernet
    key = settings.SECRET_KEY.encode()[:32]
    return base64.urlsafe_b64encode(key.ljust(32, b'0'))


class AgentAPIKey(models.Model):
    """
    API Key globale per autenticare gli agent
    Solo una chiave attiva alla volta
    """
    key_hash = models.CharField(
        max_length=128,
        unique=True,
        help_text="SHA512 hash dell'API key"
    )
    encrypted_key = models.TextField(
        null=True,
        blank=True,
        help_text="API key criptata (recuperabile con password admin)"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Solo una chiave può essere attiva"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scadenza chiave (null = mai)"
    )
    created_by = models.CharField(
        max_length=100,
        help_text="Utente che ha creato la chiave"
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Ultimo utilizzo della chiave"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Agent API Key'
        verbose_name_plural = 'Agent API Keys'

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"API Key ({status}) - Created {self.created_at}"

    @classmethod
    def hash_key(cls, raw_key: str) -> str:
        """Hash dell'API key con SHA512"""
        return hashlib.sha512(raw_key.encode()).hexdigest()

    @classmethod
    def encrypt_key(cls, raw_key: str) -> str:
        """Cripta la chiave con Fernet (simmetrica)"""
        fernet = Fernet(get_encryption_key())
        encrypted = fernet.encrypt(raw_key.encode())
        return encrypted.decode()

    def decrypt_key(self) -> str:
        """Decripta la chiave"""
        fernet = Fernet(get_encryption_key())
        decrypted = fernet.decrypt(self.encrypted_key.encode())
        return decrypted.decode()

    def verify_key(self, raw_key: str) -> bool:
        """Verifica se la chiave corrisponde"""
        return self.key_hash == self.hash_key(raw_key)

    def save(self, *args, **kwargs):
        # Se questa chiave viene attivata, disattiva tutte le altre
        if self.is_active:
            AgentAPIKey.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class PairingSession(models.Model):
    """
    Sessione di pairing tra server e agent
    Timeout: 3 minuti
    """
    STATUS_CHOICES = [
        ('waiting', 'Waiting for Agent'),
        ('verifying_api', 'Verifying API Key'),
        ('verifying_hash', 'Verifying Identity Hash'),
        ('success', 'Pairing Success'),
        ('failed', 'Pairing Failed'),
        ('expired', 'Session Expired'),
    ]

    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name='pairing_sessions',
        help_text="Target da connettere"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='waiting',
        db_index=True
    )

    # Verifiche fasi
    phase_1_verified = models.BooleanField(
        default=False,
        help_text="API key verificata"
    )
    phase_2_verified = models.BooleanField(
        default=False,
        help_text="Identity hash verificato"
    )

    # Dati agent ricevuti
    agent_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP ricevuto dall'agent"
    )
    agent_hostname = models.CharField(
        max_length=255,
        blank=True,
        help_text="Hostname ricevuto dall'agent"
    )
    agent_mac = models.CharField(
        max_length=17,
        blank=True,
        help_text="MAC address ricevuto dall'agent"
    )

    # Messaggi errore
    error_message = models.TextField(
        blank=True,
        help_text="Messaggio di errore in caso di fallimento"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(
        help_text="Scadenza sessione (3 minuti)"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando il pairing è stato completato"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Pairing Session'
        verbose_name_plural = 'Pairing Sessions'

    def __str__(self):
        return f"Pairing {self.target} - {self.status}"

    def save(self, *args, **kwargs):
        # Imposta scadenza a 3 minuti se non impostata
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=3)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Verifica se la sessione è scaduta"""
        return timezone.now() > self.expires_at

    def verify_phase_1(self, api_key: str) -> bool:
        """
        Fase 1: Verifica API key
        """
        try:
            active_key = AgentAPIKey.objects.get(is_active=True)
            if active_key.verify_key(api_key):
                self.phase_1_verified = True
                self.status = 'verifying_hash'
                self.save(update_fields=['phase_1_verified', 'status'])
                return True
        except AgentAPIKey.DoesNotExist:
            self.error_message = "No active API key found"

        self.status = 'failed'
        self.save(update_fields=['status', 'error_message'])
        return False

    def verify_phase_2(self, ip_address: str, hostname: str, mac_address: str) -> bool:
        """
        Fase 2: Verifica identity hash
        Calcola SHA512(ip+hostname+mac) e confronta con target.identity_hash
        """
        # Salva i dati ricevuti
        self.agent_ip = ip_address
        self.agent_hostname = hostname
        self.agent_mac = mac_address
        self.save(update_fields=['agent_ip', 'agent_hostname', 'agent_mac'])

        # Calcola identity hash
        identity_text = f"{ip_address}{hostname}{mac_address}"
        calculated_hash = hashlib.sha512(identity_text.encode()).hexdigest()

        # Confronta con il target
        if self.target.identity_hash == calculated_hash:
            self.phase_2_verified = True
            self.status = 'success'
            self.completed_at = timezone.now()
            self.save(update_fields=['phase_2_verified', 'status', 'completed_at'])

            # Aggiorna target
            self.target.status = 'online'
            self.target.last_seen = timezone.now()
            self.target.save(update_fields=['status', 'last_seen'])

            return True
        else:
            self.error_message = f"Identity hash mismatch. Expected: {self.target.identity_hash}, Got: {calculated_hash}"
            self.status = 'failed'
            self.save(update_fields=['status', 'error_message'])
            return False


class AgentConnection(models.Model):
    """
    Connessione WebSocket attiva con un agent
    """
    target = models.OneToOneField(
        Target,
        on_delete=models.CASCADE,
        related_name='agent_connection',
        primary_key=True,
        help_text="Target connesso"
    )

    websocket_channel = models.CharField(
        max_length=255,
        help_text="Django Channels channel name"
    )

    is_online = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Agent connesso e attivo"
    )

    # Heartbeat
    last_heartbeat = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Ultimo heartbeat ricevuto"
    )
    heartbeat_interval = models.PositiveIntegerField(
        default=30,
        help_text="Intervallo heartbeat in secondi"
    )

    # System info (ultimo ricevuto)
    system_info = models.JSONField(
        null=True,
        blank=True,
        help_text="Statistiche sistema dall'ultimo heartbeat"
    )

    # Metadata
    connected_at = models.DateTimeField(auto_now_add=True)
    disconnected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando l'agent si è disconnesso"
    )

    class Meta:
        verbose_name = 'Agent Connection'
        verbose_name_plural = 'Agent Connections'

    def __str__(self):
        status = "Online" if self.is_online else "Offline"
        return f"Connection {self.target} ({status})"

    def update_heartbeat(self, system_stats: dict = None):
        """Aggiorna heartbeat e system info"""
        self.last_heartbeat = timezone.now()
        self.is_online = True
        if system_stats:
            self.system_info = system_stats
        self.save(update_fields=['last_heartbeat', 'is_online', 'system_info'])

    def mark_offline(self):
        """Marca connessione come offline"""
        self.is_online = False
        self.disconnected_at = timezone.now()
        self.save(update_fields=['is_online', 'disconnected_at'])

        # Aggiorna anche il target
        self.target.status = 'offline'
        self.target.save(update_fields=['status'])


class AgentCommand(models.Model):
    """
    Comando da eseguire sull'agent
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent to Agent'),
        ('executing', 'Executing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
    ]

    ACTION_CHOICES = [
        ('add_rule', 'Add Firewall Rule'),
        ('remove_rule', 'Remove Firewall Rule'),
        ('sync_rules', 'Sync All Rules'),
        ('block_ip', 'Block IP'),
        ('unblock_ip', 'Unblock IP'),
        ('update_config', 'Update Configuration'),
        ('check_integrity', 'Check File Integrity'),
    ]

    command_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID univoco del comando"
    )

    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name='agent_commands',
        help_text="Target su cui eseguire il comando"
    )

    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        help_text="Azione da eseguire"
    )

    payload = models.JSONField(
        help_text="Parametri del comando"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )

    # Risultato esecuzione
    result = models.JSONField(
        null=True,
        blank=True,
        help_text="Risultato esecuzione comando"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Messaggio di errore"
    )

    # Timeout
    timeout_seconds = models.PositiveIntegerField(
        default=30,
        help_text="Timeout comando in secondi"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Agent Command'
        verbose_name_plural = 'Agent Commands'

    def __str__(self):
        return f"Command {self.action} for {self.target} ({self.status})"

    def mark_sent(self):
        """Marca comando come inviato"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])

    def mark_executing(self):
        """Marca comando come in esecuzione"""
        self.status = 'executing'
        self.save(update_fields=['status'])

    def mark_success(self, result: dict = None):
        """Marca comando come completato con successo"""
        self.status = 'success'
        self.completed_at = timezone.now()
        if result:
            self.result = result
        self.save(update_fields=['status', 'completed_at', 'result'])

    def mark_failed(self, error_message: str):
        """Marca comando come fallito"""
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=['status', 'completed_at', 'error_message'])

    def mark_timeout(self):
        """Marca comando come timeout"""
        self.status = 'timeout'
        self.completed_at = timezone.now()
        self.error_message = "Command execution timeout"
        self.save(update_fields=['status', 'completed_at', 'error_message'])


class AgentHeartbeat(models.Model):
    """
    Storico heartbeat degli agent
    Retention: 24 ore
    """
    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name='agent_heartbeats',
        help_text="Target che ha inviato l'heartbeat"
    )

    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Quando l'heartbeat è stato ricevuto"
    )

    # System statistics
    cpu_percent = models.FloatField(default=0)
    memory_percent = models.FloatField(default=0)
    disk_percent = models.FloatField(default=0)

    # Network statistics
    bytes_sent = models.BigIntegerField(default=0)
    bytes_recv = models.BigIntegerField(default=0)

    # Firewall statistics
    active_rules_count = models.PositiveIntegerField(default=0)
    blocked_ips_count = models.PositiveIntegerField(default=0)

    # Raw data
    raw_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Dati completi heartbeat"
    )

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['target', '-timestamp']),
        ]
        verbose_name = 'Agent Heartbeat'
        verbose_name_plural = 'Agent Heartbeats'

    def __str__(self):
        return f"Heartbeat {self.target} at {self.timestamp}"

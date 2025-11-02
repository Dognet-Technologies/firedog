"""
Models per l'app Targets
Gestione dei sistemi target remoti
"""
from django.db import models
from django.core.validators import validate_ipv46_address
from django.utils import timezone


class Target(models.Model):
    """
    Sistema target remoto su cui viene gestito il firewall
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('installing', 'Installing'),
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('error', 'Error'),
    ]

    # Identificazione
    ip_address = models.GenericIPAddressField(
        unique=True,
        validators=[validate_ipv46_address],
        help_text="Indirizzo IP del target"
    )
    hostname = models.CharField(
        max_length=255,
        blank=True,
        help_text="Hostname del sistema target"
    )
    description = models.TextField(
        blank=True,
        help_text="Descrizione del target"
    )

    # Stato e versione
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Stato corrente del target"
    )
    firedog_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Versione del pacchetto firedog installato"
    )

    # Configurazione SSH
    ssh_port = models.PositiveIntegerField(
        default=22,
        help_text="Porta SSH del target"
    )
    ssh_user = models.CharField(
        max_length=100,
        default='microcyber',
        help_text="Utente SSH per la connessione"
    )

    # Metadata
    last_seen = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Ultimo contatto riuscito"
    )
    last_fetch = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Ultimo fetch dati completato"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Ultimo messaggio di errore"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'last_seen']),
            models.Index(fields=['ip_address']),
        ]
        verbose_name = 'Target'
        verbose_name_plural = 'Targets'

    def __str__(self):
        return f"{self.hostname or self.ip_address} ({self.status})"

    def mark_online(self):
        """Marca il target come online"""
        self.status = 'online'
        self.last_seen = timezone.now()
        self.error_message = ''
        self.save(update_fields=['status', 'last_seen', 'error_message', 'updated_at'])

    def mark_offline(self, error_message=''):
        """Marca il target come offline"""
        self.status = 'offline'
        self.error_message = error_message
        self.save(update_fields=['status', 'error_message', 'updated_at'])

    def mark_error(self, error_message):
        """Marca il target come in errore"""
        self.status = 'error'
        self.error_message = error_message
        self.save(update_fields=['status', 'error_message', 'updated_at'])

    @property
    def is_active(self):
        """Verifica se il target è attivo"""
        return self.status == 'online'

    @property
    def connection_string(self):
        """Restituisce la stringa di connessione SSH"""
        return f"{self.ssh_user}@{self.ip_address}:{self.ssh_port}"

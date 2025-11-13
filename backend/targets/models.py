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

class Statistics(models.Model):
    """Statistiche firewall periodiche"""

    target = models.ForeignKey(
        Target, on_delete=models.CASCADE, related_name="statistics"
    )

    input_packets = models.BigIntegerField(default=0)
    output_packets = models.BigIntegerField(default=0)
    input_dropped = models.BigIntegerField(default=0)
    output_dropped = models.BigIntegerField(default=0)

    pcap_input_size = models.BigIntegerField(default=0)
    pcap_output_size = models.BigIntegerField(default=0)

    collected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "statistics"
        ordering = ["-collected_at"]
        indexes = [
            models.Index(fields=["target", "-collected_at"]),
        ]


class Alert(models.Model):
    """Alert sistema"""

    SEVERITY_CHOICES = [
        ("critical", "Critical"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
        ("info", "Info"),
    ]

    target = models.ForeignKey(
        Target, on_delete=models.CASCADE, related_name="alerts", null=True, blank=True
    )
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    acknowledged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "alerts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.title}"


    @property
    def is_active(self):
        """Verifica se il target è attivo"""
        return self.status == 'online'

    @property
    def connection_string(self):
        """Restituisce la stringa di connessione SSH"""
        return f"{self.ssh_user}@{self.ip_address}:{self.ssh_port}"


# ============================================================================
# AGGIUNGI QUESTI MODELLI AL FILE: backend/targets/models.py
# Inserisci questo codice DOPO il modello Alert
# ============================================================================

class TargetGroup(models.Model):
    """
    Gruppo di target per gestione centralizzata delle regole
    Esempi: Web Servers, DNS Servers, Database Servers, Storage
    """
    ICON_CHOICES = [
        ('server', 'Server'),
        ('database', 'Database'),
        ('globe', 'Web/DNS'),
        ('shield', 'Security'),
        ('hard-drive', 'Storage'),
        ('cloud', 'Cloud'),
        ('layers', 'Application'),
        ('box', 'Generic'),
    ]

    # Identificazione
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nome del gruppo (es. 'Web Servers', 'DNS')"
    )
    description = models.TextField(
        blank=True,
        help_text="Descrizione del gruppo e del suo scopo"
    )

    # UI customization
    color = models.CharField(
        max_length=7,
        default='#3b82f6',
        help_text="Colore esadecimale per UI (es. #3b82f6)"
    )
    icon = models.CharField(
        max_length=20,
        choices=ICON_CHOICES,
        default='server',
        help_text="Icona per rappresentare il gruppo"
    )

    # Relazione Many-to-Many con Target
    targets = models.ManyToManyField(
        Target,
        related_name='groups',
        blank=True,
        help_text="Target appartenenti a questo gruppo"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Target Group'
        verbose_name_plural = 'Target Groups'

    def __str__(self):
        return f"{self.name} ({self.targets.count()} targets)"

    @property
    def target_count(self):
        """Numero di target nel gruppo"""
        return self.targets.count()

    @property
    def online_count(self):
        """Numero di target online nel gruppo"""
        return self.targets.filter(status='online').count()

    def add_target(self, target):
        """Aggiunge un target al gruppo"""
        self.targets.add(target)

    def remove_target(self, target):
        """Rimuove un target dal gruppo"""
        self.targets.remove(target)

    def get_targets_list(self):
        """Restituisce lista dei target come dizionario"""
        return [
            {
                'id': t.id,
                'ip_address': t.ip_address,
                'hostname': t.hostname,
                'status': t.status,
            }
            for t in self.targets.all()
        ]


class GroupRuleTemplate(models.Model):
    """
    Template di regole firewall per un gruppo
    Quando un target viene aggiunto al gruppo, queste regole vengono applicate
    """
    ACTION_CHOICES = [
        ('ACCEPT', 'Accept'),
        ('DROP', 'Drop'),
        ('REJECT', 'Reject'),
    ]

    PROTOCOL_CHOICES = [
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
        ('icmp', 'ICMP'),
        ('all', 'All'),
    ]

    # Gruppo di appartenenza
    group = models.ForeignKey(
        TargetGroup,
        on_delete=models.CASCADE,
        related_name='rule_templates',
        help_text="Gruppo a cui appartiene questo template"
    )

    # Regola
    name = models.CharField(
        max_length=255,
        help_text="Nome descrittivo della regola"
    )
    protocol = models.CharField(
        max_length=10,
        choices=PROTOCOL_CHOICES,
        default='tcp'
    )
    port = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Porta (opzionale per ICMP)"
    )
    source_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP sorgente (opzionale, any se vuoto)"
    )
    action = models.CharField(
        max_length=10,
        choices=ACTION_CHOICES,
        default='ACCEPT'
    )
    comment = models.TextField(
        blank=True,
        help_text="Commento sulla regola"
    )

    # Priority per ordinamento
    priority = models.PositiveIntegerField(
        default=100,
        help_text="Priorità di applicazione (più basso = più importante)"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['group', 'priority', 'port']
        verbose_name = 'Group Rule Template'
        verbose_name_plural = 'Group Rule Templates'

    def __str__(self):
        port_str = f":{self.port}" if self.port else ""
        return f"{self.group.name} - {self.protocol}{port_str} {self.action}"

    def to_iptables_command(self, target_ip):
        """
        Converte il template in comando iptables
        """
        cmd_parts = ['iptables', '-A', 'INPUT']
        
        if self.protocol != 'all':
            cmd_parts.extend(['-p', self.protocol])
        
        if self.port:
            cmd_parts.extend(['--dport', str(self.port)])
        
        if self.source_ip:
            cmd_parts.extend(['-s', self.source_ip])
        
        cmd_parts.extend(['-j', self.action])
        
        if self.comment:
            cmd_parts.extend(['-m', 'comment', '--comment', f'"{self.comment}"'])
        
        return ' '.join(cmd_parts)

class WhitelistEntry(models.Model):
    """
    Entry nella whitelist - IP o subnet autorizzati permanentemente
    Questi IP bypassano completamente le regole del firewall
    """
    # Relazione con target
    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name='whitelist_entries',
        help_text="Target su cui applicare la whitelist"
    )

    # IP o subnet
    ip_address = models.CharField(
        max_length=50,
        help_text="Indirizzo IP o subnet CIDR (es. 192.168.1.0/24)"
    )

    description = models.CharField(
        max_length=512,
        blank=True,
        help_text="Descrizione dell'IP o subnet"
    )

    # Metadata
    added_by = models.CharField(
        max_length=100,
        help_text="Utente che ha aggiunto l'entry"
    )

    added_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Quando è stata aggiunta"
    )

    last_seen = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Ultimo accesso rilevato da questo IP"
    )

    hit_count = models.PositiveIntegerField(
        default=0,
        help_text="Numero di connessioni da questo IP"
    )

    # Stato
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Se disabilitato, l'IP non è più in whitelist"
    )

    class Meta:
        ordering = ['-added_at']
        indexes = [
            models.Index(fields=['target', 'is_active']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['-added_at']),
        ]
        unique_together = ['target', 'ip_address']
        verbose_name = 'Whitelist Entry'
        verbose_name_plural = 'Whitelist Entries'

    def __str__(self):
        return f"{self.ip_address} on {self.target.hostname}"

    @property
    def is_subnet(self):
        """Verifica se è una subnet CIDR"""
        return '/' in self.ip_address

    def increment_hit_count(self):
        """Incrementa contatore accessi e aggiorna last_seen"""
        self.hit_count += 1
        self.last_seen = timezone.now()
        self.save(update_fields=['hit_count', 'last_seen'])


class BlockedIP(models.Model):
    """
    IP bloccato manualmente o automaticamente dal sistema
    """
    BLOCK_REASON_CHOICES = [
        ('manual', 'Manual Block'),
        ('threat_detected', 'Threat Detected'),
        ('port_scan', 'Port Scanning'),
        ('brute_force', 'Brute Force Attack'),
        ('syn_flood', 'SYN Flood'),
        ('ddos', 'DDoS Attack'),
        ('malware', 'Malware Activity'),
        ('other', 'Other'),
    ]

    # Relazione con target
    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name='blocked_ips',
        help_text="Target su cui bloccare l'IP"
    )

    # IP bloccato
    ip_address = models.GenericIPAddressField(
        validators=[validate_ipv46_address],
        db_index=True,
        help_text="Indirizzo IP bloccato"
    )

    # Motivo blocco
    block_reason = models.CharField(
        max_length=20,
        choices=BLOCK_REASON_CHOICES,
        default='manual',
        help_text="Motivo del blocco"
    )

    description = models.TextField(
        blank=True,
        help_text="Descrizione dettagliata del blocco"
    )

    # Metadata
    blocked_by = models.CharField(
        max_length=100,
        help_text="Utente o sistema che ha bloccato l'IP"
    )

    blocked_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Quando è stato bloccato"
    )

    # Statistiche minaccia
    threat_score = models.PositiveIntegerField(
        default=0,
        help_text="Score della minaccia (0-100)"
    )

    packet_count = models.PositiveIntegerField(
        default=0,
        help_text="Numero di pacchetti bloccati da questo IP"
    )

    last_attempt = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Ultimo tentativo di connessione"
    )

    # Blocco temporaneo
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scadenza blocco (null = permanente)"
    )

    # Stato
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Se falso, il blocco è stato rimosso"
    )

    unblocked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando è stato sbloccato"
    )

    unblocked_by = models.CharField(
        max_length=100,
        blank=True,
        help_text="Utente che ha rimosso il blocco"
    )

    class Meta:
        ordering = ['-blocked_at']
        indexes = [
            models.Index(fields=['target', 'is_active']),
            models.Index(fields=['ip_address', 'is_active']),
            models.Index(fields=['block_reason']),
            models.Index(fields=['-blocked_at']),
            models.Index(fields=['expires_at']),
        ]
        unique_together = ['target', 'ip_address']
        verbose_name = 'Blocked IP'
        verbose_name_plural = 'Blocked IPs'

    def __str__(self):
        return f"{self.ip_address} blocked on {self.target.hostname}"

    @property
    def is_expired(self):
        """Verifica se il blocco è scaduto"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_permanent(self):
        """Verifica se il blocco è permanente"""
        return self.expires_at is None

    def unblock(self, unblocked_by: str):
        """Sblocca l'IP"""
        self.is_active = False
        self.unblocked_at = timezone.now()
        self.unblocked_by = unblocked_by
        self.save(update_fields=['is_active', 'unblocked_at', 'unblocked_by'])

    def increment_packet_count(self, count: int = 1):
        """Incrementa contatore pacchetti bloccati"""
        self.packet_count += count
        self.last_attempt = timezone.now()
        self.save(update_fields=['packet_count', 'last_attempt'])

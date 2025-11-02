"""
Models per l'app Threats
Gestione delle minacce rilevate dal traffic analyzer
"""
from django.db import models
from django.core.validators import validate_ipv46_address, MinValueValidator, MaxValueValidator
from targets.models import Target


class ThreatLog(models.Model):
    """
    Log delle minacce rilevate dal traffic analyzer
    """
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    # Relazione con target
    target = models.ForeignKey(
        Target,
        on_delete=models.CASCADE,
        related_name='threats',
        help_text="Target che ha rilevato la minaccia"
    )

    # Informazioni minaccia
    source_ip = models.GenericIPAddressField(
        validators=[validate_ipv46_address],
        db_index=True,
        help_text="IP sorgente della minaccia"
    )

    dest_port = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        help_text="Porta di destinazione attaccata"
    )

    protocol = models.CharField(
        max_length=10,
        blank=True,
        help_text="Protocollo utilizzato"
    )

    # Scoring
    threat_score = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        db_index=True,
        help_text="Punteggio della minaccia (0-100)"
    )

    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        db_index=True,
        help_text="Livello di gravità"
    )

    # Dettagli
    packet_count = models.PositiveIntegerField(
        default=1,
        help_text="Numero di pacchetti bloccati"
    )

    reasons = models.JSONField(
        default=list,
        help_text="Motivi del threat score (lista di stringhe)"
    )

    description = models.TextField(
        blank=True,
        help_text="Descrizione dettagliata della minaccia"
    )

    # Geolocalizzazione (opzionale, futuro)
    country_code = models.CharField(
        max_length=2,
        blank=True,
        help_text="Codice paese ISO dell'IP sorgente"
    )

    # Stato
    is_blocked = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Indica se l'IP è stato bloccato"
    )

    is_resolved = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Indica se la minaccia è stata risolta/gestita"
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando la minaccia è stata risolta"
    )

    # Timestamps
    detected_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Quando la minaccia è stata rilevata"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-detected_at', '-threat_score']
        indexes = [
            models.Index(fields=['target', 'detected_at']),
            models.Index(fields=['target', 'threat_score']),
            models.Index(fields=['source_ip', 'detected_at']),
            models.Index(fields=['severity', 'is_resolved']),
        ]
        verbose_name = 'Threat Log'
        verbose_name_plural = 'Threat Logs'

    def __str__(self):
        return f"{self.source_ip} -> {self.target.ip_address} (score: {self.threat_score})"

    @property
    def severity_level(self):
        """Calcola il livello di severity basato sul threat_score"""
        if self.threat_score >= 80:
            return 'critical'
        elif self.threat_score >= 60:
            return 'high'
        elif self.threat_score >= 30:
            return 'medium'
        else:
            return 'low'

    def update_severity(self):
        """Aggiorna automaticamente la severity basata sul threat_score"""
        self.severity = self.severity_level
        self.save(update_fields=['severity', 'updated_at'])

    def mark_resolved(self):
        """Marca la minaccia come risolta"""
        from django.utils import timezone
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.save(update_fields=['is_resolved', 'resolved_at', 'updated_at'])

    def mark_blocked(self):
        """Marca l'IP come bloccato"""
        self.is_blocked = True
        self.save(update_fields=['is_blocked', 'updated_at'])

    @property
    def attack_description(self):
        """Descrizione dell'attacco"""
        port_info = f" on port {self.dest_port}" if self.dest_port else ""
        proto_info = f" ({self.protocol})" if self.protocol else ""
        return f"Attack from {self.source_ip}{port_info}{proto_info}"

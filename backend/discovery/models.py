"""
Models per l'app Discovery
Network Discovery per individuare host sulla rete
"""
from django.db import models
from django.core.validators import validate_ipv46_address


class DiscoveredHost(models.Model):
    """
    Host scoperto tramite network scan (arp-scan)
    """
    # Identificazione
    ip_address = models.GenericIPAddressField(
        unique=True,
        validators=[validate_ipv46_address],
        db_index=True,
        help_text="Indirizzo IP scoperto"
    )

    mac_address = models.CharField(
        max_length=17,
        blank=True,
        help_text="Indirizzo MAC (formato XX:XX:XX:XX:XX:XX)"
    )

    hostname = models.CharField(
        max_length=255,
        blank=True,
        help_text="Hostname risolto (se disponibile)"
    )

    # Vendor info (da MAC lookup)
    vendor = models.CharField(
        max_length=255,
        blank=True,
        help_text="Vendor dell'interfaccia di rete"
    )

    # Network info
    network = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Rete di appartenenza"
    )

    netmask = models.CharField(
        max_length=15,
        blank=True,
        help_text="Netmask della rete"
    )

    # Discovery info
    discovered_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Quando l'host è stato scoperto"
    )

    last_seen = models.DateTimeField(
        auto_now=True,
        help_text="Ultimo scan in cui l'host è stato visto"
    )

    scan_count = models.PositiveIntegerField(
        default=1,
        help_text="Numero di volte che l'host è stato visto negli scan"
    )

    # Stato
    is_alive = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Host ancora attivo nell'ultimo scan"
    )

    is_imported = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Host importato come target"
    )

    # Note
    notes = models.TextField(
        blank=True,
        help_text="Note sull'host scoperto"
    )

    class Meta:
        ordering = ['-last_seen', 'ip_address']
        indexes = [
            models.Index(fields=['is_alive', 'is_imported']),
            models.Index(fields=['network']),
            models.Index(fields=['discovered_at']),
        ]
        verbose_name = 'Discovered Host'
        verbose_name_plural = 'Discovered Hosts'

    def __str__(self):
        name = self.hostname or self.ip_address
        vendor_info = f" ({self.vendor})" if self.vendor else ""
        return f"{name}{vendor_info}"

    def increment_scan_count(self):
        """Incrementa il contatore degli scan"""
        self.scan_count += 1
        self.is_alive = True
        self.save(update_fields=['scan_count', 'is_alive', 'last_seen'])

    def mark_dead(self):
        """Marca l'host come non più attivo"""
        self.is_alive = False
        self.save(update_fields=['is_alive', 'last_seen'])

    def mark_imported(self):
        """Marca l'host come importato nei target"""
        self.is_imported = True
        self.save(update_fields=['is_imported', 'last_seen'])

    @property
    def display_name(self):
        """Nome visualizzabile dell'host"""
        if self.hostname:
            return f"{self.hostname} ({self.ip_address})"
        return self.ip_address

    @property
    def is_recently_discovered(self):
        """Verifica se l'host è stato scoperto di recente (ultime 24h)"""
        from django.utils import timezone
        from datetime import timedelta
        threshold = timezone.now() - timedelta(hours=24)
        return self.discovered_at >= threshold

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
import hashlib
import json


class Target(models.Model):
    """Sistema target con firedog installato"""

    STATUS_CHOICES = [
        ("pending", "Pending Installation"),
        ("installing", "Installing"),
        ("online", "Online"),
        ("offline", "Offline"),
        ("error", "Error"),
        ("disabled", "Disabled"),
    ]

    hostname = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    ssh_port = models.IntegerField(default=22)

    # Installation
    installation_status = models.CharField(max_length=100, blank=True)
    installation_error = models.TextField(blank=True)
    firedog_version = models.CharField(max_length=20, blank=True)

    # Connection
    last_seen = models.DateTimeField(null=True, blank=True)
    last_fetch = models.DateTimeField(null=True, blank=True)
    fetch_interval_minutes = models.IntegerField(default=10)

    # Metadata
    os_info = models.CharField(max_length=255, blank=True)
    kernel_version = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "targets"
        ordering = ["hostname"]

    def __str__(self):
        return f"{self.hostname} ({self.ip_address})"

    def mark_online(self):
        self.status = "online"
        self.last_seen = timezone.now()
        self.save()

    def mark_offline(self):
        self.status = "offline"
        self.save()


class ThreatLog(models.Model):
    """Log minacce rilevate da traffic-analyzer"""

    CLASSIFICATION_CHOICES = [
        ("CRITICAL", "Critical"),
        ("HIGH", "High"),
        ("MEDIUM", "Medium"),
        ("LOW", "Low"),
    ]

    target = models.ForeignKey(Target, on_delete=models.CASCADE, related_name="threats")
    source_ip = models.GenericIPAddressField()
    threat_score = models.IntegerField()

    # Traffic details
    packets = models.IntegerField(default=0)
    ports_count = models.IntegerField(default=0)
    protocols = models.CharField(max_length=100, blank=True)

    # Classification
    threat_type = models.CharField(max_length=50)  # Port Scanning, SYN Flood, etc.
    classification = models.CharField(max_length=20, choices=CLASSIFICATION_CHOICES)

    detected_at = models.DateTimeField(auto_now_add=True)
    acknowledged = models.BooleanField(default=False)

    class Meta:
        db_table = "threat_logs"
        ordering = ["-detected_at"]
        indexes = [
            models.Index(fields=["target", "-detected_at"]),
            models.Index(fields=["classification", "-detected_at"]),
            models.Index(fields=["source_ip"]),
        ]

    def __str__(self):
        return (
            f"{self.source_ip} on {self.target.hostname} - Score: {self.threat_score}"
        )

    @classmethod
    def classify_score(cls, score):
        """Classifica score in categoria"""
        if score >= 80:
            return "CRITICAL"
        elif score >= 60:
            return "HIGH"
        elif score >= 40:
            return "MEDIUM"
        else:
            return "LOW"


class FirewallRule(models.Model):
    """Regola iptables snapshot"""

    CHAIN_CHOICES = [
        ("INPUT", "Input"),
        ("OUTPUT", "Output"),
        ("FORWARD", "Forward"),
    ]

    target = models.ForeignKey(Target, on_delete=models.CASCADE, related_name="rules")
    chain = models.CharField(max_length=10, choices=CHAIN_CHOICES)
    rule_number = models.IntegerField()

    protocol = models.CharField(max_length=10, blank=True)
    port = models.IntegerField(null=True, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    dest_ip = models.GenericIPAddressField(null=True, blank=True)
    action = models.CharField(max_length=20)
    comment = models.TextField(blank=True)

    # Counters
    packets = models.BigIntegerField(default=0)
    bytes = models.BigIntegerField(default=0)

    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "firewall_rules"
        ordering = ["target", "chain", "rule_number"]
        unique_together = ["target", "chain", "rule_number"]

    def __str__(self):
        return f"{self.target.hostname} - {self.chain} #{self.rule_number}"


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


class Config(models.Model):
    """Configurazione sistema"""

    key = models.CharField(max_length=100, primary_key=True)
    value = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "config"

    @classmethod
    def get(cls, key, default=None):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value):
        obj, created = cls.objects.update_or_create(
            key=key, defaults={"value": str(value)}
        )
        return obj


class SSHKey(models.Model):
    """Chiave SSH sistema"""

    key_type = models.CharField(max_length=20, default="ed25519")
    private_key = models.TextField()
    public_key = models.TextField()
    fingerprint = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_rotated = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ssh_keys"

    def __str__(self):
        return f"SSH Key ({self.key_type}) - {self.fingerprint[:20]}..."


class FileIntegrity(models.Model):
    """File integrity monitoring"""

    filepath = models.CharField(max_length=500, unique=True)
    sha512_hash = models.CharField(max_length=128)
    last_checked = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "file_integrity"

    @classmethod
    def compute_hash(cls, filepath):
        """Calcola SHA512 di un file"""
        sha512 = hashlib.sha512()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha512.update(chunk)
        return sha512.hexdigest()

    @classmethod
    def check_file(cls, filepath):
        """Verifica integrità file"""
        current_hash = cls.compute_hash(filepath)

        try:
            record = cls.objects.get(filepath=filepath)
            if record.sha512_hash != current_hash:
                return False, record.sha512_hash, current_hash
            return True, current_hash, current_hash
        except cls.DoesNotExist:
            # Primo check, salva hash
            cls.objects.create(filepath=filepath, sha512_hash=current_hash)
            return True, current_hash, current_hash


class AuditLog(models.Model):
    """Audit log di tutte le azioni"""

    username = models.CharField(max_length=100)
    action = models.CharField(max_length=255)
    target = models.ForeignKey(Target, on_delete=models.SET_NULL, null=True, blank=True)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.username} - {self.action} @ {self.timestamp}"

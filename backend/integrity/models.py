"""
Models per l'app Integrity
File Integrity Monitoring per i file locali di FireDog
"""

from django.db import models
from django.contrib.auth.models import User


class FileIntegrity(models.Model):
    """
    Monitoring dell'integrità dei file critici del sistema FireDog
    """

    STATUS_CHOICES = [
        ("ok", "OK"),
        ("modified", "Modified"),
        ("missing", "Missing"),
        ("new", "New"),
    ]

    # Identificazione file
    file_path = models.CharField(
        max_length=512,
        unique=True,
        db_index=True,
        help_text="Path completo del file monitorato",
    )

    file_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Tipo di file (python, config, script, etc.)",
    )

    # Hash SHA512
    sha512_hash = models.CharField(
        max_length=128, help_text="Hash SHA512 del contenuto del file"
    )

    previous_hash = models.CharField(
        max_length=128, blank=True, help_text="Hash precedente per confronto"
    )

    # Metadata file
    file_size = models.PositiveBigIntegerField(help_text="Dimensione del file in bytes")

    file_permissions = models.CharField(
        max_length=10, blank=True, help_text="Permessi del file (es. 0644)"
    )

    file_owner = models.CharField(
        max_length=100, blank=True, help_text="Proprietario del file"
    )

    # Stato
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ok",
        db_index=True,
        help_text="Stato corrente del file",
    )

    # Change tracking
    last_checked = models.DateTimeField(
        auto_now=True, help_text="Ultimo controllo effettuato"
    )

    last_modified = models.DateTimeField(
        null=True, blank=True, help_text="Ultima modifica rilevata del file"
    )

    change_detected_at = models.DateTimeField(
        null=True, blank=True, help_text="Quando è stata rilevata una modifica"
    )

    # Gestione modifiche
    is_change_approved = models.BooleanField(
        default=False, help_text="Modifica approvata dall'amministratore"
    )

    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_changes",
        help_text="Utente che ha approvato la modifica",
    )

    approved_at = models.DateTimeField(
        null=True, blank=True, help_text="Quando la modifica è stata approvata"
    )

    change_notes = models.TextField(blank=True, help_text="Note sulla modifica")

    # Alert
    alert_sent = models.BooleanField(
        default=False, help_text="Alert inviato per questa modifica"
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Quando il file è stato aggiunto al monitoring"
    )

    class Meta:
        ordering = ["-change_detected_at", "file_path"]
        indexes = [
            models.Index(fields=["status", "is_change_approved"]),
            models.Index(fields=["last_checked"]),
            models.Index(fields=["change_detected_at"]),
        ]
        verbose_name = "File Integrity"
        verbose_name_plural = "File Integrity Records"

    def __str__(self):
        return f"{self.file_path} ({self.status})"

    @property
    def is_modified(self):
        """Verifica se il file è stato modificato"""
        return self.status == "modified" and not self.is_change_approved

    @property
    def needs_attention(self):
        """Verifica se il file richiede attenzione"""
        return self.status in ["modified", "missing"] and not self.is_change_approved

    def approve_change(self, user, notes=""):
        """Approva una modifica del file"""
        from django.utils import timezone

        self.is_change_approved = True
        self.approved_by = user
        self.approved_at = timezone.now()
        self.change_notes = notes
        self.status = "ok"
        self.previous_hash = self.sha512_hash
        self.save(
            update_fields=[
                "is_change_approved",
                "approved_by",
                "approved_at",
                "change_notes",
                "status",
                "previous_hash",
                "last_checked",
            ]
        )

    def mark_modified(self, new_hash):
        """Marca il file come modificato con nuovo hash"""
        from django.utils import timezone

        self.previous_hash = self.sha512_hash
        self.sha512_hash = new_hash
        self.status = "modified"
        self.change_detected_at = timezone.now()
        self.is_change_approved = False
        self.alert_sent = False
        self.save(
            update_fields=[
                "previous_hash",
                "sha512_hash",
                "status",
                "change_detected_at",
                "is_change_approved",
                "alert_sent",
                "last_checked",
            ]
        )

    def mark_missing(self):
        """Marca il file come mancante"""
        from django.utils import timezone

        self.status = "missing"
        self.change_detected_at = timezone.now()
        self.alert_sent = False
        self.save(
            update_fields=["status", "change_detected_at", "alert_sent", "last_checked"]
        )

    def mark_ok(self):
        """Marca il file come OK"""
        self.status = "ok"
        self.change_detected_at = None
        self.save(update_fields=["status", "change_detected_at", "last_checked"])

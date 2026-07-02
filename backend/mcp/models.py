"""
Modelli per il server MCP di FireDog.

Le API key MCP sono per-utente e impersonano il proprietario: le richieste
autenticate con una chiave hanno gli stessi permessi (gruppi Admin/Reporter)
dell'utente. La chiave in chiaro viene mostrata una sola volta alla creazione
e persistita solo come hash SHA-256 (mai recuperabile), come richiesto dal
contratto MCP cross-prodotto.
"""

import hashlib
import secrets
import string

from django.conf import settings
from django.db import models
from django.utils import timezone

# Formato chiave: prefisso leggibile + 48 alfanumerici (convenzione contratto MCP)
MCP_KEY_PREFIX = "fd_"
MCP_KEY_RANDOM_LENGTH = 48
# Porzione della chiave salvata in chiaro per identificarla in UI/log
MCP_KEY_PREFIX_DISPLAY_CHARS = 8


class MCPAPIKey(models.Model):
    """API key per-utente per l'endpoint MCP (POST /api/mcp)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mcp_api_keys",
        help_text="Utente proprietario: la chiave ne eredita ruolo e permessi",
    )
    name = models.CharField(
        max_length=100, help_text="Nome descrittivo della chiave (es. 'claude-desktop')"
    )
    key_prefix = models.CharField(
        max_length=16,
        help_text="Prefisso visibile della chiave per identificarla (es. fd_a1B2c3D4)",
    )
    key_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="SHA-256 esadecimale della chiave completa",
    )
    is_active = models.BooleanField(default=True, help_text="False = chiave revocata")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True, blank=True, help_text="Scadenza opzionale della chiave"
    )
    last_used_at = models.DateTimeField(
        null=True, blank=True, help_text="Ultimo utilizzo (aggiornato best-effort)"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "MCP API Key"
        verbose_name_plural = "MCP API Keys"

    def __str__(self):
        return f"{self.name} ({self.key_prefix}…) - {self.user}"

    @classmethod
    def generate_raw_key(cls) -> str:
        """Genera una nuova chiave in chiaro: fd_<48 alfanumerici>."""
        alphabet = string.ascii_letters + string.digits
        random_part = "".join(
            secrets.choice(alphabet) for _ in range(MCP_KEY_RANDOM_LENGTH)
        )
        return f"{MCP_KEY_PREFIX}{random_part}"

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """SHA-256 esadecimale della chiave in chiaro."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @classmethod
    def create_for_user(cls, user, name: str, expires_at=None):
        """
        Crea una chiave per l'utente e restituisce (istanza, chiave_in_chiaro).
        La chiave in chiaro non è più recuperabile dopo questa chiamata.
        """
        raw_key = cls.generate_raw_key()
        instance = cls.objects.create(
            user=user,
            name=name,
            key_prefix=raw_key[: len(MCP_KEY_PREFIX) + MCP_KEY_PREFIX_DISPLAY_CHARS],
            key_hash=cls.hash_key(raw_key),
            expires_at=expires_at,
        )
        return instance, raw_key

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= timezone.now()

    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired

    def mark_used(self):
        """Aggiorna last_used_at best-effort (mai bloccare la richiesta)."""
        try:
            self.last_used_at = timezone.now()
            self.save(update_fields=["last_used_at"])
        except Exception:  # noqa: BLE001 - best effort per contratto
            pass

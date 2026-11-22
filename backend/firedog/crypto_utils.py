"""
Derivazione di chiavi di cifratura simmetrica (Fernet) da SECRET_KEY.

PRIMA: sia agent_manager (chiave agent) sia settings (password SMTP)
derivavano la chiave Fernet troncando SECRET_KEY ai primi 32 byte grezzi,
SENZA alcuna KDF — lo stesso identico segreto usato per firmare i JWT,
nessuna domain separation tra i tre usi (CRITICAL trovato in code review,
2026-11): un leak di SECRET_KEY permetteva contemporaneamente di forgiare
JWT di qualunque ruolo E decifrare ogni credenziale salvata nel DB.

Ora ogni uso ha la propria chiave derivata via HKDF-SHA256 con un `info`
distinto — un leak di una chiave derivata non compromette le altre, e
SECRET_KEY non è mai più usato direttamente come chiave di cifratura.
"""

import base64

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings


def derive_fernet_key(info: bytes) -> bytes:
    """Deriva una chiave Fernet (32 byte, base64 urlsafe) da SECRET_KEY
    via HKDF-SHA256. `info` separa i contesti d'uso, es.
    b"agent-api-key-encryption-v1" o b"smtp-password-encryption-v1" —
    non riusare lo stesso `info` per due scopi distinti."""
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info)
    derived = hkdf.derive(settings.SECRET_KEY.encode())
    return base64.urlsafe_b64encode(derived)


def legacy_truncated_secret_key() -> bytes:
    """Schema di derivazione PRE-fix (troncamento grezzo di SECRET_KEY,
    nessuna KDF) — mantenuto SOLO per decifrare dati già cifrati prima di
    questo fix su installazioni esistenti. Non usare per cifrare dati
    nuovi. Da rimuovere una volta che tutte le installazioni in campo
    hanno ri-salvato le proprie chiavi/password (il save() le ri-cifra
    sempre con lo schema nuovo)."""
    key = settings.SECRET_KEY.encode()[:32].ljust(32, b"0")
    return base64.urlsafe_b64encode(key)

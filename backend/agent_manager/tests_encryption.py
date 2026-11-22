"""
Regressione per il fix CRITICAL su derivazione della chiave di cifratura
(code review, 2026-11): la chiave Fernet per l'Agent API key era
SECRET_KEY troncato a 32 byte senza KDF, lo stesso segreto della firma
JWT — ora derivata via HKDF con un `info` dedicato (vedi
firedog/crypto_utils.py). Verifica anche la retrocompatibilità: una
chiave già cifrata con lo schema legacy resta decifrabile e viene
migrata automaticamente al primo read.
"""

from django.test import TestCase

from firedog.crypto_utils import derive_fernet_key, legacy_truncated_secret_key

from .models import AgentAPIKey


class HkdfKeyDerivationTests(TestCase):
    def test_chiavi_con_info_diversi_sono_diverse(self):
        k1 = derive_fernet_key(b"agent-api-key-encryption-v1")
        k2 = derive_fernet_key(b"smtp-password-encryption-v1")
        self.assertNotEqual(k1, k2)

    def test_chiave_hkdf_non_coincide_con_lo_schema_legacy(self):
        # Il punto centrale del fix: la chiave nuova non deve più essere
        # ricostruibile troncando SECRET_KEY.
        self.assertNotEqual(
            derive_fernet_key(b"agent-api-key-encryption-v1"),
            legacy_truncated_secret_key(),
        )

    def test_derivazione_e_deterministica(self):
        self.assertEqual(
            derive_fernet_key(b"agent-api-key-encryption-v1"),
            derive_fernet_key(b"agent-api-key-encryption-v1"),
        )


class AgentApiKeyEncryptionTests(TestCase):
    def test_round_trip_con_schema_nuovo(self):
        raw_key = "test-raw-key-12345"
        api_key = AgentAPIKey.objects.create(
            key_hash=AgentAPIKey.hash_key(raw_key),
            encrypted_key=AgentAPIKey.encrypt_key(raw_key),
            is_active=True,
            created_by="test",
        )
        self.assertEqual(api_key.decrypt_key(), raw_key)

    def test_chiave_cifrata_con_schema_legacy_resta_decifrabile_e_viene_migrata(self):
        from cryptography.fernet import Fernet

        raw_key = "legacy-raw-key-67890"
        legacy_encrypted = Fernet(legacy_truncated_secret_key()).encrypt(
            raw_key.encode()
        ).decode()

        api_key = AgentAPIKey.objects.create(
            key_hash=AgentAPIKey.hash_key(raw_key),
            encrypted_key=legacy_encrypted,
            is_active=True,
            created_by="test",
        )

        # Decifra correttamente nonostante sia cifrata col vecchio schema.
        self.assertEqual(api_key.decrypt_key(), raw_key)

        # Migrazione al primo read: ora in DB c'è il blob cifrato col
        # nuovo schema, diverso da quello legacy originale.
        api_key.refresh_from_db()
        self.assertNotEqual(api_key.encrypted_key, legacy_encrypted)
        # E resta comunque decifrabile correttamente con lo schema nuovo.
        self.assertEqual(api_key.decrypt_key(), raw_key)

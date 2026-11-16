"""
Regressione per il fix di controllo accessi (CRITICAL trovato in code
review, 2026-11): SystemSettingsViewSet/DatabaseManagementViewSet usavano
solo IsAuthenticated — un Reporter poteva modificare la configurazione di
sistema o pulire/cancellare dati dal database (inclusi i log di audit).

Copre anche il fix separato su NotificationViewSet: importava per errore
rest_framework.permissions.IsAdminUser (check su is_staff) invece di
accounts.permissions.IsAdminUser (check sul gruppo "Admin" usato ovunque
altrove) — un Admin per gruppo ma senza is_staff veniva rifiutato.
"""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from firedog.crypto_utils import legacy_truncated_secret_key

from .models import NotificationConfig


class RoleBasedAccessTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin_group, _ = Group.objects.get_or_create(name="Admin")

        self.admin = User.objects.create_user("admin", password="x")
        self.admin.groups.add(admin_group)

        self.reporter = User.objects.create_user("reporter", password="x")


class SystemSettingsAccessControlTests(RoleBasedAccessTestCase):
    def test_reporter_non_puo_fare_bulk_update(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.post(
            "/api/settings/settings/bulk_update/",
            {"settings": {"systemName": "Test"}, "category": "general"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_puo_fare_bulk_update(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/settings/settings/bulk_update/",
            {"settings": {"systemName": "Test"}, "category": "general"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_reporter_puo_leggere_le_impostazioni(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/settings/settings/")
        self.assertEqual(response.status_code, 200)


class DatabaseManagementAccessControlTests(RoleBasedAccessTestCase):
    def test_reporter_non_puo_lanciare_il_cleanup(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.post(
            "/api/settings/database/cleanup/",
            {"cleanup_type": "audit_logs", "retention_days": 90, "dry_run": True},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_puo_lanciare_il_cleanup_in_dry_run(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/settings/database/cleanup/",
            {"cleanup_type": "audit_logs", "retention_days": 90, "dry_run": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_reporter_puo_leggere_le_statistiche_db(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/settings/database/stats/")
        self.assertEqual(response.status_code, 200)


class NotificationViewSetGroupBasedAdminTests(RoleBasedAccessTestCase):
    def test_admin_per_gruppo_senza_is_staff_accede_alla_config(self):
        # Prima del fix dell'import, questo utente (Admin per gruppo, ma
        # is_staff=False come ogni utente di questo progetto) sarebbe
        # stato rifiutato da rest_framework.permissions.IsAdminUser.
        self.assertFalse(self.admin.is_staff)
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/settings/notifications/config/")
        self.assertEqual(response.status_code, 200)

    def test_reporter_non_accede_alla_config_notifiche(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/settings/notifications/config/")
        self.assertEqual(response.status_code, 403)


class SmtpPasswordEncryptionTests(TestCase):
    """
    Regressione per il fix CRITICAL su derivazione della chiave di
    cifratura (code review, 2026-11): la password SMTP era cifrata con
    SECRET_KEY troncato senza KDF, lo stesso schema (e lo stesso bug)
    dell'Agent API key. Ora via HKDF, con retrocompatibilità/migrazione
    al primo read per le password già cifrate su installazioni esistenti.
    """

    def test_round_trip_con_schema_nuovo(self):
        config = NotificationConfig.get_config()
        config.smtp_password = "s3cret-password"
        config.save()
        self.assertTrue(config.smtp_password.startswith("gAAAAAB"))
        self.assertEqual(config.get_decrypted_smtp_password(), "s3cret-password")

    def test_password_cifrata_con_schema_legacy_resta_decifrabile_e_viene_migrata(self):
        from cryptography.fernet import Fernet

        legacy_encrypted = Fernet(legacy_truncated_secret_key()).encrypt(
            b"legacy-smtp-password"
        ).decode()

        config = NotificationConfig.objects.create(
            pk=1, smtp_password=legacy_encrypted
        )
        # Bypassa save() apposta (già invocato da create() tramite .save()
        # interno di Model.objects.create — ma smtp_password inizia già per
        # gAAAAAB quindi save() non la ri-cifra, resta quella legacy).

        self.assertEqual(config.get_decrypted_smtp_password(), "legacy-smtp-password")

        config.refresh_from_db()
        self.assertNotEqual(config.smtp_password, legacy_encrypted)
        self.assertEqual(config.get_decrypted_smtp_password(), "legacy-smtp-password")

    def test_password_in_chiaro_che_inizia_per_gaaaaab_viene_comunque_cifrata(self):
        # Regressione specifica per l'euristica fragile (MEDIUM, code
        # review 2026-11): una password in chiaro che inizia per
        # coincidenza con "gAAAAAB" (il prefisso di un token Fernet)
        # doveva essere comunque rilevata come NON cifrata, perché ora si
        # verifica provando a decifrare, non guardando il prefisso.
        config = NotificationConfig.objects.create(pk=1, smtp_password="gAAAAAB-not-a-real-token")
        self.assertNotEqual(config.smtp_password, "gAAAAAB-not-a-real-token")
        self.assertEqual(config.get_decrypted_smtp_password(), "gAAAAAB-not-a-real-token")

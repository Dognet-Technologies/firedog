"""
Regressione per il fix di controllo accessi (CRITICAL trovato in code
review, 2026-11): FileIntegrityViewSet.approve usava solo IsAuthenticated
— un Reporter poteva approvare (sopprimere) un alert di integrità file
reale, una decisione di sicurezza non una semplice lettura.
"""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import FileIntegrity


class FileIntegrityAccessControlTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin_group, _ = Group.objects.get_or_create(name="Admin")

        self.admin = User.objects.create_user("admin", password="x")
        self.admin.groups.add(admin_group)

        self.reporter = User.objects.create_user("reporter", password="x")

        self.entry = FileIntegrity.objects.create(
            file_path="/etc/firewall/firedog.conf", status="modified", file_size=0
        )

    def test_reporter_non_puo_approvare_una_modifica(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.post(f"/api/integrity/{self.entry.id}/approve/")
        self.assertEqual(response.status_code, 403)
        self.entry.refresh_from_db()
        self.assertFalse(self.entry.is_change_approved)

    def test_admin_puo_approvare_una_modifica(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f"/api/integrity/{self.entry.id}/approve/")
        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertTrue(self.entry.is_change_approved)

    def test_reporter_puo_leggere_la_lista(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/integrity/")
        self.assertEqual(response.status_code, 200)

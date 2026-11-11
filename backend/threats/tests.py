"""
Regressione per il fix di controllo accessi (CRITICAL trovato in code
review, 2026-11): ThreatLogViewSet è un ModelViewSet standard — un
Reporter poteva creare/modificare/eliminare record di minacce reali
(falsificazione o cover delle proprie tracce), nonostante il ruolo
Reporter sia documentato come sola lettura.
"""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from targets.models import Target

from .models import ThreatLog


class ThreatLogAccessControlTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin_group, _ = Group.objects.get_or_create(name="Admin")

        self.admin = User.objects.create_user("admin", password="x")
        self.admin.groups.add(admin_group)

        self.reporter = User.objects.create_user("reporter", password="x")

        self.target = Target.objects.create(
            ip_address="192.168.178.202", hostname="app3", status="online"
        )
        self.threat = ThreatLog.objects.create(
            target=self.target, source_ip="203.0.113.10", threat_score=90, severity="critical"
        )

    def test_reporter_non_puo_eliminare_un_threat_log(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.delete(f"/api/threats/{self.threat.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ThreatLog.objects.filter(id=self.threat.id).exists())

    def test_admin_puo_eliminare_un_threat_log(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(f"/api/threats/{self.threat.id}/")
        self.assertEqual(response.status_code, 204)

    def test_reporter_puo_leggere_le_statistiche(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/threats/stats/")
        self.assertEqual(response.status_code, 200)

"""
Regressione per il fix di controllo accessi (CRITICAL trovato in code
review, 2026-11): TargetViewSet/WhitelistEntryViewSet/BlockedIPViewSet
usavano solo IsAuthenticated — un account Reporter (documentato come sola
lettura in accounts/permissions.py) poteva mutare/eliminare risorse reali.
Verifica che ora un Reporter venga rifiutato (403) sulle azioni mutanti,
mentre un Admin le esegua normalmente e la lettura resti aperta a entrambi.
"""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import BlockedIP, Target, WhitelistEntry


class RoleBasedAccessTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin_group, _ = Group.objects.get_or_create(name="Admin")

        self.admin = User.objects.create_user("admin", password="x")
        self.admin.groups.add(admin_group)

        self.reporter = User.objects.create_user("reporter", password="x")

        self.target = Target.objects.create(
            ip_address="192.168.178.200", hostname="app", status="online"
        )


class TargetAccessControlTests(RoleBasedAccessTestCase):
    def test_reporter_non_puo_eliminare_un_target(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.delete(f"/api/targets/{self.target.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Target.objects.filter(id=self.target.id).exists())

    def test_admin_puo_eliminare_un_target(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(f"/api/targets/{self.target.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Target.objects.filter(id=self.target.id).exists())

    def test_reporter_puo_leggere_la_lista_target(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/targets/")
        self.assertEqual(response.status_code, 200)


class WhitelistAccessControlTests(RoleBasedAccessTestCase):
    def _payload(self):
        return {
            "target": self.target.id,
            "ip_address": "10.0.0.5",
            "description": "test",
        }

    def test_reporter_non_puo_creare_una_entry_whitelist(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.post("/api/whitelist/", self._payload())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(WhitelistEntry.objects.filter(ip_address="10.0.0.5").exists())

    def test_admin_puo_creare_una_entry_whitelist(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/whitelist/", self._payload())
        self.assertEqual(response.status_code, 201)
        self.assertTrue(WhitelistEntry.objects.filter(ip_address="10.0.0.5").exists())

    def test_added_by_e_impostato_dal_server_e_non_spoofabile_dal_client(self):
        # Regressione MEDIUM (code review 2026-11): added_by era
        # client-settable e il frontend inviava la stringa letterale
        # 'current_user'. Ora lo imposta il server dall'utente autenticato,
        # ignorando qualunque valore inviato dal client.
        self.client.force_authenticate(user=self.admin)
        payload = {**self._payload(), "added_by": "qualcun-altro"}
        response = self.client.post("/api/whitelist/", payload)
        self.assertEqual(response.status_code, 201)
        entry = WhitelistEntry.objects.get(ip_address="10.0.0.5")
        self.assertEqual(entry.added_by, "admin")

    def test_reporter_puo_leggere_la_whitelist(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/whitelist/")
        self.assertEqual(response.status_code, 200)


class BlockedIPAccessControlTests(RoleBasedAccessTestCase):
    def setUp(self):
        super().setUp()
        self.block = BlockedIP.objects.create(
            target=self.target,
            ip_address="203.0.113.9",
            block_reason="manual",
            blocked_by="test",
        )

    def test_reporter_non_puo_bloccare_un_ip(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.post(
            "/api/blocked-ips/",
            {
                "target": self.target.id,
                "ip_address": "10.0.0.9",
                "block_reason": "manual",
                "blocked_by": "reporter",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_reporter_non_puo_sbloccare_un_ip(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.post(f"/api/blocked-ips/{self.block.id}/unblock/")
        self.assertEqual(response.status_code, 403)
        self.block.refresh_from_db()
        self.assertTrue(self.block.is_active)

    def test_admin_puo_sbloccare_un_ip(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f"/api/blocked-ips/{self.block.id}/unblock/")
        self.assertEqual(response.status_code, 200)
        self.block.refresh_from_db()
        self.assertFalse(self.block.is_active)

    def test_reporter_puo_leggere_le_statistiche(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/blocked-ips/stats/")
        self.assertEqual(response.status_code, 200)


class BlockedIPDispatchTests(RoleBasedAccessTestCase):
    """Regressione (seconda review, 2026-11): "Blocca IP" scriveva solo il
    DB, il comando block_ip non partiva mai verso l'agent."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.admin)

    def test_blocco_inviato_all_agent(self):
        from unittest import mock

        with mock.patch("agent_manager.services.dispatch_command_to_agent") as dispatch:
            response = self.client.post(
                "/api/blocked-ips/",
                {"target": self.target.id, "ip_address": "203.0.113.9", "block_reason": "manual"},
                format="json",
            )
        self.assertEqual(response.status_code, 201, response.content)
        block = BlockedIP.objects.get(ip_address="203.0.113.9")
        dispatch.assert_called_once_with(
            self.target,
            "block_ip",
            {"ip": "203.0.113.9", "direction": "INPUT"},
            meta={"blocked_ip_id": block.id},
        )

    def test_agent_offline_blocco_resta_nel_db(self):
        response = self.client.post(
            "/api/blocked-ips/",
            {"target": self.target.id, "ip_address": "203.0.113.10", "block_reason": "manual"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(BlockedIP.objects.filter(ip_address="203.0.113.10").exists())

    def test_sblocco_inviato_all_agent(self):
        from unittest import mock

        block = BlockedIP.objects.create(target=self.target, ip_address="203.0.113.11")
        with mock.patch("agent_manager.services.dispatch_command_to_agent") as dispatch:
            response = self.client.post(f"/api/blocked-ips/{block.id}/unblock/")
        self.assertEqual(response.status_code, 200, response.content)
        dispatch.assert_called_once_with(
            self.target, "unblock_ip", {"ip": "203.0.113.11", "direction": "INPUT"}, meta={}
        )

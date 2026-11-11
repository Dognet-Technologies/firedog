"""
Regressione per il fix di controllo accessi (CRITICAL trovato in code
review, 2026-11): AgentAPIKeyViewSet/AgentCommandViewSet/AgentConnectionViewSet
usavano solo IsAuthenticated, dando a un account Reporter (documentato come
sola lettura) accesso a generare/ruotare la chiave fleet-wide e a inviare
comandi arbitrari agli host reali.
"""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from targets.models import Target

from .models import AgentAPIKey, AgentCommand, AgentConnection


class RoleBasedAccessTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin_group, _ = Group.objects.get_or_create(name="Admin")

        self.admin = User.objects.create_user("admin", password="x")
        self.admin.groups.add(admin_group)

        self.reporter = User.objects.create_user("reporter", password="x")

        self.target = Target.objects.create(
            ip_address="192.168.178.201", hostname="app2", status="online"
        )


class AgentApiKeyAccessControlTests(RoleBasedAccessTestCase):
    def test_reporter_non_puo_generare_la_chiave_fleet_wide(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.post("/api/agent/api-keys/generate/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(AgentAPIKey.objects.count(), 0)

    def test_reporter_non_puo_nemmeno_leggere_la_lista_chiavi(self):
        # AgentAPIKeyViewSet è interamente Admin-only: anche la lista non
        # ha un caso d'uso per Reporter (a differenza di WhitelistEntry,
        # BlockedIP, ecc. dove la lettura resta aperta).
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/agent/api-keys/")
        self.assertEqual(response.status_code, 403)

    def test_admin_puo_generare_la_chiave(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/agent/api-keys/generate/")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(AgentAPIKey.objects.count(), 1)


class AgentCommandAccessControlTests(RoleBasedAccessTestCase):
    def test_reporter_non_puo_inviare_un_comando(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.post(
            "/api/agent/commands/",
            {"target": self.target.id, "action": "add_rule", "payload": {}},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_reporter_puo_leggere_i_comandi_pendenti(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/agent/commands/pending/")
        self.assertEqual(response.status_code, 200)


class AgentConnectionAccessControlTests(RoleBasedAccessTestCase):
    def setUp(self):
        super().setUp()
        self.connection = AgentConnection.objects.create(
            target=self.target, websocket_channel="chan1", is_online=True
        )

    def test_reporter_non_puo_forzare_la_disconnessione(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.post(f"/api/agent/connections/{self.target.id}/disconnect/")
        self.assertEqual(response.status_code, 403)
        self.connection.refresh_from_db()
        self.assertTrue(self.connection.is_online)

    def test_reporter_puo_leggere_le_connessioni_online(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/agent/connections/online/")
        self.assertEqual(response.status_code, 200)


class AgentCommandPayloadValidationTests(RoleBasedAccessTestCase):
    """
    Regressione per il fix HIGH (code review, 2026-11): `payload` era
    JSON completamente libero forwardato all'agent — qui verifica che
    create() E send_to_group() (che bypassava il serializer costruendo
    AgentCommand direttamente) rifiutino payload malformati.
    """

    def test_create_rifiuta_interface_non_valida(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/agent/commands/",
            {
                "target": self.target.id,
                "action": "add_rule",
                "payload": {"chain": "INPUT", "interface": "-F"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_create_rifiuta_chain_non_valida(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/agent/commands/",
            {"target": self.target.id, "action": "add_rule", "payload": {"chain": "DROP TABLE"}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_create_rifiuta_block_ip_senza_ip(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/agent/commands/",
            {"target": self.target.id, "action": "block_ip", "payload": {}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_create_accetta_payload_valido(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/agent/commands/",
            {
                "target": self.target.id,
                "action": "block_ip",
                "payload": {"ip": "203.0.113.5", "direction": "BOTH"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_send_to_group_rifiuta_payload_malformato(self):
        # send_to_group costruiva AgentCommand direttamente, bypassando il
        # serializer e quindi ogni validazione, prima di questo fix.
        self.target.gruppo = "web"
        self.target.status = "online"
        self.target.save()
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/agent/commands/send_to_group/",
            {"group": "web", "action": "add_rule", "payload": {"interface": "-F"}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AgentCommand.objects.count(), 0)


class RetrieveKeyErrorDoesNotLeakExceptionTextTests(RoleBasedAccessTestCase):
    """
    Regressione per il fix HIGH (code review, 2026-11): retrieve_key
    rimandava str(e) crudo nel body della risposta (e non la loggava
    nemmeno server-side) in caso di decifratura fallita.
    """

    def test_decifratura_fallita_non_espone_il_messaggio_grezzo_di_fernet(self):
        api_key = AgentAPIKey.objects.create(
            key_hash=AgentAPIKey.hash_key("x"),
            encrypted_key="non-e-un-token-fernet-valido",
            is_active=True,
            created_by="test",
        )
        self.admin.set_password("adminpass")
        self.admin.save()
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f"/api/agent/api-keys/{api_key.pk}/retrieve_key/",
            {"password": "adminpass"},
            format="json",
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"], "Impossibile decifrare la chiave")

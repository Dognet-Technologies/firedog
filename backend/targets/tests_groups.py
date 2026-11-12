"""
Regressione per il fix di controllo accessi (CRITICAL trovato in code
review, 2026-11): TargetGroupViewSet/GroupRuleTemplateViewSet usavano solo
IsAuthenticated — un Reporter poteva creare/modificare gruppi di target e
i template di regole applicati a tutti i target del gruppo.
"""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import TargetGroup


class TargetGroupAccessControlTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin_group, _ = Group.objects.get_or_create(name="Admin")

        self.admin = User.objects.create_user("admin", password="x")
        self.admin.groups.add(admin_group)

        self.reporter = User.objects.create_user("reporter", password="x")

    def test_reporter_non_puo_creare_un_gruppo(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.post("/api/groups/", {"name": "Web Servers"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(TargetGroup.objects.filter(name="Web Servers").exists())

    def test_admin_puo_creare_un_gruppo(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/groups/", {"name": "Web Servers"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(TargetGroup.objects.filter(name="Web Servers").exists())

    def test_reporter_puo_leggere_la_lista_gruppi(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/groups/")
        self.assertEqual(response.status_code, 200)


class ErrorResponseDoesNotLeakExceptionTextTests(TestCase):
    """
    Regressione per il fix HIGH (code review, 2026-11): gli handler
    `except Exception as e` di questo file rimandavano str(e) crudo nel
    body della risposta, invece di limitarsi al log server-side.
    """

    def setUp(self):
        self.client = APIClient()
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.admin = User.objects.create_user("admin", password="x")
        self.admin.groups.add(admin_group)

    def test_gruppo_non_trovato_non_espone_il_messaggio_grezzo_della_queryset(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/groups/999999/")
        self.assertEqual(response.status_code, 404)
        # Non deve contenere il messaggio grezzo di Django
        # ("TargetGroup matching query does not exist.").
        self.assertNotIn("matching query", response.json()["error"])


class GroupAddRuleValidationTests(TestCase):
    """Regressione (seconda review, 2026-11): add-rule di gruppo scriveva
    protocol/port/IP/comment nel DB e nel payload dell'agent senza validarli."""

    def setUp(self):
        from targets.models import Target

        self.client = APIClient()
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.admin = User.objects.create_user("admin", password="x")
        self.admin.groups.add(admin_group)
        self.client.force_authenticate(user=self.admin)
        self.group = TargetGroup.objects.create(name="web")
        target = Target.objects.create(ip_address="192.168.178.210", hostname="w1")
        self.group.targets.add(target)

    def _add(self, **extra):
        body = {"chain": "INPUT", "action": "ACCEPT", "protocol": "tcp", "port": 443, **extra}
        return self.client.post(f"/api/groups/{self.group.id}/add-rule/", body, format="json")

    def test_commento_con_newline_rifiutato(self):
        from rules.models import FirewallRule

        response = self._add(comment="ok\niptables -F")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(FirewallRule.objects.exists())

    def test_ip_non_valido_rifiutato(self):
        response = self._add(source_ip="999.1.1.1")
        self.assertEqual(response.status_code, 400)

    def test_porta_fuori_range_rifiutata(self):
        response = self._add(port=70000)
        self.assertEqual(response.status_code, 400)

    def test_regola_valida_creata_con_marker_ripulito(self):
        from rules.models import FirewallRule

        self.group.name = 'web"; x'
        self.group.save()
        response = self._add(comment="HTTPS")
        self.assertEqual(response.status_code, 201, response.content)
        rule = FirewallRule.objects.get()
        self.assertEqual(rule.comment, "[group:web; x] HTTPS")

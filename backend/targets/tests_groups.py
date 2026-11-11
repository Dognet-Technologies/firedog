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

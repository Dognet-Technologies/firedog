"""Autenticazione dei WebSocket dei log (firedog/consumers.py)."""

from asgiref.sync import async_to_sync
from django.contrib.auth.models import Group, User
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken

from firedog.consumers import authenticate_ws


class LogWebSocketAuthTests(TransactionTestCase):
    """Il JWT veniva stampato su stdout (journal) e bastava un utente
    qualsiasi, anche disattivato o senza ruolo, per leggere i log."""

    def setUp(self):
        reporter_group, _ = Group.objects.get_or_create(name="Reporter")
        self.reporter = User.objects.create_user("rep", password="x")
        self.reporter.groups.add(reporter_group)
        self.no_role = User.objects.create_user("nobody", password="x")

    def _scope(self, user):
        token = str(AccessToken.for_user(user))
        return {"query_string": f"token={token}".encode()}

    def test_reporter_ammesso(self):
        user = async_to_sync(authenticate_ws)(self._scope(self.reporter))
        self.assertEqual(user, self.reporter)

    def test_utente_senza_ruolo_rifiutato(self):
        self.assertIsNone(async_to_sync(authenticate_ws)(self._scope(self.no_role)))

    def test_utente_disattivato_rifiutato(self):
        scope = self._scope(self.reporter)
        self.reporter.is_active = False
        self.reporter.save()
        self.assertIsNone(async_to_sync(authenticate_ws)(scope))

    def test_token_assente_o_non_valido(self):
        self.assertIsNone(async_to_sync(authenticate_ws)({"query_string": b""}))
        self.assertIsNone(async_to_sync(authenticate_ws)({"query_string": b"token=abc"}))

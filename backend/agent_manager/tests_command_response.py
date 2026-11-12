"""Regressione (seconda review, 2026-11): command_response legato al target
dell'agent che risponde."""

from django.test import TransactionTestCase

from targets.models import Target

from .models import AgentCommand


class CommandResponseTargetScopingTests(TransactionTestCase):
    """Regressione (seconda review, 2026-11): handle_command_response
    cercava il comando solo per command_id. Qualunque socket, anche non
    accoppiato, poteva marcare come riuscito il comando di un altro target
    (remove_rule → cancellazione della regola dal DB)."""

    # TransactionTestCase: database_sync_to_async chiude la connessione,
    # incompatibile con la transazione unica di TestCase.
    def setUp(self):
        from rules.models import FirewallRule

        self.target = Target.objects.create(ip_address="192.168.178.201", hostname="app2")
        self.other = Target.objects.create(ip_address="192.168.178.202", hostname="other")
        self.rule = FirewallRule.objects.create(target=self.target, chain="INPUT", port=22)
        self.command = AgentCommand.objects.create(
            target=self.target,
            action="remove_rule",
            payload={"chain": "INPUT", "rule_num": 1, "_meta": {"rule_id": self.rule.id}},
        )

    def _respond_as(self, target):
        from asgiref.sync import async_to_sync

        from .consumers import AgentConsumer

        consumer = AgentConsumer()
        consumer.target = target
        sent = []

        async def fake_send(text_data=None, **kwargs):
            sent.append(text_data)

        consumer.send = fake_send
        async_to_sync(consumer.handle_command_response)(
            {"command_id": str(self.command.command_id), "status": "success"}
        )
        return sent

    def test_agent_di_un_altro_target_non_tocca_il_comando(self):
        from rules.models import FirewallRule

        self._respond_as(self.other)
        self.command.refresh_from_db()
        self.assertNotEqual(self.command.status, "success")
        self.assertTrue(FirewallRule.objects.filter(id=self.rule.id).exists())

    def test_socket_non_accoppiato_rifiutato(self):
        sent = self._respond_as(None)
        self.command.refresh_from_db()
        self.assertNotEqual(self.command.status, "success")
        self.assertIn("Not paired", sent[0])

    def test_agent_del_target_giusto_aggiorna_il_comando(self):
        from rules.models import FirewallRule

        self._respond_as(self.target)
        self.command.refresh_from_db()
        self.assertEqual(self.command.status, "success")
        self.assertFalse(FirewallRule.objects.filter(id=self.rule.id).exists())


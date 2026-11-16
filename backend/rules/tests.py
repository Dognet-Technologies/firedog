"""
Regressione per il fix HIGH (code review, 2026-11): il campo `interface`
di FirewallRule non aveva alcuna validazione di formato, a differenza di
port/source_ip/dest_ip/protocol/action/chain — un valore con un leading
'-' sarebbe stato letto come opzione da iptables sul lato agent (stesso
principio di validate_fw_word in dog_agent/src/firewall/mod.rs, qui
applicato anche al boundary dell'API, non solo a valle sull'agent).
"""

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from targets.models import Target

from .models import FirewallRule


class InterfaceValidatorTests(TestCase):
    def setUp(self):
        self.target = Target.objects.create(
            ip_address="192.168.178.210", hostname="rules-test", status="online"
        )

    def _rule(self, interface):
        return FirewallRule(
            target=self.target, chain="INPUT", protocol="tcp", action="ACCEPT",
            interface=interface,
        )

    def test_nomi_interfaccia_legittimi_sono_validi(self):
        for v in ["eth0", "eth0.100", "br-lan0", "wg0", "tun_0", "eth0:1"]:
            self._rule(v).full_clean()

    def test_interfaccia_vuota_e_valida(self):
        # blank=True: nessuna interfaccia specifica = tutto l'host.
        self._rule("").full_clean()

    def test_rifiuta_leading_dash_e_metacaratteri(self):
        for v in ["-F", "--flush", "eth0; rm -rf /", "eth0 lo", "$(id)"]:
            with self.assertRaises(ValidationError, msg=f"{v!r} doveva essere rifiutato"):
                self._rule(v).full_clean()


class FirewallRuleApiAccessControlTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.admin = User.objects.create_user("admin", password="x")
        self.admin.groups.add(admin_group)
        self.target = Target.objects.create(
            ip_address="192.168.178.211", hostname="rules-test2", status="online"
        )

    def test_interfaccia_non_valida_e_rifiutata_dall_api(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/rules/",
            {
                "target": self.target.id,
                "chain": "INPUT",
                "protocol": "tcp",
                "action": "ACCEPT",
                "interface": "-F",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("interface", response.json())

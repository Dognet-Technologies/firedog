"""
Test del server MCP: autenticazione API key, protocollo JSON-RPC,
tool phase-1 e semantica errori (contratto §2-§6).
"""

import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from rules.models import FirewallRule
from targets.models import Target

from .models import MCPAPIKey

MCP_URL = "/api/mcp"


def rpc(method, params=None, request_id=1):
    message = {"jsonrpc": "2.0", "method": method, "id": request_id}
    if params is not None:
        message["params"] = params
    return message


class MCPAPIKeyModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("simone", password="x")

    def test_create_for_user_returns_raw_key_once(self):
        instance, raw_key = MCPAPIKey.create_for_user(self.user, "test-key")
        self.assertTrue(raw_key.startswith("fd_"))
        self.assertEqual(len(raw_key), 3 + 48)
        # In DB solo hash SHA-256 e prefisso, mai la chiave in chiaro
        self.assertEqual(instance.key_hash, MCPAPIKey.hash_key(raw_key))
        self.assertEqual(len(instance.key_hash), 64)
        self.assertTrue(raw_key.startswith(instance.key_prefix))

    def test_expired_key_is_invalid(self):
        instance, _ = MCPAPIKey.create_for_user(
            self.user, "expired", expires_at=timezone.now() - timedelta(minutes=1)
        )
        self.assertFalse(instance.is_valid())

    def test_revoked_key_is_invalid(self):
        instance, _ = MCPAPIKey.create_for_user(self.user, "revoked")
        instance.is_active = False
        self.assertFalse(instance.is_valid())


class MCPAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("simone", password="x")
        self.key, self.raw_key = MCPAPIKey.create_for_user(self.user, "test")

    def _post(self, body, token=None):
        headers = {}
        if token:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.post(
            MCP_URL, data=json.dumps(body), content_type="application/json", **headers
        )

    def test_no_auth_returns_401(self):
        response = self._post(rpc("ping"))
        self.assertEqual(response.status_code, 401)

    def test_invalid_key_returns_401(self):
        response = self._post(rpc("ping"), token="fd_" + "x" * 48)
        self.assertEqual(response.status_code, 401)

    def test_revoked_key_returns_401(self):
        self.key.is_active = False
        self.key.save()
        response = self._post(rpc("ping"), token=self.raw_key)
        self.assertEqual(response.status_code, 401)

    def test_expired_key_returns_401(self):
        self.key.expires_at = timezone.now() - timedelta(minutes=1)
        self.key.save()
        response = self._post(rpc("ping"), token=self.raw_key)
        self.assertEqual(response.status_code, 401)

    def test_valid_key_authenticates_and_updates_last_used(self):
        self.assertIsNone(self.key.last_used_at)
        response = self._post(rpc("ping"), token=self.raw_key)
        self.assertEqual(response.status_code, 200)
        self.key.refresh_from_db()
        self.assertIsNotNone(self.key.last_used_at)


class MCPProtocolTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("simone", password="x")
        _, self.raw_key = MCPAPIKey.create_for_user(self.user, "test")

    def _post(self, body):
        return self.client.post(
            MCP_URL,
            data=json.dumps(body),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.raw_key}",
        )

    def test_initialize(self):
        response = self._post(rpc("initialize", {"protocolVersion": "2025-03-26"}))
        result = response.json()["result"]
        self.assertEqual(result["protocolVersion"], "2025-03-26")
        self.assertEqual(result["serverInfo"]["name"], "firedog-mcp")
        self.assertIn("tools", result["capabilities"])

    def test_ping(self):
        response = self._post(rpc("ping"))
        self.assertEqual(response.json()["result"], {})

    def test_tools_list(self):
        response = self._post(rpc("tools/list"))
        tools = response.json()["result"]["tools"]
        names = {t["name"] for t in tools}
        self.assertIn("list_targets", names)
        self.assertIn("get_policy_summary", names)
        for tool in tools:
            self.assertFalse(tool["inputSchema"].get("additionalProperties", True))

    def test_unknown_method_returns_32601(self):
        response = self._post(rpc("does/not/exist"))
        self.assertEqual(response.json()["error"]["code"], -32601)

    def test_unknown_tool_returns_32602(self):
        response = self._post(rpc("tools/call", {"name": "nope", "arguments": {}}))
        self.assertEqual(response.json()["error"]["code"], -32602)

    def test_unknown_argument_returns_32602(self):
        response = self._post(
            rpc("tools/call", {"name": "list_targets", "arguments": {"bogus": 1}})
        )
        self.assertEqual(response.json()["error"]["code"], -32602)

    def test_malformed_json_returns_parse_error(self):
        response = self.client.post(
            MCP_URL,
            data="{not json",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.raw_key}",
        )
        self.assertEqual(response.json()["error"]["code"], -32700)

    def test_batch_returns_one_response_per_request(self):
        response = self._post(
            [rpc("ping", request_id=1), rpc("tools/list", request_id=2)]
        )
        payload = response.json()
        self.assertIsInstance(payload, list)
        self.assertEqual({r["id"] for r in payload}, {1, 2})

    def test_batch_of_only_notifications_returns_202(self):
        response = self._post(
            [{"jsonrpc": "2.0", "method": "notifications/initialized"}]
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.content, b"")


class MCPToolTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("simone", password="x")
        _, self.raw_key = MCPAPIKey.create_for_user(self.user, "test")
        self.target = Target.objects.create(
            ip_address="192.168.178.200", hostname="app", status="online"
        )
        self.other = Target.objects.create(
            ip_address="192.168.178.198", hostname="db1", status="offline"
        )
        FirewallRule.objects.create(
            target=self.target,
            chain="INPUT",
            rule_number=1,
            protocol="tcp",
            port=22,
            action="ACCEPT",
            is_synced=True,
        )
        FirewallRule.objects.create(
            target=self.target,
            chain="INPUT",
            rule_number=2,
            protocol="tcp",
            port=8080,
            action="DROP",
            is_synced=False,
        )

    def _call(self, name, arguments=None):
        response = self.client.post(
            MCP_URL,
            data=json.dumps(
                rpc("tools/call", {"name": name, "arguments": arguments or {}})
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.raw_key}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["result"]
        self.assertFalse(result["isError"], result)
        return json.loads(result["content"][0]["text"])

    def test_list_targets_envelope(self):
        payload = self._call("list_targets")
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["limit"], 50)
        self.assertEqual(payload["offset"], 0)
        self.assertEqual(len(payload["targets"]), 2)

    def test_list_targets_filter_status(self):
        payload = self._call("list_targets", {"status": "online"})
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["targets"][0]["hostname"], "app")

    def test_list_targets_limit_hard_max(self):
        payload = self._call("list_targets", {"limit": 9999})
        self.assertEqual(payload["limit"], 200)

    def test_get_target_by_hostname(self):
        payload = self._call("get_target", {"hostname": "app"})
        self.assertEqual(payload["target"]["ip_address"], "192.168.178.200")
        self.assertEqual(payload["target"]["rules_count"], 2)

    def test_get_target_not_found(self):
        payload = self._call("get_target", {"hostname": "ghost"})
        self.assertIsNone(payload["target"])
        self.assertFalse(payload["found"])

    def test_get_target_requires_exactly_one_lookup(self):
        response = self.client.post(
            MCP_URL,
            data=json.dumps(
                rpc(
                    "tools/call",
                    {"name": "get_target", "arguments": {"id": 1, "hostname": "app"}},
                )
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.raw_key}",
        )
        self.assertEqual(response.json()["error"]["code"], -32602)

    def test_list_rules_filter_by_action(self):
        payload = self._call("list_rules", {"action": "DROP"})
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["rules"][0]["port"], 8080)

    def test_get_rule_not_found(self):
        payload = self._call("get_rule", {"id": 999999})
        self.assertIsNone(payload["rule"])
        self.assertFalse(payload["found"])

    def test_get_policy_summary(self):
        payload = self._call("get_policy_summary")
        self.assertEqual(payload["targets"]["total"], 2)
        self.assertEqual(payload["targets"]["by_status"]["online"], 1)
        self.assertEqual(payload["rules"]["total"], 2)
        self.assertEqual(payload["rules"]["unsynced"], 1)
        self.assertEqual(payload["exposed_ports"], [22])


class MCPAPIKeyEndpointTests(TestCase):
    """Gestione chiavi via /api/settings/mcp-keys/ (config utente in Settings)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("simone", password="x")
        self.other_user = User.objects.create_user("altro", password="x")
        self.client.force_authenticate(user=self.user)

    def test_create_returns_raw_key_only_once(self):
        response = self.client.post("/api/settings/mcp-keys/", {"name": "claude"})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data["key"].startswith("fd_"))
        # La lista non espone mai la chiave in chiaro
        listing = self.client.get("/api/settings/mcp-keys/").json()
        rows = listing["results"] if isinstance(listing, dict) else listing
        self.assertNotIn("key", rows[0])

    def test_user_sees_only_own_keys(self):
        MCPAPIKey.create_for_user(self.user, "mine")
        MCPAPIKey.create_for_user(self.other_user, "theirs")
        listing = self.client.get("/api/settings/mcp-keys/").json()
        rows = listing["results"] if isinstance(listing, dict) else listing
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "mine")

    def test_revoke_key(self):
        instance, raw_key = MCPAPIKey.create_for_user(self.user, "to-revoke")
        response = self.client.post(f"/api/settings/mcp-keys/{instance.id}/revoke/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_active"])
        # La chiave revocata non autentica più l'endpoint MCP
        mcp_client = APIClient()
        mcp_response = mcp_client.post(
            MCP_URL,
            data=json.dumps(rpc("ping")),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw_key}",
        )
        self.assertEqual(mcp_response.status_code, 401)

    def test_expires_at_must_be_future(self):
        response = self.client.post(
            "/api/settings/mcp-keys/",
            {
                "name": "old",
                "expires_at": (timezone.now() - timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 400)

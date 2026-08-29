"""
Test del server MCP: autenticazione API key, protocollo JSON-RPC,
tool phase-1 e semantica errori (contratto §2-§6).
"""

import json
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from rules.models import FirewallRule
from targets.models import BlockedIP, FirewallStats, NetworkFlow, Target

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
        from threats.models import ThreatLog

        self.threat = ThreatLog.objects.create(
            target=self.target,
            source_ip="203.0.113.10",
            threat_score=90,
            severity="critical",
            reasons=["port_scan"],
        )
        self.stats = FirewallStats.objects.create(
            target=self.target,
            hostname="app",
            firedog_version="1.0.0",
            input_packets=1000,
            output_packets=500,
            protocols={"tcp": {"in_packets": 900, "out_packets": 400}},
            collected_at=timezone.now(),
        )
        self.flow = NetworkFlow.objects.create(
            target=self.target,
            remote_ip="203.0.113.10",
            country_code="US",
            times_seen=5,
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

    def test_get_threat_detail(self):
        payload = self._call("get_threat", {"id": self.threat.id})
        self.assertEqual(payload["threat"]["source_ip"], "203.0.113.10")
        self.assertEqual(payload["threat"]["reasons"], ["port_scan"])

    def test_get_threat_not_found(self):
        payload = self._call("get_threat", {"id": 999999})
        self.assertIsNone(payload["threat"])
        self.assertFalse(payload["found"])

    def test_list_traffic_stats(self):
        payload = self._call("list_traffic_stats", {"target_id": self.target.id})
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["traffic_stats"][0]["input_packets"], 1000)
        self.assertEqual(payload["traffic_stats"][0]["protocols"]["tcp"]["in_packets"], 900)

    def test_list_network_flows(self):
        payload = self._call("list_network_flows", {"target_id": self.target.id})
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["network_flows"][0]["remote_ip"], "203.0.113.10")
        self.assertEqual(payload["network_flows"][0]["country_code"], "US")

    def test_list_network_flows_min_times_seen_filter(self):
        payload = self._call("list_network_flows", {"min_times_seen": 10})
        self.assertEqual(payload["total"], 0)


class MCPWriteToolTests(TestCase):
    """Tool di scrittura (phase 2): permessi Admin, create/delete_rule, block/unblock_ip."""

    def setUp(self):
        self.client = APIClient()
        self.admin_group, _ = Group.objects.get_or_create(name="Admin")

        self.admin = User.objects.create_user("admin", password="x")
        self.admin.groups.add(self.admin_group)
        _, self.admin_key = MCPAPIKey.create_for_user(self.admin, "admin-key")

        self.reporter = User.objects.create_user("reporter", password="x")
        _, self.reporter_key = MCPAPIKey.create_for_user(self.reporter, "reporter-key")

        self.target = Target.objects.create(
            ip_address="192.168.178.200", hostname="app", status="online"
        )
        self.rule = FirewallRule.objects.create(
            target=self.target,
            chain="INPUT",
            rule_number=1,
            protocol="tcp",
            port=22,
            action="ACCEPT",
            is_synced=True,
        )
        self.block = BlockedIP.objects.create(
            target=self.target,
            ip_address="203.0.113.9",
            block_reason="manual",
            blocked_by="test",
        )
        from threats.models import ThreatLog

        self.threat = ThreatLog.objects.create(
            target=self.target, source_ip="203.0.113.10", threat_score=90, severity="critical"
        )

    def _post(self, token, name, arguments=None):
        return self.client.post(
            MCP_URL,
            data=json.dumps(
                rpc("tools/call", {"name": name, "arguments": arguments or {}})
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def _call_ok(self, token, name, arguments=None):
        response = self._post(token, name, arguments)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["result"]
        self.assertFalse(result["isError"], result)
        return json.loads(result["content"][0]["text"])

    def _call_error(self, token, name, arguments=None, rpc_error=False):
        response = self._post(token, name, arguments)
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        if rpc_error:
            return payload["error"]
        result = payload["result"]
        self.assertTrue(result["isError"], result)
        return result["content"][0]["text"]

    # -- Permessi ------------------------------------------------------

    def test_create_rule_requires_admin(self):
        message = self._call_error(
            self.reporter_key,
            "create_rule",
            {"target_id": self.target.id, "chain": "INPUT", "port": 8080},
        )
        self.assertIn("Admin", message)
        self.assertEqual(FirewallRule.objects.filter(target=self.target).count(), 1)

    def test_delete_rule_requires_admin(self):
        self._call_error(self.reporter_key, "delete_rule", {"id": self.rule.id})
        self.assertTrue(FirewallRule.objects.filter(id=self.rule.id).exists())

    def test_block_ip_requires_admin(self):
        self._call_error(
            self.reporter_key,
            "block_ip",
            {"target_id": self.target.id, "ip_address": "203.0.113.50"},
        )
        self.assertFalse(
            BlockedIP.objects.filter(ip_address="203.0.113.50").exists()
        )

    def test_unblock_ip_requires_admin(self):
        self._call_error(self.reporter_key, "unblock_ip", {"id": self.block.id})
        self.block.refresh_from_db()
        self.assertTrue(self.block.is_active)

    # -- create_rule -----------------------------------------------------

    def test_create_rule_success(self):
        payload = self._call_ok(
            self.admin_key,
            "create_rule",
            {
                "target_id": self.target.id,
                "chain": "INPUT",
                "port": 8080,
                "protocol": "tcp",
                "action": "DROP",
                "comment": "test",
            },
        )
        self.assertEqual(payload["rule"]["port"], 8080)
        self.assertEqual(payload["rule"]["action"], "DROP")
        self.assertFalse(payload["dispatched_to_agent"])  # nessun agent connesso nei test
        rule = FirewallRule.objects.get(id=payload["rule"]["id"])
        self.assertTrue(rule.is_custom)
        self.assertFalse(rule.is_synced)

    def test_create_rule_unknown_target(self):
        error = self._call_error(
            self.admin_key, "create_rule", {"target_id": 999999, "chain": "INPUT"},
            rpc_error=True,
        )
        self.assertEqual(error["code"], -32602)

    def test_create_rule_invalid_chain(self):
        error = self._call_error(
            self.admin_key,
            "create_rule",
            {"target_id": self.target.id, "chain": "BOGUS"},
            rpc_error=True,
        )
        self.assertEqual(error["code"], -32602)

    def test_create_rule_invalid_port_range(self):
        error = self._call_error(
            self.admin_key,
            "create_rule",
            {"target_id": self.target.id, "chain": "INPUT", "port": 70000},
            rpc_error=True,
        )
        self.assertEqual(error["code"], -32602)

    # -- delete_rule -------------------------------------------------------

    def test_delete_rule_success(self):
        payload = self._call_ok(self.admin_key, "delete_rule", {"id": self.rule.id})
        self.assertTrue(payload["deleted"])
        self.assertTrue(payload["found"])
        self.assertFalse(FirewallRule.objects.filter(id=self.rule.id).exists())

    def test_delete_rule_not_found_is_not_an_error(self):
        payload = self._call_ok(self.admin_key, "delete_rule", {"id": 999999})
        self.assertFalse(payload["deleted"])
        self.assertFalse(payload["found"])

    def test_delete_rule_without_rule_number_warns_stale_on_device(self):
        # rule_number è null finché non arriva una riconciliazione sync_rules
        # dall'agent: senza, la rimozione non può essere dispatchata e la
        # regola può restare attiva sul device (vedi rules.services).
        fresh_rule = FirewallRule.objects.create(
            target=self.target, chain="INPUT", protocol="tcp", port=8888,
            action="DROP", is_custom=True, is_synced=False,
        )
        payload = self._call_ok(self.admin_key, "delete_rule", {"id": fresh_rule.id})
        self.assertTrue(payload["deleted"])
        self.assertFalse(payload["dispatched_to_agent"])
        self.assertIn("warning", payload)

    # -- block_ip / unblock_ip ----------------------------------------------

    def test_block_ip_creates_threat_log_for_non_manual_reason(self):
        payload = self._call_ok(
            self.admin_key,
            "block_ip",
            {
                "target_id": self.target.id,
                "ip_address": "203.0.113.50",
                "block_reason": "brute_force",
            },
        )
        self.assertEqual(payload["blocked_ip"]["ip_address"], "203.0.113.50")
        from threats.models import ThreatLog

        self.assertTrue(
            ThreatLog.objects.filter(source_ip="203.0.113.50", severity="high").exists()
        )

    def test_block_ip_manual_reason_has_no_threat_log(self):
        self._call_ok(
            self.admin_key,
            "block_ip",
            {"target_id": self.target.id, "ip_address": "203.0.113.51"},
        )
        from threats.models import ThreatLog

        self.assertFalse(
            ThreatLog.objects.filter(source_ip="203.0.113.51").exists()
        )

    def test_block_ip_duplicate_on_same_target_is_param_error(self):
        error = self._call_error(
            self.admin_key,
            "block_ip",
            {"target_id": self.target.id, "ip_address": self.block.ip_address},
            rpc_error=True,
        )
        self.assertEqual(error["code"], -32602)

    def test_unblock_ip_success(self):
        payload = self._call_ok(self.admin_key, "unblock_ip", {"id": self.block.id})
        self.assertTrue(payload["unblocked"])
        self.block.refresh_from_db()
        self.assertFalse(self.block.is_active)

    def test_unblock_ip_already_unblocked(self):
        self.block.unblock(unblocked_by="x")
        payload = self._call_ok(self.admin_key, "unblock_ip", {"id": self.block.id})
        self.assertFalse(payload["unblocked"])
        self.assertTrue(payload["found"])

    def test_unblock_ip_not_found(self):
        payload = self._call_ok(self.admin_key, "unblock_ip", {"id": 999999})
        self.assertFalse(payload["found"])

    # -- resolve_threat ------------------------------------------------------

    def test_resolve_threat_requires_admin(self):
        self._call_error(self.reporter_key, "resolve_threat", {"id": self.threat.id})
        self.threat.refresh_from_db()
        self.assertFalse(self.threat.is_resolved)

    def test_resolve_threat_success(self):
        payload = self._call_ok(self.admin_key, "resolve_threat", {"id": self.threat.id})
        self.assertTrue(payload["resolved"])
        self.threat.refresh_from_db()
        self.assertTrue(self.threat.is_resolved)
        self.assertIsNotNone(self.threat.resolved_at)

    def test_resolve_threat_already_resolved_is_idempotent(self):
        self.threat.mark_resolved()
        payload = self._call_ok(self.admin_key, "resolve_threat", {"id": self.threat.id})
        self.assertFalse(payload["resolved"])
        self.assertTrue(payload["found"])

    def test_resolve_threat_not_found(self):
        payload = self._call_ok(self.admin_key, "resolve_threat", {"id": 999999})
        self.assertFalse(payload["found"])


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

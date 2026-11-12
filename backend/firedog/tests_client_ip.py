"""Test per firedog/client_ip.py."""

from django.test import SimpleTestCase

from firedog.client_ip import client_ip_from_scope, resolve_client_ip


class ResolveClientIpTests(SimpleTestCase):
    def test_dal_proxy_locale_usa_x_real_ip(self):
        self.assertEqual(resolve_client_ip("127.0.0.1", "203.0.113.4"), "203.0.113.4")

    def test_da_un_peer_esterno_ignora_x_real_ip(self):
        self.assertEqual(resolve_client_ip("192.0.2.9", "203.0.113.4"), "192.0.2.9")

    def test_x_real_ip_non_valido_ricade_sul_peer(self):
        self.assertEqual(resolve_client_ip("127.0.0.1", "not-an-ip"), "127.0.0.1")

    def test_peer_assente(self):
        self.assertEqual(resolve_client_ip(None, None), "unknown")

    def test_scope_asgi(self):
        scope = {"client": ("127.0.0.1", 5555), "headers": [(b"x-real-ip", b"2001:db8::1")]}
        self.assertEqual(client_ip_from_scope(scope), "2001:db8::1")


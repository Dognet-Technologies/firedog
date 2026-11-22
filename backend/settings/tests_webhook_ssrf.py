"""
Regressione per il fix MEDIUM (code review, 2026-11): i webhook Slack/
Discord (URL configurabile dall'admin) venivano chiamati con
requests.post grezzo, senza alcun controllo sull'host di destinazione —
un vettore SSRF verso la rete interna o i metadata cloud (169.254.169.254)
se l'URL punta lì invece che al vero endpoint Slack/Discord.

Usa hostname letterali IP (non richiedono una vera risoluzione DNS) per
restare deterministico senza accesso di rete nell'ambiente di test.
"""

from django.test import TestCase

from .tasks import WebhookUrlError, _validate_webhook_url


class WebhookUrlValidationTests(TestCase):
    def test_rifiuta_loopback(self):
        with self.assertRaises(WebhookUrlError):
            _validate_webhook_url("https://127.0.0.1/hook")

    def test_rifiuta_metadata_cloud(self):
        with self.assertRaises(WebhookUrlError):
            _validate_webhook_url("https://169.254.169.254/latest/meta-data/")

    def test_rifiuta_ip_privato(self):
        with self.assertRaises(WebhookUrlError):
            _validate_webhook_url("https://10.0.0.5/hook")

    def test_rifiuta_http_non_https(self):
        with self.assertRaises(WebhookUrlError):
            _validate_webhook_url("http://8.8.8.8/hook")

    def test_rifiuta_userinfo_nell_url(self):
        with self.assertRaises(WebhookUrlError):
            _validate_webhook_url("https://user:pass@8.8.8.8/hook")

    def test_accetta_ip_pubblico_valido(self):
        # Non deve solllevare per un host che risolve a un IP pubblico.
        _validate_webhook_url("https://8.8.8.8/hook")


class WebhookDnsRebindingTests(TestCase):
    """Seconda review (2026-11): requests risolveva di nuovo l'host dopo la
    validazione, quindi un DNS che cambia risposta (rebinding) portava la
    richiesta su un IP interno. Ora ci si connette all'IP validato."""

    def test_connessione_all_ip_validato_senza_seconda_risoluzione(self):
        import socket
        from unittest import mock

        from requests import Response

        from . import tasks

        answers = iter(["93.184.216.34", "127.0.0.1"])

        def fake_getaddrinfo(host, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (next(answers), port))]

        sent = {}

        def fake_send(adapter, request, **kwargs):
            sent["url"] = request.url
            sent["host"] = request.headers.get("Host")
            sent["sni"] = adapter._hostname
            response = Response()
            response.status_code = 200
            return response

        with mock.patch.object(tasks.socket, "getaddrinfo", side_effect=fake_getaddrinfo), \
                mock.patch.object(tasks._PinnedHostAdapter, "send", fake_send):
            response = tasks._post_webhook("https://hooks.example.test/x", {"a": 1})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sent["url"], "https://93.184.216.34/x")
        self.assertEqual(sent["host"], "hooks.example.test")
        self.assertEqual(sent["sni"], "hooks.example.test")

    def test_rifiuta_ipv4_mappato_in_ipv6(self):
        with self.assertRaises(WebhookUrlError):
            _validate_webhook_url("https://[::ffff:127.0.0.1]/hook")

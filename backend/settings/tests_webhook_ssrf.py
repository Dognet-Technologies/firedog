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

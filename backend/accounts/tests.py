"""
Regressione per il fix HIGH (code review, 2026-11): /api/token/ non aveva
alcun rate limit, un vettore di brute-force su username+password. Ora
RateLimitedTokenObtainPairView applica ScopedRateThrottle con lo scope
"login" (10/min, vedi firedog/settings.py).

Usa una LocMemCache dedicata invece della CACHES di default (Redis) per
isolare il test dallo stato condiviso tra run e non richiedere un Redis
reale in esecuzione solo per questo test.
"""

from django.contrib.auth.models import User
from django.core.cache import caches
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "login-throttle-test",
    }
}


@override_settings(CACHES=TEST_CACHES)
class LoginRateLimitTests(TestCase):
    def setUp(self):
        caches["default"].clear()
        self.client = APIClient()
        User.objects.create_user("bob", password="correct-password")

    def test_sotto_la_soglia_non_viene_limitato(self):
        for _ in range(9):
            response = self.client.post(
                "/api/token/", {"username": "bob", "password": "wrong"}
            )
            self.assertNotEqual(response.status_code, 429)

    def test_oltre_la_soglia_viene_limitato(self):
        for _ in range(10):
            self.client.post("/api/token/", {"username": "bob", "password": "wrong"})
        response = self.client.post(
            "/api/token/", {"username": "bob", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 429)

    def test_credenziali_corrette_funzionano_sotto_la_soglia(self):
        response = self.client.post(
            "/api/token/", {"username": "bob", "password": "correct-password"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())


@override_settings(CACHES=TEST_CACHES)
class LoginThrottleClientIpTests(TestCase):
    """Regressione (seconda review, 2026-11): senza NUM_PROXIES DRF usava
    l'intero X-Forwarded-For come identita' del client, quindi cambiarlo a
    ogni tentativo azzerava il limite. Dietro nginx conta X-Real-IP, ma solo
    se la richiesta arriva dal proxy locale (firedog/client_ip.py)."""

    def setUp(self):
        caches["default"].clear()
        self.client = APIClient()
        User.objects.create_user("bob", password="correct-password")

    def _post(self, **extra):
        return self.client.post(
            "/api/token/", {"username": "bob", "password": "wrong"}, **extra
        )

    def test_x_forwarded_for_falsificato_non_aggira_il_limite(self):
        for i in range(10):
            self._post(HTTP_X_FORWARDED_FOR=f"198.51.100.{i}")
        response = self._post(HTTP_X_FORWARDED_FOR="198.51.100.200")
        self.assertEqual(response.status_code, 429)

    def test_client_diversi_dietro_nginx_hanno_limiti_separati(self):
        for _ in range(10):
            self._post(REMOTE_ADDR="127.0.0.1", HTTP_X_REAL_IP="203.0.113.10")
        self.assertEqual(
            self._post(REMOTE_ADDR="127.0.0.1", HTTP_X_REAL_IP="203.0.113.10").status_code,
            429,
        )
        self.assertNotEqual(
            self._post(REMOTE_ADDR="127.0.0.1", HTTP_X_REAL_IP="203.0.113.11").status_code,
            429,
        )

    def test_x_real_ip_ignorato_se_non_arriva_dal_proxy(self):
        for i in range(10):
            self._post(REMOTE_ADDR="192.0.2.50", HTTP_X_REAL_IP=f"203.0.113.{i}")
        response = self._post(REMOTE_ADDR="192.0.2.50", HTTP_X_REAL_IP="203.0.113.99")
        self.assertEqual(response.status_code, 429)


@override_settings(CACHES=TEST_CACHES)
class RefreshTokenRotationTests(TestCase):
    """Regressione (seconda review, 2026-11): BLACKLIST_AFTER_ROTATION era
    attivo ma l'app token_blacklist non era installata, quindi il refresh
    token appena ruotato restava riutilizzabile fino alla scadenza."""

    def setUp(self):
        caches["default"].clear()
        self.client = APIClient()
        User.objects.create_user("bob", password="correct-password")

    def test_refresh_token_ruotato_non_e_piu_valido(self):
        tokens = self.client.post(
            "/api/token/", {"username": "bob", "password": "correct-password"}
        ).json()
        first = self.client.post("/api/token/refresh/", {"refresh": tokens["refresh"]})
        self.assertEqual(first.status_code, 200)
        reused = self.client.post("/api/token/refresh/", {"refresh": tokens["refresh"]})
        self.assertEqual(reused.status_code, 401)

    def test_flush_dei_token_scaduti(self):
        from accounts.tasks import flush_expired_tokens

        flush_expired_tokens()


@override_settings(CACHES=TEST_CACHES)
class ChangePasswordThrottleTests(TestCase):
    """La verifica della password attuale nel cambio password non aveva
    limiti: brute-force con un token rubato."""

    def setUp(self):
        caches["default"].clear()
        self.client = APIClient()
        self.user = User.objects.create_user("bob", password="correct-password")
        self.client.force_authenticate(user=self.user)

    def test_oltre_la_soglia_viene_limitato(self):
        body = {"current_password": "wrong", "new_password": "N3w-Passw0rd!x", "confirm_password": "N3w-Passw0rd!x"}
        for _ in range(5):
            self.client.put("/api/settings/user/change_password/", body, format="json")
        response = self.client.put("/api/settings/user/change_password/", body, format="json")
        self.assertEqual(response.status_code, 429)

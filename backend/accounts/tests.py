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

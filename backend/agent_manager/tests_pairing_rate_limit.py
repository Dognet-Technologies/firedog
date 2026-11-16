"""
Test per il rate limit sui tentativi di pairing (CRITICAL mitigato in
code review, 2026-11) — vedi agent_manager/pairing_rate_limit.py.
"""

from django.test import TestCase

from . import pairing_rate_limit as rl


class PairingRateLimitTests(TestCase):
    def setUp(self):
        self.ip = "203.0.113.77"
        rl.reset_pairing_attempts(self.ip)

    def tearDown(self):
        rl.reset_pairing_attempts(self.ip)

    def test_non_bloccato_sotto_la_soglia(self):
        for _ in range(rl.MAX_FAILED_ATTEMPTS - 1):
            rl.record_failed_pairing_attempt(self.ip)
        self.assertFalse(rl.is_pairing_blocked(self.ip))

    def test_bloccato_al_raggiungimento_della_soglia(self):
        for _ in range(rl.MAX_FAILED_ATTEMPTS):
            rl.record_failed_pairing_attempt(self.ip)
        self.assertTrue(rl.is_pairing_blocked(self.ip))

    def test_reset_sblocca(self):
        for _ in range(rl.MAX_FAILED_ATTEMPTS):
            rl.record_failed_pairing_attempt(self.ip)
        self.assertTrue(rl.is_pairing_blocked(self.ip))
        rl.reset_pairing_attempts(self.ip)
        self.assertFalse(rl.is_pairing_blocked(self.ip))

    def test_ip_diversi_non_si_influenzano(self):
        other_ip = "203.0.113.78"
        self.addCleanup(rl.reset_pairing_attempts, other_ip)
        for _ in range(rl.MAX_FAILED_ATTEMPTS):
            rl.record_failed_pairing_attempt(self.ip)
        self.assertFalse(rl.is_pairing_blocked(other_ip))

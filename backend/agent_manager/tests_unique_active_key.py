"""
Regressione per il fix MEDIUM (code review, 2026-11): l'unicità della
chiave agent attiva era garantita solo in save() (applicativo) — una vera
race tra due generate()/activate() concorrenti poteva produrre due righe
is_active=True. Il vincolo DB è il backstop che questo test verifica
direttamente, bypassando save() per simulare cosa accadrebbe sotto race.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import AgentAPIKey


class UniqueActiveApiKeyConstraintTests(TestCase):
    def test_save_normale_lascia_una_sola_chiave_attiva(self):
        first = AgentAPIKey.objects.create(
            key_hash=AgentAPIKey.hash_key("a"), is_active=True, created_by="t"
        )
        second = AgentAPIKey.objects.create(
            key_hash=AgentAPIKey.hash_key("b"), is_active=True, created_by="t"
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)

    def test_il_vincolo_db_rifiuta_una_seconda_riga_attiva_se_si_bypassa_save(self):
        AgentAPIKey.objects.create(
            key_hash=AgentAPIKey.hash_key("a"), is_active=True, created_by="t"
        )
        # is_active=False esplicito: evita che save() disattivi la prima
        # chiave come effetto collaterale della creazione di questa.
        AgentAPIKey.objects.create(
            key_hash=AgentAPIKey.hash_key("b"), is_active=False, created_by="t"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                # .update() bypassa save(): simula esattamente cosa farebbe
                # vincere la race a un secondo generate() concorrente senza
                # il vincolo DB sotto — ora la prima chiave è ANCORA attiva.
                AgentAPIKey.objects.filter(key_hash=AgentAPIKey.hash_key("b")).update(
                    is_active=True
                )

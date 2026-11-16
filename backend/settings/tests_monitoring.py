"""Regressione (review del 2026-11-16): Impostazioni > Monitoraggio.

"Conservazione log" veniva salvata ma nessuno la leggeva; "Intervallo
scansione" e "Blocco automatico minacce" (globale) idem, e sono stati tolti.
I valori del Monitoraggio non venivano validati lato server.
"""

from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from agent_manager.models import AgentCommand
from audit.models import AuditLog
from targets.models import Alert, Target
from threats.models import ThreatLog

from .models import DatabaseCleanupLog, NotificationLog, SystemSettings
from .tasks import apply_log_retention

BULK_URL = "/api/settings/settings/bulk_update/"


class LogRetentionTests(TestCase):
    def setUp(self):
        self.target = Target.objects.create(ip_address="10.10.0.18", hostname="lab-client1")
        self.old = timezone.now() - timedelta(days=40)

    def _threat(self, ip, age=None):
        threat = ThreatLog.objects.create(target=self.target, source_ip=ip, threat_score=50, severity="medium")
        if age:
            ThreatLog.objects.filter(pk=threat.pk).update(updated_at=age)
        return threat

    def _age(self, model, obj, field):
        model.objects.filter(pk=obj.pk).update(**{field: self.old})

    def test_cancella_il_vecchio_e_tiene_il_recente(self):
        SystemSettings.set_setting("logRetention", 30, category="monitoring")
        old_threat = self._threat("203.0.113.1", age=self.old)
        new_threat = self._threat("203.0.113.2")
        old_alert = Alert.objects.create(target=self.target, severity="high", title="x", message="x")
        self._age(Alert, old_alert, "created_at")
        old_notif = NotificationLog.objects.create(
            notification_type="email", alert_type="target_offline", recipient="a@b.c", message="x"
        )
        self._age(NotificationLog, old_notif, "sent_at")
        done = AgentCommand.objects.create(target=self.target, action="sync_rules", payload={}, status="success")
        pending = AgentCommand.objects.create(target=self.target, action="sync_rules", payload={}, status="pending")
        AgentCommand.objects.filter(pk__in=[done.pk, pending.pk]).update(created_at=self.old)
        audit = AuditLog.log_action(action="update", description="vecchio")
        AuditLog.objects.filter(pk=audit.pk).update(created_at=self.old)

        deleted = apply_log_retention()

        self.assertFalse(ThreatLog.objects.filter(pk=old_threat.pk).exists())
        self.assertTrue(ThreatLog.objects.filter(pk=new_threat.pk).exists())
        self.assertFalse(Alert.objects.filter(pk=old_alert.pk).exists())
        self.assertFalse(NotificationLog.objects.filter(pk=old_notif.pk).exists())
        self.assertFalse(AgentCommand.objects.filter(pk=done.pk).exists())
        self.assertTrue(AgentCommand.objects.filter(pk=pending.pk).exists(), "comandi in corso restano")
        self.assertTrue(AuditLog.objects.filter(pk=audit.pk).exists(), "l'audit log non si tocca")
        self.assertEqual(deleted, 4)
        log = DatabaseCleanupLog.objects.latest("executed_at")
        self.assertEqual((log.retention_days, log.records_deleted, log.success), (30, 4, True))

    def test_rispetta_il_valore_impostato(self):
        SystemSettings.set_setting("logRetention", 60, category="monitoring")
        threat = self._threat("203.0.113.3", age=self.old)  # 40 giorni < 60
        apply_log_retention()
        self.assertTrue(ThreatLog.objects.filter(pk=threat.pk).exists())

    def test_valore_non_valido_usa_il_minimo_sicuro(self):
        # Un valore corrotto non deve svuotare il database: si usa il default.
        SystemSettings.set_setting("logRetention", "abc", category="monitoring")
        threat = self._threat("203.0.113.4", age=timezone.now() - timedelta(days=10))
        apply_log_retention()
        self.assertTrue(ThreatLog.objects.filter(pk=threat.pk).exists())


class MonitoringValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.admin = User.objects.create_user("admin", password="x")
        self.admin.groups.add(admin_group)
        self.client.force_authenticate(user=self.admin)

    def _save(self, **values):
        return self.client.post(
            BULK_URL, {"settings": values, "category": "monitoring"}, format="json"
        )

    def test_valori_validi_accettati(self):
        response = self._save(logRetention=15, alertNotificationMinScore=4)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(SystemSettings.get_setting("logRetention"), 15)

    def test_valori_fuori_intervallo_rifiutati(self):
        for values in (
            {"logRetention": 3},
            {"logRetention": 1000},
            {"logRetention": "trenta"},
            {"alertNotificationMinScore": 0},
            {"alertNotificationMinScore": 11},
            {"alertNotificationMinScore": True},
        ):
            with self.subTest(values=values):
                response = self._save(**values)
                self.assertEqual(response.status_code, 400, response.content)
        self.assertIsNone(SystemSettings.get_setting("logRetention"))

    def test_impostazioni_rimosse_non_si_salvano(self):
        response = self._save(scanInterval=20, enableAutoBlock=True)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIsNone(SystemSettings.get_setting("scanInterval"))

"""Regressione (review del 2026-11-16): minacce dell'agent e alert.

- handle_threat_log leggeva source_ip/threat_score/classification/attack_type,
  mentre dog_agent invia src_ip/score/threat_type (ThreatEntry in
  dog_agent/src/protocol/firedog.rs), e creava ThreatLog con campi che il
  modello non ha: ogni minaccia rilevata dall'agent andava persa.
- trigger_threat_alert e trigger_target_offline_alert non erano chiamati da
  nessuno: nessun alert email/Slack/Discord partiva mai.
- check_critical_threats filtrava su ThreatLog.timestamp, campo inesistente.
"""

from datetime import timedelta
from unittest import mock

from django.test import TransactionTestCase
from django.utils import timezone

from settings.models import SystemSettings
from targets.models import Alert, Target
from threats.models import ThreatLog

from .models import AgentConnection

DELAY = "settings.tasks.send_alert_notification.delay"


def agent_threat(ip="10.10.0.25", score=84, threat_type="BRUTE_FORCE", auto_blocked=False):
    """Una ThreatEntry come la serializza dog_agent."""
    return {
        "src_ip": ip,
        "dst_ip": None,
        "dst_port": 22,
        "protocol": "tcp",
        "threat_type": threat_type,
        "score": score,
        "description": f"Brute force ssh da {ip} — 12 tentativi (CRITICAL)",
        "timestamp": "2026-11-16T15:00:00Z",
        "auto_blocked": auto_blocked,
    }


class AgentThreatLogTests(TransactionTestCase):
    # TransactionTestCase: database_sync_to_async chiude la connessione.
    def setUp(self):
        self.target = Target.objects.create(ip_address="10.10.0.18", hostname="lab-client1")

    def _send(self, threats, target="default"):
        from asgiref.sync import async_to_sync

        from .consumers import AgentConsumer

        consumer = AgentConsumer()
        consumer.target = self.target if target == "default" else target
        sent = []

        async def fake_send(text_data=None, **kwargs):
            sent.append(text_data)

        consumer.send = fake_send
        async_to_sync(consumer.handle_threat_log)({"type": "threat_log", "threats": threats})
        return sent

    def test_minaccia_dell_agent_salvata(self):
        with mock.patch(DELAY):
            sent = self._send([agent_threat()])
        threat = ThreatLog.objects.get(target=self.target, source_ip="10.10.0.25")
        self.assertEqual(threat.threat_score, 84)
        self.assertEqual(threat.severity, "critical")
        self.assertEqual(threat.reasons, ["brute_force"])
        self.assertEqual(threat.dest_port, 22)
        self.assertEqual(threat.protocol, "tcp")
        self.assertIn('"threat_ack"', sent[0])
        self.assertIn('"count": 1', sent[0])

    def test_reinvio_aggiorna_senza_duplicare(self):
        with mock.patch(DELAY):
            self._send([agent_threat(score=70)])
            self._send([agent_threat(score=84)])
        self.assertEqual(ThreatLog.objects.filter(source_ip="10.10.0.25").count(), 1)
        self.assertEqual(ThreatLog.objects.get(source_ip="10.10.0.25").threat_score, 84)

    def test_auto_blocked_segna_bloccata(self):
        with mock.patch(DELAY):
            self._send([agent_threat(auto_blocked=True)])
        self.assertTrue(ThreatLog.objects.get(source_ip="10.10.0.25").is_blocked)

    def test_voci_non_valide_ignorate(self):
        with mock.patch(DELAY):
            sent = self._send([
                {"score": 90},
                agent_threat(ip="non-un-ip"),
                "stringa",
                agent_threat(ip="203.0.113.7"),
            ])
        self.assertEqual(list(ThreatLog.objects.values_list("source_ip", flat=True)), ["203.0.113.7"])
        self.assertIn('"count": 1', sent[0])

    def test_socket_non_accoppiato_rifiutato(self):
        sent = self._send([agent_threat()], target=None)
        self.assertIn("Not paired", sent[0])
        self.assertFalse(ThreatLog.objects.exists())

    def test_alert_alla_prima_rilevazione_non_a_ogni_reinvio(self):
        with mock.patch(DELAY) as delay:
            self._send([agent_threat(score=84)])
            self._send([agent_threat(score=90)])
        self.assertEqual(delay.call_count, 1)
        self.assertEqual(delay.call_args.kwargs["alert_type"], "threat_critical")
        self.assertIn("84/100", delay.call_args.kwargs["message"])
        self.assertEqual(Alert.objects.filter(target=self.target, severity="critical").count(), 1)

    def test_alert_quando_la_minaccia_si_aggrava(self):
        with mock.patch(DELAY) as delay:
            self._send([agent_threat(score=35)])  # medium: nessun alert
            self.assertEqual(delay.call_count, 0)
            self._send([agent_threat(score=85)])  # diventa critical
        self.assertEqual(delay.call_count, 1)

    def test_soglia_invio_su_scala_dieci(self):
        # Default 8/10 = score 80: una minaccia high (65) non parte...
        with mock.patch(DELAY) as delay:
            self._send([agent_threat(ip="198.51.100.1", score=65)])
        self.assertEqual(delay.call_count, 0)
        # ...con la soglia a 6/10 (= 60) sì, come threat_high.
        SystemSettings.set_setting("alertNotificationMinScore", 6, category="monitoring")
        with mock.patch(DELAY) as delay:
            self._send([agent_threat(ip="198.51.100.2", score=65)])
        self.assertEqual(delay.call_count, 1)
        self.assertEqual(delay.call_args.kwargs["alert_type"], "threat_high")


class AgentHealthAlertTests(TransactionTestCase):
    def setUp(self):
        self.target = Target.objects.create(ip_address="10.10.0.18", hostname="lab-client1", status="online")

    def _connection(self, last_heartbeat=None, **kwargs):
        conn = AgentConnection.objects.create(target=self.target, websocket_channel="ch", **kwargs)
        if last_heartbeat is not None:
            # auto_now_add: il valore passato a create() verrebbe ignorato.
            AgentConnection.objects.filter(pk=conn.pk).update(last_heartbeat=last_heartbeat)
        return conn

    def test_heartbeat_scaduto_manda_un_solo_alert(self):
        from .tasks import check_agent_health

        self._connection(is_online=True, last_heartbeat=timezone.now() - timedelta(minutes=5))
        with mock.patch(DELAY) as delay:
            check_agent_health()
            check_agent_health()
        self.assertEqual(delay.call_count, 1)
        self.assertEqual(delay.call_args.kwargs["alert_type"], "target_offline")
        self.assertEqual(Alert.objects.filter(target=self.target, title="Agent Offline").count(), 1)
        self.target.refresh_from_db()
        self.assertEqual(self.target.status, "offline")

    def test_disconnessione_websocket_segnalata_dopo_la_soglia(self):
        from .tasks import check_agent_health

        conn = self._connection(is_online=False, last_heartbeat=timezone.now() - timedelta(minutes=1))
        AgentConnection.objects.filter(pk=conn.pk).update(disconnected_at=timezone.now() - timedelta(seconds=30))
        with mock.patch(DELAY) as delay:
            check_agent_health()  # appena disconnesso: ancora niente (riavvio dell'agent)
            self.assertEqual(delay.call_count, 0)
            AgentConnection.objects.filter(pk=conn.pk).update(disconnected_at=timezone.now() - timedelta(minutes=5))
            check_agent_health()
            check_agent_health()
        self.assertEqual(delay.call_count, 1)

    def test_disconnessioni_vecchie_non_segnalate_al_primo_avvio(self):
        from .tasks import check_agent_health

        conn = self._connection(is_online=False)
        AgentConnection.objects.filter(pk=conn.pk).update(disconnected_at=timezone.now() - timedelta(days=30))
        with mock.patch(DELAY) as delay:
            check_agent_health()
        self.assertEqual(delay.call_count, 0)


class CriticalThreatsTaskTests(TransactionTestCase):
    def test_aggrega_le_minacce_critiche_recenti(self):
        from .tasks import check_critical_threats

        target = Target.objects.create(ip_address="10.10.0.18", hostname="lab-client1")
        for i in range(3):
            ThreatLog.objects.create(
                target=target, source_ip=f"203.0.113.{i}", threat_score=90, severity="critical"
            )
        check_critical_threats()
        self.assertTrue(
            Alert.objects.filter(target=target, title="Multiple Critical Threats Detected").exists()
        )

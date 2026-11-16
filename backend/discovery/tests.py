"""
Regressione per il fix di controllo accessi (CRITICAL trovato in code
review, 2026-11): DiscoveredHostViewSet usava solo IsAuthenticated — un
Reporter poteva avviare una vera scan di rete (start_scan) o importare
host scoperti come Target reali.
"""

import subprocess
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from .tasks import scan_network_arp


class DiscoveryAccessControlTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin_group, _ = Group.objects.get_or_create(name="Admin")

        self.admin = User.objects.create_user("admin", password="x")
        self.admin.groups.add(admin_group)

        self.reporter = User.objects.create_user("reporter", password="x")

    def test_reporter_non_puo_avviare_una_scan_di_rete(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.post("/api/discovery/start_scan/")
        self.assertEqual(response.status_code, 403)

    def test_admin_supera_il_controllo_permessi_su_start_scan(self):
        # Non asseriamo un codice di successo specifico: start_scan lancia
        # un task Celery reale (.delay()), che in un ambiente di test senza
        # broker può fallire più a valle — qui verifichiamo solo che il
        # controllo IsAdminOrReadOnly admetta l'Admin (non 403), che è
        # esattamente il gap corretto da questo fix.
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/discovery/start_scan/")
        self.assertNotEqual(response.status_code, 403)

    def test_reporter_puo_leggere_la_lista_host_scoperti(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/discovery/")
        self.assertEqual(response.status_code, 200)


class ScanNetworkArpUsesRequestedNetworkTests(TestCase):
    """
    Regressione per il fix MEDIUM (code review, 2026-11): il parametro
    `network` veniva accettato ma mai usato — ogni chiamata scansionava
    sempre la subnet locale (`arp-scan -l`), indipendentemente dalla rete
    richiesta. Su un host multi-NIC con più reti locali, ogni iterazione
    del loop in discover_network_task ripeteva la stessa scan.
    """

    @mock.patch("discovery.tasks.subprocess.run")
    def test_passa_la_rete_richiesta_non_l(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        scan_network_arp("10.20.30.0/24")

        called_args = mock_run.call_args[0][0]
        self.assertIn("10.20.30.0/24", called_args)
        self.assertNotIn("-l", called_args)

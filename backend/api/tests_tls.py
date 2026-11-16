"""CA locale (deploy/firedog-tls): download pubblico della CA e riepilogo
per le Impostazioni."""

import json
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .views_tls import looks_like_certificate

CERT = "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n"


class TlsEndpointsTests(TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.override = override_settings(TLS_PUBLIC_DIR=str(self.dir))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.client = APIClient()

    def test_ca_scaricabile_senza_login(self):
        (self.dir / "ca.crt").write_text(CERT)
        response = self.client.get("/api/tls/ca.pem")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/x-pem-file")
        self.assertEqual(response.content.decode(), CERT)

    def test_token_non_valido_non_blocca_il_download(self):
        # Un agent con una chiave vecchia non deve ricevere 401 sulla CA.
        (self.dir / "ca.crt").write_text(CERT)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer non-valido")
        self.assertEqual(self.client.get("/api/tls/ca.pem").status_code, 200)

    def test_senza_ca_gestita_404(self):
        self.assertEqual(self.client.get("/api/tls/ca.pem").status_code, 404)

    def test_un_file_con_una_chiave_non_viene_servito(self):
        (self.dir / "ca.crt").write_text(CERT + "-----BEGIN PRIVATE KEY-----\nxx\n-----END PRIVATE KEY-----\n")
        response = self.client.get("/api/tls/ca.pem")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b"PRIVATE", response.content)

    def test_riepilogo_solo_autenticati(self):
        info = {"managed": True, "profile": "testing", "ca_fingerprint_sha256": "AA:BB"}
        (self.dir / "tls-info.json").write_text(json.dumps(info))
        self.assertEqual(self.client.get("/api/settings/tls/").status_code, 401)
        self.client.force_authenticate(User.objects.create_user("u", password="x"))
        response = self.client.get("/api/settings/tls/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ca_fingerprint_sha256"], "AA:BB")

    def test_riepilogo_assente_o_corrotto(self):
        self.client.force_authenticate(User.objects.create_user("u", password="x"))
        self.assertEqual(self.client.get("/api/settings/tls/").json(), {"managed": False})
        (self.dir / "tls-info.json").write_text("{non json")
        self.assertEqual(self.client.get("/api/settings/tls/").json(), {"managed": False})


class LooksLikeCertificateTests(TestCase):
    def test_solo_un_certificato(self):
        self.assertTrue(looks_like_certificate(CERT))
        self.assertFalse(looks_like_certificate("-----BEGIN PRIVATE KEY-----\n..."))
        self.assertFalse(looks_like_certificate(CERT * 2))
        self.assertFalse(looks_like_certificate("ciao"))

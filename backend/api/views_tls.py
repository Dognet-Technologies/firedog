"""CA locale dell'installazione (creata da deploy/firedog-tls).

GET /api/tls/ca.pem (pubblico): il certificato della CA, per configurare un
  agent (ca_cert) o importarlo nel browser. È un dato pubblico; chi lo
  scarica lo conferma con l'impronta SHA-256 mostrata nelle Impostazioni.
GET /api/settings/tls/ (autenticato): profilo, impronta e scadenze, letti da
  tls-info.json che lo script riscrive a ogni emissione o rinnovo.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# Un certificato PEM sta in pochi KB: oltre è un file sbagliato.
MAX_PEM_BYTES = 64 * 1024


def _public_dir() -> Path:
    return Path(settings.TLS_PUBLIC_DIR)


def looks_like_certificate(pem: str) -> bool:
    """Un solo blocco CERTIFICATE e nient'altro (mai una chiave): se per
    errore il file contenesse altro, non lo si serve."""
    return (
        len(pem) <= MAX_PEM_BYTES
        and pem.lstrip().startswith("-----BEGIN CERTIFICATE-----")
        and pem.count("-----BEGIN ") == 1
        and "PRIVATE KEY" not in pem
    )


class TlsCaCertificateView(APIView):
    # Pubblico: un agent appena installato non ha ancora credenziali.
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        try:
            pem = (_public_dir() / "ca.crt").read_text(encoding="ascii")
        except FileNotFoundError:
            # Nessuna CA gestita (installazione HTTP o certificato fornito dall'amministratore).
            return HttpResponse(status=404)
        except (OSError, UnicodeDecodeError):
            logger.exception("Lettura della CA pubblica fallita")
            return HttpResponse(status=500)
        if not looks_like_certificate(pem):
            logger.error("ca.crt non è un certificato PEM valido: non servito")
            return HttpResponse(status=500)
        response = HttpResponse(pem, content_type="application/x-pem-file")
        response["Content-Disposition"] = 'attachment; filename="firedog-ca.pem"'
        return response


class TlsInfoView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        try:
            info = json.loads((_public_dir() / "tls-info.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            info = None
        if not isinstance(info, dict):
            return Response({"managed": False})
        return Response(info)

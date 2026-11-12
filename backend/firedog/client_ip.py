"""
IP reale del client dietro nginx.

Daphne gira dietro nginx (deploy/nginx-firedog.conf), quindi il peer TCP visto
da Django/Channels e' sempre 127.0.0.1. Prima di questo modulo:
- il rate limit del pairing WS (agent_manager/pairing_rate_limit.py) contava
  tutti i fallimenti sullo stesso IP: 20 tentativi sbagliati da chiunque
  bloccavano il pairing dell'intera flotta;
- il throttle DRF del login usava X-Forwarded-For (NUM_PROXIES non
  impostato), che il client puo' scrivere a piacere: bastava cambiarlo a ogni
  tentativo per non essere mai limitati.

Regola: X-Real-IP (che nginx sovrascrive sempre con $remote_addr) vale solo se
la connessione arriva da un proxy fidato (TRUSTED_PROXY_IPS, default
localhost). Da qualunque altro peer si usa il peer stesso.
"""

import ipaddress
from typing import Iterable, Optional

from django.conf import settings

DEFAULT_TRUSTED_PROXIES = ("127.0.0.1", "::1")


def _trusted_proxies() -> Iterable[str]:
    return getattr(settings, "TRUSTED_PROXY_IPS", DEFAULT_TRUSTED_PROXIES)


def _normalize(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def resolve_client_ip(peer: Optional[str], real_ip_header: Optional[str]) -> str:
    """IP del client dato il peer TCP e l'eventuale header X-Real-IP."""
    peer_ip = _normalize(peer)
    if peer_ip is not None and peer_ip in _trusted_proxies():
        forwarded = _normalize(real_ip_header)
        if forwarded is not None:
            return forwarded
    return peer_ip or "unknown"


def client_ip_from_scope(scope) -> str:
    """IP del client per un consumer Channels (scope ASGI)."""
    client = scope.get("client") or (None,)
    real_ip = None
    for name, value in scope.get("headers") or []:
        if name.lower() == b"x-real-ip":
            real_ip = value.decode("latin-1")
            break
    return resolve_client_ip(client[0], real_ip)


class RealIPMiddleware:
    """Riscrive REMOTE_ADDR con l'IP reale (solo da proxy fidato).

    Va con REST_FRAMEWORK["NUM_PROXIES"] = 0: il throttle DRF usa allora
    REMOTE_ADDR e ignora X-Forwarded-For.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.META["REMOTE_ADDR"] = resolve_client_ip(
            request.META.get("REMOTE_ADDR"), request.META.get("HTTP_X_REAL_IP")
        )
        return self.get_response(request)

"""
Rate limit sui tentativi di pairing via WebSocket (agent_manager/consumers.py).

Il pairing non passa per le throttle class di DRF (sono per le APIView, non
per i consumer ASGI di Channels) e l'endpoint ws/agent/ non richiede alcuna
autenticazione Django al connect — senza un limite qui, un attacker poteva
tentare in loop combinazioni ip/hostname/mac (identity hash, derivabile da
dati non segreti) contro l'unica chiave fleet-wide senza alcun freno
(CRITICAL mitigato in code review, 2026-11). Il redesign completo del
protocollo di pairing — identity hash non più derivata da dati non segreti,
un vero challenge/nonce — è un cambiamento cross-repo con dog_agent e resta
fuori scope qui: questo è un freno sull'exploitability immediata, non la
soluzione strutturale.

Usa Redis direttamente (già una dipendenza per i channel layer, vedi
CHANNEL_LAYERS in settings.py) invece della cache di Django, che di
default è LocMemCache — per-processo, non condivisa tra i worker ASGI.
"""

import logging

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 20
WINDOW_SECONDS = 300

_redis_client = None


def _get_client():
    global _redis_client
    if _redis_client is None:
        host, port = settings.CHANNEL_LAYERS["default"]["CONFIG"]["hosts"][0]
        _redis_client = redis.Redis(host=host, port=port, db=1, socket_timeout=2)
    return _redis_client


def is_pairing_blocked(source_ip: str) -> bool:
    """True se questo IP ha superato MAX_FAILED_ATTEMPTS fallimenti di
    pairing nella finestra corrente. Fail-open se Redis è irraggiungibile:
    il rate limit è una difesa aggiuntiva, non deve bloccare il pairing
    legittimo per un problema infrastrutturale separato."""
    try:
        count = _get_client().get(f"pairing_fail:{source_ip}")
        return count is not None and int(count) >= MAX_FAILED_ATTEMPTS
    except redis.RedisError:
        logger.warning("pairing_rate_limit: Redis irraggiungibile, fail-open")
        return False


def record_failed_pairing_attempt(source_ip: str) -> None:
    """Incrementa il contatore di fallimenti per questo IP; la finestra
    (WINDOW_SECONDS) viene impostata solo al primo incremento, così non si
    rinnova ad ogni singolo tentativo."""
    key = f"pairing_fail:{source_ip}"
    try:
        client = _get_client()
        count = client.incr(key)
        if count == 1:
            client.expire(key, WINDOW_SECONDS)
        if count == MAX_FAILED_ATTEMPTS:
            logger.warning(
                "pairing_rate_limit: IP %s ha raggiunto %d tentativi di pairing falliti, bloccato per %ds",
                source_ip, count, WINDOW_SECONDS,
            )
    except redis.RedisError:
        logger.warning("pairing_rate_limit: Redis irraggiungibile, fail-open")


def reset_pairing_attempts(source_ip: str) -> None:
    """Azzera il contatore dopo un pairing riuscito, così un target
    legittimo che ha avuto qualche fallimento transitorio (es. durante un
    riavvio) non resta penalizzato."""
    try:
        _get_client().delete(f"pairing_fail:{source_ip}")
    except redis.RedisError:
        pass

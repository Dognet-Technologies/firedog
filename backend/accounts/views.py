"""
View di autenticazione con rate limiting dedicato.

/api/token/ accettava tentativi di login illimitati (nessuna throttle
class configurata, vedi firedog/settings.py) — un vettore di brute-force
su username+password senza alcun freno (HIGH trovato in code review,
2026-11). ScopedRateThrottle usa `throttle_scope` + la rate registrata in
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login"], applicata per IP
client (default di DRF per le view non autenticate).
"""

from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView


class RateLimitedTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

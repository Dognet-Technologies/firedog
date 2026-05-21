"""Endpoint di aggregazione fleet-wide per la Dashboard.

Calcoli pesanti restano qui fuori dai ModelViewSet così non sporcano lo
schema CRUD dei target/firewall-stats.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from targets.models import FirewallStats

logger = logging.getLogger(__name__)


class FleetTrafficView(APIView):
    """GET /api/dashboard/fleet-traffic/?hours=24

    Restituisce per ciascuna delle ultime N ore (default 24, max 168) la
    somma fleet-wide dei delta di `input_packets` e `output_packets`.

    Algoritmo:
      1. Prende tutti i FirewallStats nelle ultime N+1 ore (servono N+1
         samples per N delta).
      2. Per ogni target, tiene l'ULTIMO sample di ogni ora (i counter sono
         cumulativi, quindi l'ultimo dà il valore "fine-ora").
      3. Per ogni target calcola il delta tra ora_i e ora_i+1; sommato per
         tutti i target dà il delta fleet dell'ora i+1.
      4. Bucket privi di dati (target offline in quell'ora) contribuiscono 0.

    Response:
        {
          "hours": 24,
          "series": [
            {"time": "12:00", "in": 12345, "out": 6789},
            ...
          ]
        }
    """

    permission_classes = [IsAuthenticated]

    MAX_HOURS = 168  # 7 giorni

    def get(self, request):
        try:
            hours = int(request.query_params.get("hours", 24))
        except ValueError:
            hours = 24
        hours = max(1, min(self.MAX_HOURS, hours))

        now = timezone.now()
        # Allineiamo "ora" al top of hour così i bucket sono prevedibili.
        now_h = now.replace(minute=0, second=0, microsecond=0)
        # Pesco N+1 ore per avere N delta utili.
        since = now_h - timedelta(hours=hours)

        stats = (
            FirewallStats.objects
            .filter(collected_at__gte=since)
            .values("target_id", "collected_at", "input_packets", "output_packets")
            .order_by("collected_at")
        )

        # Per-target: per ogni ora, tieni l'ULTIMO sample (counter cumulativi).
        per_target: Dict[int, Dict[datetime, tuple[int, int]]] = defaultdict(dict)
        for s in stats:
            bucket = s["collected_at"].replace(minute=0, second=0, microsecond=0)
            per_target[s["target_id"]][bucket] = (
                int(s["input_packets"] or 0),
                int(s["output_packets"] or 0),
            )

        # Bucket fleet-wide: somma dei delta per-target per ora.
        fleet_delta: Dict[datetime, List[int]] = defaultdict(lambda: [0, 0])
        for samples in per_target.values():
            ordered = sorted(samples.items())
            for i in range(1, len(ordered)):
                h_now, (in_now, out_now) = ordered[i]
                _, (in_prev, out_prev) = ordered[i - 1]
                # max(0, …): tollera reset dei counter (es. firewall flush).
                fleet_delta[h_now][0] += max(0, in_now - in_prev)
                fleet_delta[h_now][1] += max(0, out_now - out_prev)

        # Timeline ordinata su tutte le N ore (anche quelle vuote).
        # NB: il campo `time` (HH:00) è derivabile dal browser via toLocaleTimeString
        # sul timestamp ISO; lo lasciamo come hint comodo per chart semplici, ma
        # è formattato esplicitamente in TZ del server (Django TIME_ZONE) così
        # è prevedibile a prescindere dall'ora di sistema.
        timeline = [now_h - timedelta(hours=hours - 1 - i) for i in range(hours)]
        series = [
            {
                "time": timezone.localtime(h).strftime("%H:00"),
                "in": fleet_delta.get(h, [0, 0])[0],
                "out": fleet_delta.get(h, [0, 0])[1],
                "timestamp": h.isoformat(),
            }
            for h in timeline
        ]

        return Response({"hours": hours, "series": series})

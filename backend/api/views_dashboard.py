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

from django.db.models import Sum, Count
from targets.models import FirewallStats, NetworkFlow, BlockedIP
from threats.models import ThreatLog
from audit.models import AuditLog

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


class FleetGeoView(APIView):
    """GET /api/dashboard/geo/?target_id=<id>

    Aggrega i NetworkFlow per country_code (peer remoti pubblici visti dai
    target). Senza `target_id` ritorna fleet-wide; con `target_id` solo
    quel target.

    Response:
        {
          "total_flows": N,
          "with_country": N,
          "countries": [
            {"country_code": "US", "country_name": "United States",
             "flows": N, "times_seen": N, "pct": 42.0},
            ...
          ]
        }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            target_id = request.query_params.get("target_id")
            qs = NetworkFlow.objects.all()
            if target_id:
                qs = qs.filter(target_id=int(target_id))
        except ValueError:
            qs = NetworkFlow.objects.none()

        total_flows = qs.count()
        with_country = qs.exclude(country_code="").count()

        if with_country == 0:
            return Response({
                "total_flows": total_flows,
                "with_country": 0,
                "countries": [],
            })

        # Aggregato per country
        grouped = (
            qs.exclude(country_code="")
            .values("country_code", "country_name")
            .annotate(flows=Count("id"), times_seen=Sum("times_seen"))
            .order_by("-times_seen")[:30]
        )

        total_seen = sum(g["times_seen"] or 0 for g in grouped) or 1
        countries = [
            {
                "country_code": g["country_code"],
                "country_name": g["country_name"] or g["country_code"],
                "flows": g["flows"],
                "times_seen": g["times_seen"] or 0,
                "pct": round(((g["times_seen"] or 0) / total_seen) * 100, 1),
            }
            for g in grouped
        ]
        return Response({
            "total_flows": total_flows,
            "with_country": with_country,
            "countries": countries,
        })


class FleetActivityView(APIView):
    """GET /api/dashboard/activity/?limit=20&hours=24

    Timeline unificata fleet-wide degli ultimi N eventi da più sorgenti:
      - threat:  ThreatLog (minacce rilevate dai target)
      - block:   BlockedIP (IP bloccati da iptables sui target)
      - audit:   AuditLog (azioni utente: rule add/remove, login, install…)

    Ogni record viene normalizzato in:
        {kind, timestamp, message, severity, target_id, target_hostname, meta}

    severity ∈ {info, low, medium, high, critical}. Usato dal frontend per il
    colore del dot e l'eventuale badge.

    Ordinamento finale per timestamp DESC. `limit` cap a 50, `hours` cap a 168.
    """

    permission_classes = [IsAuthenticated]
    MAX_LIMIT = 50
    MAX_HOURS = 168

    SEVERITY_BY_REASON = {
        "ddos": "critical",
        "syn_flood": "critical",
        "malware": "critical",
        "brute_force": "high",
        "port_scan": "high",
        "threat_detected": "high",
        "manual": "medium",
        "other": "low",
    }

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", 20))
        except ValueError:
            limit = 20
        limit = max(1, min(self.MAX_LIMIT, limit))

        try:
            hours = int(request.query_params.get("hours", 24))
        except ValueError:
            hours = 24
        hours = max(1, min(self.MAX_HOURS, hours))

        since = timezone.now() - timedelta(hours=hours)
        events: List[Dict] = []

        # 1. Threats
        threat_qs = (
            ThreatLog.objects
            .filter(detected_at__gte=since)
            .select_related("target")
            .order_by("-detected_at")[:limit]
        )
        for t in threat_qs:
            proto = f" {t.protocol}" if getattr(t, "protocol", "") else ""
            port = f":{t.dest_port}" if getattr(t, "dest_port", None) else ""
            events.append({
                "kind": "threat",
                "timestamp": t.detected_at.isoformat(),
                "message": f"Threat from {t.source_ip}{proto}{port}",
                "severity": t.severity or "medium",
                "target_id": t.target_id,
                "target_hostname": getattr(t.target, "hostname", "") or getattr(t.target, "ip_address", ""),
                "meta": {
                    "source_ip": t.source_ip,
                    "score": getattr(t, "threat_score", 0),
                    "reasons": getattr(t, "reasons", []),
                },
            })

        # 2. Blocked IPs
        block_qs = (
            BlockedIP.objects
            .filter(blocked_at__gte=since, is_active=True)
            .select_related("target")
            .order_by("-blocked_at")[:limit]
        )
        for b in block_qs:
            sev = self.SEVERITY_BY_REASON.get(b.block_reason, "medium")
            reason_label = b.get_block_reason_display() if hasattr(b, "get_block_reason_display") else b.block_reason
            events.append({
                "kind": "block",
                "timestamp": b.blocked_at.isoformat(),
                "message": f"Blocked {b.ip_address} ({reason_label})",
                "severity": sev,
                "target_id": b.target_id,
                "target_hostname": getattr(b.target, "hostname", "") or getattr(b.target, "ip_address", ""),
                "meta": {
                    "ip": b.ip_address,
                    "reason": b.block_reason,
                    "blocked_by": b.blocked_by,
                },
            })

        # 3. Audit log: solo azioni operative significative (no fetch/login spam)
        relevant_actions = ("create", "update", "delete", "install", "uninstall",
                            "rule_add", "rule_remove", "approve", "error")
        audit_qs = (
            AuditLog.objects
            .filter(created_at__gte=since, action__in=relevant_actions)
            .select_related("user")
            .order_by("-created_at")[:limit]
        )
        for a in audit_qs:
            sev = "high" if not a.success else ("medium" if a.action in ("delete", "uninstall") else "info")
            user = a.user.username if a.user_id else "system"
            events.append({
                "kind": "audit",
                "timestamp": a.created_at.isoformat(),
                "message": f"{user}: {a.description or a.get_action_display()}",
                "severity": sev,
                "target_id": None,
                "target_hostname": "",
                "meta": {
                    "action": a.action,
                    "success": a.success,
                },
            })

        # Merge, sort, cap
        events.sort(key=lambda e: e["timestamp"], reverse=True)
        return Response({
            "hours": hours,
            "count": len(events[:limit]),
            "events": events[:limit],
        })

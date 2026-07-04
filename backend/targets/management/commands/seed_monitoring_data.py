"""
Management command: seed_monitoring_data
Popola il DB con dati fake realistici per testare le pagine Monitoring.
Crea un target demo + 48h di AgentHeartbeat + 48h di FirewallStats.
"""

import random
import math
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from targets.models import Target, FirewallStats
from agent_manager.models import AgentHeartbeat


class Command(BaseCommand):
    help = "Seed monitoring data: target demo + 48h heartbeat + firewall stats"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Elimina i dati demo esistenti prima di rigenerarli",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            Target.objects.filter(hostname="demo-firewall-01").delete()
            self.stdout.write("Dati demo eliminati.")

        target, created = Target.objects.get_or_create(
            hostname="demo-firewall-01",
            defaults={
                "ip_address": "192.168.100.10",
                "status": "online",
                "connection_type": "ssh",
                "description": "Target demo per test monitoring UI",
            },
        )

        if created:
            self.stdout.write(f"Target creato: {target.hostname} (id={target.id})")
        else:
            self.stdout.write(f"Target esistente: {target.hostname} (id={target.id})")

        now = timezone.now()
        interval = timedelta(minutes=30)
        points = 96  # 48h ogni 30min

        # Elimina heartbeat e stats precedenti per questo target
        AgentHeartbeat.objects.filter(target=target).delete()
        FirewallStats.objects.filter(target=target).delete()

        heartbeats = []
        stats = []

        # Baseline realistiche con rumore + picchi simulati
        cpu_base = 25.0
        mem_base = 48.0
        disk_base = 62.0
        bytes_sent_cumul = 0
        bytes_recv_cumul = 0
        packets_in_cumul = 500_000
        packets_out_cumul = 350_000

        for i in range(points):
            ts = now - interval * (points - i)

            # Simula carico diurno (ore 8-20 più alto)
            hour = (ts.hour + i % 24) % 24
            day_factor = 1.0 + 0.4 * math.sin(math.pi * (hour - 8) / 12) if 8 <= hour <= 20 else 1.0

            cpu = min(95, max(5, cpu_base * day_factor + random.gauss(0, 4)))
            mem = min(95, max(20, mem_base + random.gauss(0, 2)))
            disk = min(98, max(55, disk_base + i * 0.02))  # disco cresce lentamente

            step_sent = int(random.uniform(50_000, 300_000) * day_factor)
            step_recv = int(random.uniform(80_000, 500_000) * day_factor)
            bytes_sent_cumul += step_sent
            bytes_recv_cumul += step_recv

            step_in = int(random.uniform(5_000, 20_000) * day_factor)
            step_out = int(random.uniform(3_000, 15_000) * day_factor)
            step_fwd = int(random.uniform(1_000, 8_000) * day_factor)
            packets_in_cumul += step_in
            packets_out_cumul += step_out

            heartbeats.append(AgentHeartbeat(
                target=target,
                cpu_percent=round(cpu, 1),
                memory_percent=round(mem, 1),
                disk_percent=round(disk, 1),
                bytes_sent=bytes_sent_cumul,
                bytes_recv=bytes_recv_cumul,
                active_rules_count=random.randint(18, 24),
                blocked_ips_count=random.randint(3, 15),
            ))

            stats.append(FirewallStats(
                target=target,
                hostname="demo-firewall-01",
                firedog_version="2.1.0",
                os_version="Ubuntu 22.04.3 LTS",
                kernel_version="5.15.0-91-generic",
                uptime_seconds=int((ts - (now - timedelta(days=30))).total_seconds()),
                input_packets=packets_in_cumul,
                output_packets=packets_out_cumul,
                forward_packets=packets_in_cumul // 4,
                pcap_input_dropped_bytes=random.randint(0, 10_000),
                pcap_output_dropped_bytes=random.randint(0, 5_000),
                status="healthy",
                collected_at=ts,
            ))

        # Bulk insert — bypass auto_now_add per timestamp heartbeat
        AgentHeartbeat.objects.bulk_create(heartbeats)

        # Patch timestamp manualmente (auto_now_add non si può sovrascrivere in bulk_create)
        all_hb = list(AgentHeartbeat.objects.filter(target=target).order_by("id"))
        for idx, hb in enumerate(all_hb):
            hb.timestamp = now - interval * (points - idx)
        AgentHeartbeat.objects.bulk_update(all_hb, ["timestamp"])

        FirewallStats.objects.bulk_create(stats)

        self.stdout.write(self.style.SUCCESS(
            f"Seeding completato: {len(heartbeats)} heartbeat + {len(stats)} firewall stats "
            f"per target id={target.id}"
        ))

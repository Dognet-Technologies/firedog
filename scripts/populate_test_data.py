import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'firedog.settings')
django.setup()

from targets.models import Target, WhitelistEntry, BlockedIP
from django.utils import timezone
from datetime import timedelta

# Crea target di test
target1 = Target.objects.create(
    ip_address='192.168.1.100',
    hostname='server-01',
    description='Server Test 1',
    status='online',
    firedog_version='1.0.0'
)

target2 = Target.objects.create(
    ip_address='192.168.1.101',
    hostname='server-02',
    description='Server Test 2',
    status='online',
    firedog_version='1.0.0'
)

# Whitelist entries
WhitelistEntry.objects.create(
    target=target1,
    ip_address='192.168.1.0/24',
    description='Rete locale ufficio',
    added_by='admin',
    hit_count=15234,
    last_seen=timezone.now() - timedelta(hours=1)
)

WhitelistEntry.objects.create(
    target=target1,
    ip_address='10.0.0.50',
    description='Server monitoring',
    added_by='admin',
    hit_count=8921,
    last_seen=timezone.now() - timedelta(minutes=5)
)

# Blocked IPs
BlockedIP.objects.create(
    target=target1,
    ip_address='203.0.113.45',
    block_reason='port_scan',
    description='Port scanning detected',
    blocked_by='system',
    threat_score=85,
    packet_count=1234
)

BlockedIP.objects.create(
    target=target1,
    ip_address='198.51.100.78',
    block_reason='brute_force',
    description='SSH brute force attack',
    blocked_by='system',
    threat_score=92,
    packet_count=5678
)

print("✅ Dati di test creati con successo!")
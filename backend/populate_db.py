# ~/Repos/Progetti/firedog/backend/populate_db.py

"""
Script per popolare il database con dati di test
Uso: python manage.py shell < populate_db.py
"""

from targets.models import Target, Statistics
from threats.models import ThreatLog
from audit.models import AuditLog
from rules.models import FirewallRule
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import random

print("🚀 Popolamento database con dati di test...")

# Get o crea target
target = Target.objects.get(id=1)
print(f"✅ Target: {target.hostname} ({target.ip_address})")

# Marca come online
target.status = 'online'
target.last_seen = timezone.now()
target.save()

# Get admin user
admin_user = User.objects.filter(is_superuser=True).first()
if not admin_user:
    print("⚠️  Creando utente admin...")
    admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'admin')

# 1. STATISTICS - Ultimi 24h ogni 10 minuti
print("\n📊 Creando Statistics...")
for i in range(144):  # 24h * 6 per hour
    Statistics.objects.create(
        target=target,
        input_packets=random.randint(50000, 150000),
        output_packets=random.randint(40000, 120000),
        input_dropped=random.randint(100, 5000),
        output_dropped=random.randint(50, 2000),
        pcap_input_size=random.randint(1000000, 10000000),
        pcap_output_size=random.randint(800000, 8000000),
        collected_at=timezone.now() - timedelta(minutes=i*10)
    )
print(f"✅ Creati {Statistics.objects.count()} records Statistics")

# 2. THREATS - Minacce varie
print("\n🔥 Creando ThreatLogs...")
threat_ips = [
    '45.142.212.61', '185.220.101.34', '198.98.57.207',
    '203.0.113.42', '192.0.2.100', '198.51.100.88'
]

severities = ['low', 'medium', 'high', 'critical']
protocols = ['TCP', 'UDP', 'ICMP']

for i in range(50):
    ThreatLog.objects.create(
        target=target,
        source_ip=random.choice(threat_ips),
        dest_port=random.choice([22, 80, 443, 3389, 8080]),
        protocol=random.choice(protocols),
        threat_score=random.randint(20, 95),
        severity=random.choice(severities),
        packet_count=random.randint(100, 10000),
        reasons='Suspicious activity detected',
        description=f'Threat #{i+1} from automated scan',
        country_code=random.choice(['US', 'CN', 'RU', 'DE', 'BR']),
        is_blocked=random.choice([True, False]),
        is_resolved=random.choice([True, False]),
        detected_at=timezone.now() - timedelta(hours=random.randint(0, 48))
    )
print(f"✅ Creati {ThreatLog.objects.count()} ThreatLogs")

# 3. FIREWALL RULES
print("\n🛡️  Creando Firewall Rules...")
rules_data = [
    {'chain': 'INPUT', 'protocol': 'tcp', 'port': 22, 'action': 'ACCEPT', 'comment': 'SSH Access'},
    {'chain': 'INPUT', 'protocol': 'tcp', 'port': 80, 'action': 'ACCEPT', 'comment': 'HTTP'},
    {'chain': 'INPUT', 'protocol': 'tcp', 'port': 443, 'action': 'ACCEPT', 'comment': 'HTTPS'},
    {'chain': 'INPUT', 'protocol': 'icmp', 'port': None, 'action': 'ACCEPT', 'comment': 'ICMP'},
    {'chain': 'INPUT', 'protocol': 'tcp', 'port': 3389, 'action': 'DROP', 'comment': 'Block RDP'},
]

for rule in rules_data:
    FirewallRule.objects.create(
        target=target,
        chain=rule['chain'],
        rule_number=FirewallRule.objects.filter(target=target, chain=rule['chain']).count() + 1,
        protocol=rule['protocol'],
        port=rule['port'],
        action=rule['action'],
        comment=rule['comment'],
        is_custom=False,
        is_synced=True
    )
print(f"✅ Creati {FirewallRule.objects.count()} Firewall Rules")

# 4. AUDIT LOGS (CORRETTO)
print("\n📝 Creando Audit Logs...")
actions = ['create', 'update', 'rule_add', 'fetch', 'install', 'scan']

for i in range(30):
    AuditLog.objects.create(
        user=admin_user,
        action=random.choice(actions),
        description=f'Action {i+1}: {random.choice(actions)}',
        content_object=target if random.choice([True, False]) else None,
        old_values={'test': 'old_value'} if random.choice([True, False]) else None,
        new_values={'test': 'new_value'} if random.choice([True, False]) else None,
        ip_address='127.0.0.1',
        user_agent='Mozilla/5.0',
        success=random.choice([True, True, True, False]),  # 75% success
        created_at=timezone.now() - timedelta(hours=random.randint(0, 72))
    )
print(f"✅ Creati {AuditLog.objects.count()} Audit Logs")

print("\n✅ ✅ ✅ DATABASE POPOLATO CON SUCCESSO! ✅ ✅ ✅")
print("\n📊 Riepilogo:")
print(f"  - Targets: {Target.objects.count()}")
print(f"  - Statistics: {Statistics.objects.count()}")
print(f"  - Threats: {ThreatLog.objects.count()}")
print(f"  - Rules: {FirewallRule.objects.count()}")
print(f"  - Audit Logs: {AuditLog.objects.count()}")

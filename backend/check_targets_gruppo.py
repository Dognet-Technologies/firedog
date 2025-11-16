#!/usr/bin/env python
"""
Script per verificare i target nel database e cosa restituisce l'API
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'firedog.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from targets.models import Target
from targets.serializers import TargetSerializer, TargetListSerializer
from django.db import connection

print("=" * 70)
print("VERIFICA COMPLETA TARGET E GRUPPO")
print("=" * 70)

# 1. Verifica Database
print("\n📊 DATI NEL DATABASE:")
print("-" * 70)
targets = Target.objects.all()
for target in targets:
    print(f"\nTarget ID {target.id}:")
    print(f"  IP: {target.ip_address}")
    print(f"  Hostname: {target.hostname}")
    print(f"  Gruppo (DB): '{target.gruppo}' (tipo: {type(target.gruppo).__name__})")
    print(f"  Gruppo Custom (DB): '{target.gruppo_custom}'")
    print(f"  get_gruppo_display_name(): '{target.get_gruppo_display_name()}'")

# 2. Verifica Serializer Dettaglio
print("\n\n🔧 SERIALIZER COMPLETO (TargetSerializer):")
print("-" * 70)
for target in targets:
    serializer = TargetSerializer(target)
    data = serializer.data
    print(f"\nTarget ID {target.id} - Serialized Data:")
    print(f"  gruppo: '{data.get('gruppo')}'")
    print(f"  gruppo_custom: '{data.get('gruppo_custom')}'")
    print(f"  gruppo_display: '{data.get('gruppo_display')}'")

# 3. Verifica Serializer Lista
print("\n\n📋 SERIALIZER LISTA (TargetListSerializer):")
print("-" * 70)
list_serializer = TargetListSerializer(targets, many=True)
for item in list_serializer.data:
    print(f"\nTarget ID {item['id']}:")
    print(f"  IP: {item['ip_address']}")
    print(f"  gruppo: '{item.get('gruppo')}'")
    print(f"  gruppo_custom: '{item.get('gruppo_custom')}'")
    print(f"  gruppo_display: '{item.get('gruppo_display')}'")

# 4. Verifica Schema Database
print("\n\n🗄️  SCHEMA DATABASE:")
print("-" * 70)
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = 'targets_target'
        AND column_name IN ('gruppo', 'gruppo_custom')
        ORDER BY column_name;
    """)
    columns = cursor.fetchall()

    for col in columns:
        print(f"  {col[0]:20} | Type: {col[1]:15} | Nullable: {col[2]} | Default: {col[3]}")

# 5. Query SQL diretta
print("\n\n🔍 QUERY SQL DIRETTA:")
print("-" * 70)
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT id, ip_address, hostname, gruppo, gruppo_custom
        FROM targets_target
        ORDER BY id;
    """)
    rows = cursor.fetchall()

    for row in rows:
        print(f"  ID {row[0]}: IP={row[1]}, Host={row[2]}, Gruppo='{row[3]}', Custom='{row[4]}'")

print("\n" + "=" * 70)

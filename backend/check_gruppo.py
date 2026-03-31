#!/usr/bin/env python
"""
Script per verificare se il campo 'gruppo' esiste nella tabella Target
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firedog.settings")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from targets.models import Target
from django.db import connection


def check_gruppo_field():
    """Verifica se il campo gruppo esiste nella tabella"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'targets_target'
            AND column_name IN ('gruppo', 'gruppo_custom')
            ORDER BY column_name;
        """)
        columns = cursor.fetchall()

    print("=" * 60)
    print("VERIFICA CAMPI GRUPPO NEL DATABASE")
    print("=" * 60)

    if columns:
        print("\n✅ Campi trovati:")
        for col in columns:
            print(f"  - {col[0]:20} | Type: {col[1]:15} | Nullable: {col[2]}")

        # Verifica se ci sono dati
        total = Target.objects.count()
        with_gruppo = (
            Target.objects.exclude(gruppo__isnull=True).exclude(gruppo="").count()
        )

        print(f"\n📊 Statistiche:")
        print(f"  - Totale targets: {total}")
        print(f"  - Targets con gruppo: {with_gruppo}")
        print(f"  - Targets senza gruppo: {total - with_gruppo}")

        if total > 0:
            print(f"\n📋 Esempi di target:")
            for target in Target.objects.all()[:5]:
                gruppo_display = target.get_gruppo_display_name()
                print(f"  - {target.ip_address:15} | Gruppo: {gruppo_display}")
    else:
        print("\n❌ ERRORE: I campi 'gruppo' e 'gruppo_custom' NON esistono!")
        print("\n🔧 SOLUZIONE: Devi applicare le migrazioni:")
        print("  1. cd /home/simone/Repos/Progetti/firedog/backend")
        print("  2. source venv/bin/activate")
        print("  3. python manage.py migrate targets")
        print("  4. Riavvia il backend (daphne e celery)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        check_gruppo_field()
    except Exception as e:
        print(f"❌ Errore durante la verifica: {e}")
        import traceback

        traceback.print_exc()

"""Toglie le impostazioni di Monitoraggio che non avevano effetto (review
2026-11-16): nessuna parte del codice leggeva scanInterval né
enableAutoBlock. Il blocco automatico resta per target
(agentThreatScoring.autoBlockEnabled), l'intervallo è quello dell'agent."""

from django.db import migrations

REMOVED_KEYS = ("scanInterval", "enableAutoBlock")


def remove_settings(apps, schema_editor):
    SystemSettings = apps.get_model("settings", "SystemSettings")
    SystemSettings.objects.filter(key__in=REMOVED_KEYS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("settings", "0006_notificationconfig_smtp_skip_tls_verify"),
    ]

    operations = [
        # Irreversibile nei dati ma innocuo: i valori non erano usati.
        migrations.RunPython(remove_settings, migrations.RunPython.noop),
    ]

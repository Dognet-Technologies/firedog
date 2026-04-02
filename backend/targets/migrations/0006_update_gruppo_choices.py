# Generated migration to update gruppo choices
from django.db import migrations, models


def migrate_old_groups(apps, schema_editor):
    """
    Migra i valori dei gruppi vecchi ai nuovi valori.
    Mappa:
    - 'mail' -> 'web' (mail server come web server)
    - 'backup' -> 'storage' (backup come storage)
    - 'monitoring' -> 'web' (monitoring come web server)
    - 'application' -> 'web' (application server come web server)
    - 'queue' -> 'cache' (message queue come cache)
    - 'other' -> 'custom' (altro diventa personalizzato)
    """
    Target = apps.get_model("targets", "Target")

    # Mappatura vecchi valori -> nuovi valori
    mapping = {
        "mail": "web",
        "backup": "storage",
        "monitoring": "web",
        "application": "web",
        "queue": "cache",
        "other": "custom",
    }

    for old_value, new_value in mapping.items():
        targets = Target.objects.filter(gruppo=old_value)
        count = targets.count()
        if count > 0:
            targets.update(gruppo=new_value)
            print(f"Migrated {count} target(s) from '{old_value}' to '{new_value}'")


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - non facciamo nulla perché non è critico
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("targets", "0005_target_gruppo_target_gruppo_custom"),
    ]

    operations = [
        # Prima eseguiamo la migrazione dei dati
        migrations.RunPython(migrate_old_groups, reverse_migration),
        # Poi aggiorniamo le scelte del campo
        migrations.AlterField(
            model_name="target",
            name="gruppo",
            field=models.CharField(
                blank=True,
                choices=[
                    ("web", "Web Server"),
                    ("firewall", "Firewall"),
                    ("db", "Database"),
                    ("vpn", "VPN"),
                    ("ssh-bastions", "SSH Bastions"),
                    ("proxy", "Proxy"),
                    ("storage", "Storage"),
                    ("dns", "DNS"),
                    ("cache", "Cache"),
                    ("ldap", "LDAP"),
                    ("custom", "Personalizzato"),
                ],
                db_index=True,
                help_text="Gruppo logico del target per organizzazione e gestione regole",
                max_length=50,
                null=True,
            ),
        ),
    ]

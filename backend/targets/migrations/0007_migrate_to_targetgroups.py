# Generated migration to migrate from static gruppo field to TargetGroup
from django.db import migrations, models


def migrate_to_targetgroups(apps, schema_editor):
    """
    Migra i target dal campo statico 'gruppo' ai TargetGroup dinamici.

    1. Crea i 10 TargetGroup predefiniti se non esistono
    2. Assegna ogni target al TargetGroup corrispondente basandosi sul campo 'gruppo'
    """
    Target = apps.get_model('targets', 'Target')
    TargetGroup = apps.get_model('targets', 'TargetGroup')

    # Mappa tra campo statico 'gruppo' e nomi TargetGroup
    gruppo_to_targetgroup = {
        'web': 'Web Server',
        'firewall': 'Firewall',
        'db': 'Database',
        'vpn': 'VPN',
        'ssh-bastions': 'SSH Bastions',
        'proxy': 'Proxy',
        'storage': 'Storage',
        'dns': 'DNS',
        'cache': 'Cache',
        'ldap': 'LDAP',
    }

    # 1. Crea i TargetGroup predefiniti se non esistono
    for gruppo_key, group_name in gruppo_to_targetgroup.items():
        TargetGroup.objects.get_or_create(
            name=group_name,
            defaults={
                'description': f'Gruppo {group_name}',
                'color': '#3b82f6',
                'icon': 'server',
            }
        )

    # 2. Migra i target esistenti
    migrated_count = 0
    for target in Target.objects.all():
        if target.gruppo and target.gruppo in gruppo_to_targetgroup:
            group_name = gruppo_to_targetgroup[target.gruppo]
            try:
                group = TargetGroup.objects.get(name=group_name)
                group.targets.add(target)
                migrated_count += 1
            except TargetGroup.DoesNotExist:
                print(f"Warning: TargetGroup '{group_name}' not found for target {target.id}")
        elif target.gruppo == 'custom' and target.gruppo_custom:
            # Per i gruppi personalizzati, crea un nuovo TargetGroup
            group, created = TargetGroup.objects.get_or_create(
                name=target.gruppo_custom,
                defaults={
                    'description': f'Gruppo personalizzato: {target.gruppo_custom}',
                    'color': '#6b7280',
                    'icon': 'server',
                }
            )
            group.targets.add(target)
            migrated_count += 1

    print(f"Migrated {migrated_count} target(s) to TargetGroups")


def reverse_migration(apps, schema_editor):
    """
    Reverse: copia i TargetGroup sul campo gruppo (limitato - prende solo il primo gruppo)
    """
    Target = apps.get_model('targets', 'Target')

    targetgroup_to_gruppo = {
        'Web Server': 'web',
        'Firewall': 'firewall',
        'Database': 'db',
        'VPN': 'vpn',
        'SSH Bastions': 'ssh-bastions',
        'Proxy': 'proxy',
        'Storage': 'storage',
        'DNS': 'dns',
        'Cache': 'cache',
        'LDAP': 'ldap',
    }

    for target in Target.objects.all():
        groups = target.groups.all()
        if groups.exists():
            first_group = groups.first()
            gruppo_value = targetgroup_to_gruppo.get(first_group.name, 'custom')
            target.gruppo = gruppo_value
            if gruppo_value == 'custom':
                target.gruppo_custom = first_group.name
            target.save()


class Migration(migrations.Migration):

    dependencies = [
        ("targets", "0006_update_gruppo_choices"),
    ]

    operations = [
        # Esegui la migrazione dei dati
        migrations.RunPython(migrate_to_targetgroups, reverse_migration),

        # Rimuovi i campi gruppo e gruppo_custom
        migrations.RemoveField(
            model_name='target',
            name='gruppo',
        ),
        migrations.RemoveField(
            model_name='target',
            name='gruppo_custom',
        ),
    ]

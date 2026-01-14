# 02 - DATABASE SCHEMA

## Migration: Rimozione SSH

```python
# firedog_backend/targets/migrations/0002_remove_ssh_fields.py

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('targets', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField('target', 'ssh_port'),
        migrations.RemoveField('target', 'ssh_username'),
        migrations.RemoveField('target', 'ssh_key'),
        
        migrations.AddField(
            'target',
            'connection_type',
            field=models.CharField(max_length=10, default='agent')
        ),
        migrations.AddField(
            'target',
            'identity_hash',
            field=models.CharField(max_length=128, unique=True, null=True)
        ),
        migrations.AlterField(
            'target',
            'status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('unpaired', 'Unpaired'),
                    ('pairing', 'Pairing'),
                    ('online', 'Online'),
                    ('offline', 'Offline'),
                ]
            )
        ),
    ]
```

## Schema SQL Completo

Vedi documentazione completa nella versione originale fornita.
Tabelle principali:
- agent_manager_apikey
- agent_manager_pairingsession
- agent_manager_agentconnection
- agent_manager_agentcommand
- agent_manager_agentheartbeat


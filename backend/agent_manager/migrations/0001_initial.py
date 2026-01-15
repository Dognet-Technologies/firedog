# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('targets', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AgentAPIKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key_hash', models.CharField(help_text='SHA512 hash dell\'API key', max_length=128, unique=True)),
                ('encrypted_key', models.TextField(help_text='API key criptata (recuperabile con password admin)')),
                ('is_active', models.BooleanField(db_index=True, default=True, help_text='Solo una chiave può essere attiva')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, help_text='Scadenza chiave (null = mai)', null=True)),
                ('created_by', models.CharField(help_text='Utente che ha creato la chiave', max_length=100)),
                ('last_used_at', models.DateTimeField(blank=True, help_text='Ultimo utilizzo della chiave', null=True)),
            ],
            options={
                'verbose_name': 'Agent API Key',
                'verbose_name_plural': 'Agent API Keys',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PairingSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.UUIDField(db_index=True, unique=True)),
                ('status', models.CharField(choices=[('waiting', 'Waiting for Agent'), ('verifying_api', 'Verifying API Key'), ('verifying_hash', 'Verifying Identity Hash'), ('success', 'Pairing Success'), ('failed', 'Pairing Failed'), ('expired', 'Session Expired')], default='waiting', max_length=20)),
                ('ip_address', models.GenericIPAddressField()),
                ('hostname', models.CharField(max_length=255)),
                ('mac_address', models.CharField(max_length=17)),
                ('identity_hash', models.CharField(max_length=128)),
                ('api_key_verified', models.BooleanField(default=False)),
                ('identity_verified', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True)),
                ('target', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pairing_sessions', to='targets.target')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AgentConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('online', 'Online'), ('offline', 'Offline'), ('disconnected', 'Disconnected')], default='offline', max_length=20)),
                ('connected_at', models.DateTimeField(auto_now_add=True)),
                ('last_seen', models.DateTimeField(auto_now=True)),
                ('disconnected_at', models.DateTimeField(blank=True, null=True)),
                ('channel_name', models.CharField(blank=True, max_length=255)),
                ('agent_version', models.CharField(blank=True, max_length=50)),
                ('target', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='agent_connection', to='targets.target')),
            ],
            options={
                'ordering': ['-last_seen'],
            },
        ),
        migrations.CreateModel(
            name='AgentCommand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('command_type', models.CharField(choices=[('update_firewall', 'Update Firewall'), ('scan_threats', 'Scan Threats'), ('check_integrity', 'Check Integrity'), ('restart_services', 'Restart Services')], max_length=50)),
                ('command_data', models.JSONField(default=dict)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('executing', 'Executing'), ('completed', 'Completed'), ('failed', 'Failed'), ('timeout', 'Timeout')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('timeout_seconds', models.IntegerField(default=30)),
                ('result', models.JSONField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True)),
                ('target', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='agent_commands', to='targets.target')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AgentHeartbeat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('system_stats', models.JSONField(default=dict)),
                ('agent_version', models.CharField(blank=True, max_length=50)),
                ('target', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='heartbeats', to='targets.target')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
    ]

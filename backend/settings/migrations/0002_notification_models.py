"""
Migration per aggiungere NotificationConfig e NotificationLog

ISTRUZIONI:
1. Salvare questo file in: backend/settings/migrations/0002_notification_models.py
2. Eseguire: python manage.py migrate settings
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0001_initial'),
        ('targets', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_enabled', models.BooleanField(default=False, help_text='Abilita notifiche email')),
                ('email_recipients', models.JSONField(default=list, help_text='Lista indirizzi email destinatari')),
                ('smtp_host', models.CharField(blank=True, default='localhost', help_text='Host SMTP (es. smtp.gmail.com, localhost)', max_length=255)),
                ('smtp_port', models.IntegerField(default=587, help_text='Porta SMTP (587 per TLS, 465 per SSL, 25 per plain)', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(65535)])),
                ('smtp_user', models.CharField(blank=True, default='microcyber', help_text='Username SMTP (es. microcyber)', max_length=255)),
                ('smtp_password', models.CharField(blank=True, help_text='Password SMTP (salvata encrypted)', max_length=500)),
                ('smtp_use_tls', models.BooleanField(default=True, help_text='Usa STARTTLS per connessione sicura')),
                ('smtp_from_email', models.EmailField(blank=True, default='firedog@localhost', help_text='Email mittente per le notifiche', max_length=254)),
                ('slack_enabled', models.BooleanField(default=False, help_text='Abilita notifiche Slack')),
                ('slack_webhook_url', models.URLField(blank=True, help_text='URL webhook Slack', max_length=500)),
                ('discord_enabled', models.BooleanField(default=False, help_text='Abilita notifiche Discord')),
                ('discord_webhook_url', models.URLField(blank=True, help_text='URL webhook Discord', max_length=500)),
                ('alert_on_critical_threat', models.BooleanField(default=True, help_text='Invia alert per minacce critiche')),
                ('alert_on_high_threat', models.BooleanField(default=True, help_text='Invia alert per minacce high')),
                ('alert_on_target_offline', models.BooleanField(default=True, help_text='Invia alert quando target va offline')),
                ('target_offline_threshold_minutes', models.IntegerField(default=5, help_text='Minuti prima di considerare target offline', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(60)])),
                ('alert_on_ssh_error', models.BooleanField(default=True, help_text='Invia alert per errori SSH')),
                ('alert_on_install_success', models.BooleanField(default=False, help_text='Invia alert per installazioni completate')),
                ('alert_on_install_failed', models.BooleanField(default=True, help_text='Invia alert per installazioni fallite')),
                ('cooldown_minutes', models.IntegerField(default=60, help_text='Cooldown tra notifiche dello stesso tipo (minuti)', validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(1440)])),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notification_config_updates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Notification Configuration',
                'verbose_name_plural': 'Notification Configurations',
                'db_table': 'notification_config',
            },
        ),
        migrations.CreateModel(
            name='NotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('email', 'Email'), ('slack', 'Slack'), ('discord', 'Discord')], help_text='Tipo di notifica inviata', max_length=20)),
                ('alert_type', models.CharField(choices=[('threat_critical', 'Critical Threat'), ('threat_high', 'High Threat'), ('target_offline', 'Target Offline'), ('ssh_error', 'SSH Error'), ('install_success', 'Installation Success'), ('install_failed', 'Installation Failed')], help_text='Tipo di alert', max_length=50)),
                ('recipient', models.CharField(help_text='Destinatario (email o webhook URL)', max_length=500)),
                ('message', models.TextField(help_text='Contenuto messaggio inviato')),
                ('success', models.BooleanField(default=True, help_text='Se True, notifica inviata con successo')),
                ('error_message', models.TextField(blank=True, help_text='Messaggio di errore se success=False')),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('target', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notifications', to='targets.target')),
            ],
            options={
                'verbose_name': 'Notification Log',
                'verbose_name_plural': 'Notification Logs',
                'db_table': 'notification_logs',
                'ordering': ['-sent_at'],
            },
        ),
        migrations.AddIndex(
            model_name='notificationlog',
            index=models.Index(fields=['alert_type', 'sent_at'], name='notificatio_alert_t_idx'),
        ),
        migrations.AddIndex(
            model_name='notificationlog',
            index=models.Index(fields=['target', 'sent_at'], name='notificatio_target_idx'),
        ),
    ]

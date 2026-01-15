# Generated manually - Add encrypted_key and last_used_at fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Nessuna dipendenza dato che è la prima migration
    ]

    operations = [
        migrations.AddField(
            model_name='agentapikey',
            name='encrypted_key',
            field=models.TextField(blank=True, help_text='API key criptata (recuperabile con password admin)', null=True),
        ),
        migrations.AddField(
            model_name='agentapikey',
            name='last_used_at',
            field=models.DateTimeField(blank=True, help_text='Ultimo utilizzo della chiave', null=True),
        ),
    ]

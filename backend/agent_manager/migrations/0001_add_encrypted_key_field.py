# Migration originalmente creata manualmente per aggiungere encrypted_key e last_used_at.
# Questi campi sono già inclusi in 0001_initial, quindi questa migration è ora un no-op
# che serve solo a preservare la storia della migration nei DB esistenti.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agent_manager', '0001_initial'),
    ]

    operations = [
    ]

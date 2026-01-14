"""
Celery Configuration for FireDog
"""
import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'firedog.settings')

app = Celery('firedog')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
    'fetch-all-targets-data': {
        'task': 'targets.tasks.fetch_all_targets_data',
        'schedule': crontab(minute=f'*/10'),
    },
    'check-file-integrity': {
        'task': 'integrity.tasks.check_all_integrity',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    # Agent Manager tasks
    'check-agent-health': {
        'task': 'agent_manager.tasks.check_agent_health',
        'schedule': crontab(minute='*/2'),  # Every 2 minutes
    },
    'cleanup-old-heartbeats': {
        'task': 'agent_manager.tasks.cleanup_old_heartbeats',
        'schedule': crontab(minute='0', hour='*'),  # Every hour
    },
    'cleanup-expired-pairing-sessions': {
        'task': 'agent_manager.tasks.cleanup_expired_pairing_sessions',
        'schedule': crontab(minute='0', hour='0'),  # Daily at midnight
    },
    'timeout-stale-commands': {
        'task': 'agent_manager.tasks.timeout_stale_commands',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'check-critical-threats': {
        'task': 'agent_manager.tasks.check_critical_threats',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing"""
    print(f'Request: {self.request!r}')

"""
Settings per l'esecuzione dei test: SQLite in-memory al posto di PostgreSQL,
così la suite gira senza un DB server né permessi CREATEDB.

Uso: python manage.py test --settings=firedog.settings_test
"""

from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Nei test le password non devono costare: hasher veloce
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Celery in modalità eager: i task girano in-process
CELERY_TASK_ALWAYS_EAGER = True

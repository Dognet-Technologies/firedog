"""Task periodiche degli account."""

from celery import shared_task
from django.core.management import call_command


@shared_task(ignore_result=True)
def flush_expired_tokens():
    """Rimuove dalla blacklist JWT i token gia' scaduti (tabelle
    OutstandingToken/BlacklistedToken di simplejwt), che altrimenti
    crescono a ogni login e rinnovo."""
    call_command("flushexpiredtokens")

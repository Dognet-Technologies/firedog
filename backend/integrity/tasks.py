from celery import shared_task
from .models import FileIntegrity
import hashlib
import os


@shared_task
def check_all_integrity():
    """Controlla integrità di tutti i file monitorati"""
    files = FileIntegrity.objects.all()

    for file_integrity in files:
        if not os.path.exists(file_integrity.file_path):
            file_integrity.mark_missing()
            continue

        # Calcola hash corrente
        with open(file_integrity.file_path, "rb") as f:
            current_hash = hashlib.sha512(f.read()).hexdigest()

        if current_hash != file_integrity.sha512_hash:
            file_integrity.mark_modified(current_hash)
        else:
            file_integrity.mark_ok()

    return {"success": True, "checked": files.count()}

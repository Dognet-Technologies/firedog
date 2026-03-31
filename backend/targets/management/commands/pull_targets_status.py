"""
Django Management Command - Pull Targets Status
Scarica periodicamente i file JSON di stato dai target via SCP
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from targets.models import Target
from core.ssh_manager import SSHManager

logger = logging.getLogger("firedog.pull_status")


class Command(BaseCommand):
    help = "Scarica file JSON di stato da tutti i target attivi via SCP"

    def add_arguments(self, parser):
        parser.add_argument(
            "--target-id",
            type=int,
            help="Pull da un singolo target (opzionale)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula operazione senza scaricare file",
        )

    def handle(self, *args, **options):
        """Main entry point"""

        target_id = options.get("target_id")
        dry_run = options.get("dry_run")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - Nessun file verrà scaricato")
            )

        # Ottieni targets
        if target_id:
            targets = Target.objects.filter(id=target_id)
            if not targets.exists():
                self.stdout.write(self.style.ERROR(f"Target {target_id} non trovato"))
                return
        else:
            # Pull da tutti i target online
            targets = Target.objects.filter(status="online")

        if not targets.exists():
            self.stdout.write(self.style.WARNING("Nessun target disponibile per pull"))
            return

        self.stdout.write(f"Pull status da {targets.count()} target...\n")

        success_count = 0
        error_count = 0

        for target in targets:
            try:
                if self.pull_target_status(target, dry_run):
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                logger.exception(f"Errore pull target {target.id}: {e}")
                self.stdout.write(self.style.ERROR(f"  ✗ {target.hostname}: {str(e)}"))
                error_count += 1

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"✓ Completati: {success_count}"))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"✗ Errori: {error_count}"))
        self.stdout.write("=" * 60 + "\n")

    def pull_target_status(self, target, dry_run=False) -> bool:
        """
        Scarica file JSON di stato da un singolo target

        Args:
            target: Target instance
            dry_run: Se True, simula operazione

        Returns:
            bool: True se successo
        """

        hostname = target.hostname or f"target-{target.id}"
        remote_path = "/opt/firedog/export/status.json"

        # Directory locale per gruppo (se disponibile) o per hostname
        if hasattr(target, "group") and target.group:
            local_dir = (
                Path(settings.FIREDOG_DATA_DIR)
                / "groups"
                / target.group.name
                / hostname
            )
        else:
            local_dir = (
                Path(settings.FIREDOG_DATA_DIR) / "groups" / "default" / hostname
            )

        local_path = local_dir / "status.json"

        self.stdout.write(f"  → {hostname} ({target.ip_address})")

        if dry_run:
            self.stdout.write(
                f"    SCP: {target.ssh_user}@{target.ip_address}:{remote_path} → {local_path}"
            )
            return True

        try:
            # Crea directory locale
            local_dir.mkdir(parents=True, exist_ok=True)

            # Connessione SSH
            ssh = SSHManager(
                host=target.ip_address,
                port=target.ssh_port,
                username=target.ssh_user,
                password=None,  # Usa solo chiave pubblica
            )

            ssh.connect()

            # Verifica esistenza file remoto
            exit_code, stdout, stderr = ssh.execute_command(
                f'test -f {remote_path} && echo "EXISTS"'
            )

            if "EXISTS" not in stdout:
                self.stdout.write(
                    self.style.WARNING(f"    ⚠ File remoto non trovato: {remote_path}")
                )
                ssh.disconnect()
                return False

            # Download file via SFTP
            sftp = ssh.client.open_sftp()
            sftp.get(remote_path, str(local_path))
            sftp.close()

            ssh.disconnect()

            # Verifica file scaricato
            if not local_path.exists():
                self.stdout.write(self.style.ERROR(f"    ✗ Download fallito"))
                return False

            file_size = local_path.stat().st_size

            # Verifica JSON valido
            import json

            with open(local_path, "r") as f:
                data = json.load(f)

            timestamp = data.get("timestamp", "unknown")

            self.stdout.write(
                self.style.SUCCESS(
                    f"    ✓ Downloaded {file_size} bytes (timestamp: {timestamp})"
                )
            )

            logger.info(
                f"Pull successful for target {target.id} ({hostname}): {file_size} bytes"
            )

            return True

        except Exception as e:
            logger.exception(f"Error pulling target {target.id}: {e}")
            self.stdout.write(self.style.ERROR(f"    ✗ Errore: {str(e)}"))
            return False

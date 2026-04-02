"""
Django management command per sincronizzare i target esistenti con i TargetGroup
Uso: python manage.py sync_target_groups
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from targets.models import Target, TargetGroup


class Command(BaseCommand):
    help = "Sincronizza i target esistenti con i TargetGroup basandosi sul campo gruppo"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra cosa verrebbe fatto senza applicare modifiche",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - Nessuna modifica verrà applicata")
            )

        # Trova tutti i target con un gruppo assegnato
        targets_with_gruppo = Target.objects.exclude(gruppo__isnull=True).exclude(
            gruppo=""
        )

        self.stdout.write(
            f"Trovati {targets_with_gruppo.count()} target con un gruppo assegnato"
        )

        created_groups = {}
        synced_count = 0

        for target in targets_with_gruppo:
            # Determina il nome del gruppo
            if target.gruppo == "custom":
                group_name = target.gruppo_custom
            else:
                group_name = dict(Target.GRUPPO_CHOICES).get(
                    target.gruppo, target.gruppo
                )

            if not group_name:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipping target {target.ip_address}: gruppo vuoto"
                    )
                )
                continue

            # Verifica se il target è già nel gruppo corretto
            existing_group = target.groups.filter(name=group_name).first()
            if existing_group:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Target {target.ip_address} già nel gruppo "{group_name}"'
                    )
                )
                continue

            if not dry_run:
                with transaction.atomic():
                    # Trova o crea il TargetGroup
                    target_group, created = TargetGroup.objects.get_or_create(
                        name=group_name,
                        defaults={
                            "description": f"Auto-created from target gruppo field",
                            "color": self._get_default_color(target.gruppo),
                            "icon": self._get_default_icon(target.gruppo),
                        },
                    )

                    if created:
                        created_groups[group_name] = target_group
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  + Creato nuovo gruppo: "{group_name}"'
                            )
                        )

                    # Aggiungi il target al gruppo
                    target_group.targets.add(target)
                    synced_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Aggiunto {target.ip_address} al gruppo "{group_name}"'
                        )
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'  [DRY RUN] Aggiungerei {target.ip_address} al gruppo "{group_name}"'
                    )
                )
                synced_count += 1

        # Riepilogo
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("RIEPILOGO:"))
        self.stdout.write(self.style.SUCCESS(f"  Target sincronizzati: {synced_count}"))
        self.stdout.write(self.style.SUCCESS(f"  Gruppi creati: {len(created_groups)}"))

        if created_groups:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Gruppi creati:"))
            for group_name in created_groups.keys():
                self.stdout.write(f"  - {group_name}")

        if dry_run:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING("Esegui senza --dry-run per applicare le modifiche")
            )

    def _get_default_color(self, gruppo):
        """Restituisce un colore di default basato sul tipo di gruppo"""
        colors = {
            "web": "#10b981",  # green
            "db": "#3b82f6",  # blue
            "dns": "#8b5cf6",  # purple
            "storage": "#f59e0b",  # amber
            "mail": "#ef4444",  # red
            "backup": "#6366f1",  # indigo
            "monitoring": "#06b6d4",  # cyan
            "proxy": "#ec4899",  # pink
            "vpn": "#14b8a6",  # teal
            "firewall": "#f97316",  # orange
            "application": "#84cc16",  # lime
            "cache": "#a855f7",  # fuchsia
            "queue": "#f43f5e",  # rose
            "other": "#6b7280",  # gray
            "custom": "#3b82f6",  # blue
        }
        return colors.get(gruppo, "#3b82f6")

    def _get_default_icon(self, gruppo):
        """Restituisce un'icona di default basata sul tipo di gruppo"""
        icons = {
            "web": "globe",
            "db": "database",
            "dns": "globe",
            "storage": "hard-drive",
            "mail": "server",
            "backup": "hard-drive",
            "monitoring": "shield",
            "proxy": "layers",
            "vpn": "shield",
            "firewall": "shield",
            "application": "layers",
            "cache": "server",
            "queue": "layers",
            "other": "box",
            "custom": "server",
        }
        return icons.get(gruppo, "server")

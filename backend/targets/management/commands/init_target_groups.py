"""
Management Command per inizializzare gruppi predefiniti
CREA QUESTO FILE: backend/targets/management/commands/init_target_groups.py

Crea la struttura directory:
backend/targets/management/
backend/targets/management/__init__.py
backend/targets/management/commands/
backend/targets/management/commands/__init__.py
backend/targets/management/commands/init_target_groups.py

Uso:
    python manage.py init_target_groups
    python manage.py init_target_groups --template web
    python manage.py init_target_groups --all
"""

from django.core.management.base import BaseCommand, CommandError
from targets.group_templates import (
    create_predefined_group,
    create_all_predefined_groups,
    get_template_names,
    get_template_info,
    PREDEFINED_TEMPLATES,
)


class Command(BaseCommand):
    help = "Initialize predefined target groups with rule templates"

    def add_arguments(self, parser):
        parser.add_argument(
            "--template",
            type=str,
            help="Create specific template group (web, dns, database, storage, mail, monitoring)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Create all predefined groups",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="List available templates",
        )

    def handle(self, *args, **options):
        # List templates
        if options["list"]:
            self.stdout.write(self.style.SUCCESS("\nAvailable templates:"))
            for template_key in get_template_names():
                info = get_template_info(template_key)
                self.stdout.write(
                    f"  • {template_key:12} - {info['name']:25} "
                    f"({info['rule_count']} rules)"
                )
            self.stdout.write("")
            return

        # Create all groups
        if options["all"]:
            self.stdout.write("Creating all predefined groups...\n")
            groups = create_all_predefined_groups()

            for group in groups:
                rule_count = group.rule_templates.count()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created group: {group.name} ({rule_count} rules)"
                    )
                )

            self.stdout.write(self.style.SUCCESS(f"\n✓ Created {len(groups)} group(s)"))
            return

        # Create specific template
        if options["template"]:
            template_key = options["template"].lower()

            if template_key not in PREDEFINED_TEMPLATES:
                raise CommandError(
                    f"Template '{template_key}' not found. "
                    f"Use --list to see available templates."
                )

            try:
                group = create_predefined_group(template_key)
                rule_count = group.rule_templates.count()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created group: {group.name} ({rule_count} rules)"
                    )
                )
            except Exception as e:
                raise CommandError(f"Error creating group: {e}")

            return

        # No options provided
        self.stdout.write(
            self.style.WARNING(
                "Please specify --all to create all groups, "
                "--template <name> to create a specific group, "
                "or --list to see available templates."
            )
        )

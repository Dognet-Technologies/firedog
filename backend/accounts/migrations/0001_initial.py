"""
Initial migration for accounts app
Crea gruppi Admin e Reporter con permessi appropriati
"""

from django.db import migrations


def create_user_groups(apps, schema_editor):
    """
    Crea gruppi Admin e Reporter con permessi

    Admin:
    - Tutti i permessi (add, change, delete, view) su tutte le risorse

    Reporter:
    - Solo permessi view su tutte le risorse
    """
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    # Crea gruppo Admin
    admin_group, created = Group.objects.get_or_create(name="Admin")
    if created:
        # Admin ha TUTTI i permessi
        # Ottieni tutti i permessi disponibili
        all_permissions = Permission.objects.all()
        admin_group.permissions.set(all_permissions)
        admin_group.save()

    # Crea gruppo Reporter
    reporter_group, created = Group.objects.get_or_create(name="Reporter")
    if created:
        # Reporter ha solo permessi VIEW
        view_permissions = Permission.objects.filter(codename__startswith="view_")
        reporter_group.permissions.set(view_permissions)
        reporter_group.save()


def assign_default_users(apps, schema_editor):
    """
    Assegna gruppi agli utenti esistenti:
    - microcyber → Admin
    - user1 → Reporter (se esiste)
    """
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")

    admin_group = Group.objects.get(name="Admin")
    reporter_group = Group.objects.get(name="Reporter")

    # Assegna microcyber al gruppo Admin
    try:
        microcyber = User.objects.get(username="microcyber")
        microcyber.groups.add(admin_group)
        microcyber.is_staff = True  # Accesso admin Django
        microcyber.save()
    except User.DoesNotExist:
        pass

    # Assegna user1 al gruppo Reporter (se esiste)
    try:
        user1 = User.objects.get(username="user1")
        user1.groups.add(reporter_group)
        user1.save()
    except User.DoesNotExist:
        pass


def reverse_groups(apps, schema_editor):
    """Rimuovi gruppi creati"""
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["Admin", "Reporter"]).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "__latest__"),  # Dipende da auth per Group e Permission
    ]

    operations = [
        migrations.RunPython(create_user_groups, reverse_groups),
        migrations.RunPython(assign_default_users, migrations.RunPython.noop),
    ]

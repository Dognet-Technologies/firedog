"""
Admin configuration per Settings App
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    SystemSettings,
    SSHKey,
    DatabaseCleanupLog,
    NotificationConfig,
    NotificationLog,
)


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    """Admin per SystemSettings"""

    list_display = [
        "key",
        "category",
        "value_preview",
        "is_public",
        "updated_by",
        "updated_at",
    ]

    list_filter = [
        "category",
        "is_public",
        "updated_at",
    ]

    search_fields = [
        "key",
        "description",
    ]

    readonly_fields = [
        "updated_at",
    ]

    fieldsets = (
        ("Impostazione", {"fields": ("key", "value", "category", "description")}),
        ("Visibilità", {"fields": ("is_public",)}),
        (
            "Metadata",
            {"fields": ("updated_by", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def value_preview(self, obj):
        """Anteprima valore (troncato)"""
        value_str = str(obj.value)
        if len(value_str) > 50:
            return f"{value_str[:50]}..."
        return value_str

    value_preview.short_description = "Valore"


@admin.register(SSHKey)
class SSHKeyAdmin(admin.ModelAdmin):
    """Admin per SSHKey"""

    list_display = [
        "name",
        "key_type_badge",
        "scope_badge",
        "fingerprint_preview",
        "is_active",
        "created_at",
        "last_used_at",
    ]

    list_filter = [
        "key_type",
        "scope",
        "is_active",
        "created_at",
    ]

    search_fields = [
        "name",
        "fingerprint",
    ]

    readonly_fields = [
        "fingerprint",
        "created_at",
        "last_used_at",
        "associated_targets_count",
    ]

    fieldsets = (
        ("Identificazione", {"fields": ("name", "key_type", "key_size")}),
        (
            "Chiavi",
            {
                "fields": ("public_key", "fingerprint"),
                "description": "La chiave privata non è visualizzata per sicurezza",
            },
        ),
        ("Ambito", {"fields": ("scope", "scope_value", "associated_targets_count")}),
        (
            "Stato",
            {"fields": ("is_active", "created_at", "created_by", "last_used_at")},
        ),
    )

    def key_type_badge(self, obj):
        """Badge colorato per tipo chiave"""
        colors = {
            "ed25519": "#10b981",  # green
            "rsa": "#3b82f6",  # blue
            "ecdsa": "#f59e0b",  # amber
        }
        color = colors.get(obj.key_type, "#6b7280")
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.key_type.upper(),
        )

    key_type_badge.short_description = "Tipo"

    def scope_badge(self, obj):
        """Badge colorato per scope"""
        colors = {
            "global": "#8b5cf6",  # purple
            "group": "#06b6d4",  # cyan
            "target": "#ec4899",  # pink
        }
        color = colors.get(obj.scope, "#6b7280")

        label = obj.get_scope_display()
        if obj.scope_value:
            label = f"{label}: {obj.scope_value}"

        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            label,
        )

    scope_badge.short_description = "Ambito"

    def fingerprint_preview(self, obj):
        """Anteprima fingerprint"""
        if len(obj.fingerprint) > 30:
            return f"{obj.fingerprint[:30]}..."
        return obj.fingerprint

    fingerprint_preview.short_description = "Fingerprint"

    def has_add_permission(self, request):
        """Disabilita aggiunta diretta (usa API)"""
        return False


@admin.register(DatabaseCleanupLog)
class DatabaseCleanupLogAdmin(admin.ModelAdmin):
    """Admin per DatabaseCleanupLog"""

    list_display = [
        "cleanup_type",
        "records_deleted",
        "retention_days",
        "success_badge",
        "executed_by",
        "executed_at",
    ]

    list_filter = [
        "cleanup_type",
        "success",
        "executed_at",
    ]

    search_fields = [
        "executed_by__username",
        "error_message",
    ]

    readonly_fields = [
        "cleanup_type",
        "records_deleted",
        "retention_days",
        "executed_at",
        "executed_by",
        "success",
        "error_message",
    ]

    def success_badge(self, obj):
        """Badge per stato operazione"""
        if obj.success:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 3px 8px; '
                'border-radius: 4px; font-size: 11px; font-weight: 600;">SUCCESS</span>'
            )
        else:
            return format_html(
                '<span style="background: #ef4444; color: white; padding: 3px 8px; '
                'border-radius: 4px; font-size: 11px; font-weight: 600;">ERROR</span>'
            )

    success_badge.short_description = "Stato"

    def has_add_permission(self, request):
        """Disabilita aggiunta manuale"""
        return False

    def has_change_permission(self, request, obj=None):
        """Disabilita modifica"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Consenti solo eliminazione"""
        return True


@admin.register(NotificationConfig)
class NotificationConfigAdmin(admin.ModelAdmin):
    """Admin per NotificationConfig (singleton)"""

    list_display = [
        "id",
        "email_status",
        "slack_status",
        "discord_status",
        "updated_at",
        "updated_by",
    ]

    readonly_fields = [
        "updated_at",
        "smtp_password_masked",
    ]

    fieldsets = (
        (
            "Email Configuration",
            {
                "fields": (
                    "email_enabled",
                    "email_recipients",
                    "smtp_host",
                    "smtp_port",
                    "smtp_user",
                    "smtp_password_masked",
                    "smtp_use_tls",
                    "smtp_from_email",
                )
            },
        ),
        (
            "Slack Configuration",
            {
                "fields": ("slack_enabled", "slack_webhook_url"),
                "classes": ("collapse",),
            },
        ),
        (
            "Discord Configuration",
            {
                "fields": ("discord_enabled", "discord_webhook_url"),
                "classes": ("collapse",),
            },
        ),
        (
            "Alert Triggers",
            {
                "fields": (
                    "alert_on_critical_threat",
                    "alert_on_high_threat",
                    "alert_on_target_offline",
                    "target_offline_threshold_minutes",
                    "alert_on_ssh_error",
                    "alert_on_install_success",
                    "alert_on_install_failed",
                    "cooldown_minutes",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {"fields": ("updated_at", "updated_by"), "classes": ("collapse",)},
        ),
    )

    def email_status(self, obj):
        """Badge stato email"""
        if obj.email_enabled:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 3px 8px; '
                'border-radius: 4px; font-size: 11px; font-weight: 600;">ENABLED</span>'
            )
        return format_html(
            '<span style="background: #6b7280; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 600;">DISABLED</span>'
        )

    email_status.short_description = "Email"

    def slack_status(self, obj):
        """Badge stato Slack"""
        if obj.slack_enabled:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 3px 8px; '
                'border-radius: 4px; font-size: 11px; font-weight: 600;">ENABLED</span>'
            )
        return format_html(
            '<span style="background: #6b7280; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 600;">DISABLED</span>'
        )

    slack_status.short_description = "Slack"

    def discord_status(self, obj):
        """Badge stato Discord"""
        if obj.discord_enabled:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 3px 8px; '
                'border-radius: 4px; font-size: 11px; font-weight: 600;">ENABLED</span>'
            )
        return format_html(
            '<span style="background: #6b7280; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 600;">DISABLED</span>'
        )

    discord_status.short_description = "Discord"

    def smtp_password_masked(self, obj):
        """Maschera password SMTP"""
        if obj.smtp_password:
            return "••••••••••"
        return "(not set)"

    smtp_password_masked.short_description = "SMTP Password"

    def has_add_permission(self, request):
        """Disabilita creazione (singleton)"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disabilita eliminazione (singleton)"""
        return False


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """Admin per NotificationLog"""

    list_display = [
        "sent_at",
        "notification_type_badge",
        "alert_type",
        "target",
        "recipient_preview",
        "success_badge",
    ]

    list_filter = [
        "notification_type",
        "alert_type",
        "success",
        "sent_at",
    ]

    search_fields = [
        "recipient",
        "message",
        "error_message",
        "target__hostname",
    ]

    readonly_fields = [
        "notification_type",
        "alert_type",
        "target",
        "recipient",
        "message",
        "success",
        "error_message",
        "sent_at",
    ]

    date_hierarchy = "sent_at"

    def notification_type_badge(self, obj):
        """Badge colorato per tipo notifica"""
        colors = {
            "email": "#3b82f6",  # blue
            "slack": "#8b5cf6",  # purple
            "discord": "#ec4899",  # pink
        }
        color = colors.get(obj.notification_type, "#6b7280")

        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.get_notification_type_display().upper(),
        )

    notification_type_badge.short_description = "Type"

    def recipient_preview(self, obj):
        """Anteprima destinatario"""
        if len(obj.recipient) > 50:
            return f"{obj.recipient[:50]}..."
        return obj.recipient

    recipient_preview.short_description = "Recipient"

    def success_badge(self, obj):
        """Badge stato invio"""
        if obj.success:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 3px 8px; '
                'border-radius: 4px; font-size: 11px; font-weight: 600;">✓ SUCCESS</span>'
            )
        return format_html(
            '<span style="background: #ef4444; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 600;">✗ FAILED</span>'
        )

    success_badge.short_description = "Status"

    def has_add_permission(self, request):
        """Disabilita creazione manuale"""
        return False

    def has_change_permission(self, request, obj=None):
        """Disabilita modifica"""
        return False

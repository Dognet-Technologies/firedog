"""
Models per l'app Audit
Audit logging per tutte le operazioni critiche
"""
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class AuditLog(models.Model):
    """
    Log di audit per tutte le operazioni critiche del sistema
    """
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('install', 'Install'),
        ('uninstall', 'Uninstall'),
        ('rule_add', 'Rule Add'),
        ('rule_remove', 'Rule Remove'),
        ('fetch', 'Fetch Data'),
        ('scan', 'Network Scan'),
        ('approve', 'Approve Change'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('error', 'Error'),
    ]

    # Utente che ha eseguito l'azione
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
        help_text="Utente che ha eseguito l'azione"
    )

    # Azione eseguita
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        db_index=True,
        help_text="Tipo di azione eseguita"
    )

    # Oggetto target (generic foreign key)
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True
    )
    content_object = GenericForeignKey('content_type', 'object_id')

    # Dettagli operazione
    description = models.TextField(
        help_text="Descrizione dell'operazione"
    )

    # Dati prima/dopo (per tracking modifiche)
    old_values = models.JSONField(
        null=True,
        blank=True,
        help_text="Valori prima della modifica"
    )

    new_values = models.JSONField(
        null=True,
        blank=True,
        help_text="Valori dopo la modifica"
    )

    # Metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP da cui è stata eseguita l'azione"
    )

    user_agent = models.CharField(
        max_length=512,
        blank=True,
        help_text="User agent del client"
    )

    # Risultato
    success = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Indica se l'operazione è riuscita"
    )

    error_message = models.TextField(
        blank=True,
        help_text="Messaggio di errore se l'operazione è fallita"
    )

    # Timestamp
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Quando l'azione è stata eseguita"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action', 'success']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def __str__(self):
        user_info = self.user.username if self.user else 'System'
        status = "✓" if self.success else "✗"
        return f"{status} {user_info} - {self.action} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

    @classmethod
    def log_action(cls, action, description, user=None, content_object=None,
                   old_values=None, new_values=None, ip_address=None,
                   user_agent=None, success=True, error_message=''):
        """
        Helper method per creare un audit log
        """
        log_data = {
            'action': action,
            'description': description,
            'user': user,
            'old_values': old_values,
            'new_values': new_values,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'success': success,
            'error_message': error_message,
        }

        if content_object:
            log_data['content_object'] = content_object

        return cls.objects.create(**log_data)

    @property
    def action_display(self):
        """Descrizione leggibile dell'azione"""
        return dict(self.ACTION_CHOICES).get(self.action, self.action)

    @property
    def has_changes(self):
        """Verifica se ci sono modifiche tracciate"""
        return self.old_values or self.new_values

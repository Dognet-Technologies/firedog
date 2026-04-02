"""
Models per l'app Dashboards
Gestione delle dashboard personalizzabili
"""

from django.db import models
from django.contrib.auth.models import User


class Dashboard(models.Model):
    """
    Dashboard personalizzabile per utente
    """

    # Owner
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="dashboards",
        help_text="Proprietario della dashboard",
    )

    # Identificazione
    name = models.CharField(max_length=255, help_text="Nome della dashboard")

    description = models.TextField(blank=True, help_text="Descrizione della dashboard")

    # Configurazione
    is_default = models.BooleanField(
        default=False, help_text="Dashboard di default per l'utente"
    )

    is_public = models.BooleanField(
        default=False, help_text="Dashboard visibile ad altri utenti"
    )

    # Layout (react-grid-layout configuration)
    layout_config = models.JSONField(
        default=dict, help_text="Configurazione layout per react-grid-layout"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-updated_at"]
        indexes = [
            models.Index(fields=["user", "is_default"]),
            models.Index(fields=["is_public"]),
        ]
        verbose_name = "Dashboard"
        verbose_name_plural = "Dashboards"
        unique_together = [["user", "name"]]

    def __str__(self):
        default_marker = " [Default]" if self.is_default else ""
        return f"{self.name} - {self.user.username}{default_marker}"

    def save(self, *args, **kwargs):
        """Override save per gestire is_default unico per utente"""
        if self.is_default:
            # Rimuovi is_default da altre dashboard dello stesso utente
            Dashboard.objects.filter(user=self.user, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)


class Widget(models.Model):
    """
    Widget componente di una dashboard
    """

    WIDGET_TYPE_CHOICES = [
        ("threat_summary", "Threat Summary"),
        ("threat_chart", "Threat Chart"),
        ("target_status", "Target Status"),
        ("recent_threats", "Recent Threats"),
        ("top_attackers", "Top Attackers"),
        ("rule_count", "Rule Count"),
        ("traffic_stats", "Traffic Stats"),
        ("activity_timeline", "Activity Timeline"),
        ("geo_map", "Geographic Map"),
        ("custom", "Custom Widget"),
    ]

    # Relazione con dashboard
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name="widgets",
        help_text="Dashboard a cui appartiene il widget",
    )

    # Identificazione
    title = models.CharField(max_length=255, help_text="Titolo del widget")

    widget_type = models.CharField(
        max_length=50, choices=WIDGET_TYPE_CHOICES, help_text="Tipo di widget"
    )

    # Configurazione
    config = models.JSONField(
        default=dict,
        help_text="Configurazione specifica del widget (filtri, opzioni, ecc.)",
    )

    # Posizione e dimensioni (react-grid-layout)
    grid_position = models.JSONField(
        default=dict, help_text="Posizione nel grid layout {x, y, w, h}"
    )

    # Stato
    is_visible = models.BooleanField(
        default=True, help_text="Widget visibile nella dashboard"
    )

    # Refresh interval (secondi)
    refresh_interval = models.PositiveIntegerField(
        default=60, help_text="Intervallo di refresh in secondi (0 = manuale)"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["dashboard", "created_at"]
        indexes = [
            models.Index(fields=["dashboard", "is_visible"]),
            models.Index(fields=["widget_type"]),
        ]
        verbose_name = "Widget"
        verbose_name_plural = "Widgets"

    def __str__(self):
        return f"{self.title} ({self.widget_type}) - {self.dashboard.name}"

    @property
    def position_x(self):
        return self.grid_position.get("x", 0)

    @property
    def position_y(self):
        return self.grid_position.get("y", 0)

    @property
    def width(self):
        return self.grid_position.get("w", 4)

    @property
    def height(self):
        return self.grid_position.get("h", 3)

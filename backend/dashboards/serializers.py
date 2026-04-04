"""
Serializers per l'app Dashboards
"""

from rest_framework import serializers
from .models import Dashboard, Widget


class WidgetSerializer(serializers.ModelSerializer):
    """Serializer per il modello Widget"""

    class Meta:
        model = Widget
        fields = [
            "id",
            "dashboard",
            "title",
            "widget_type",
            "config",
            "grid_position",
            "is_visible",
            "refresh_interval",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class DashboardSerializer(serializers.ModelSerializer):
    """Serializer per il modello Dashboard"""

    widgets = WidgetSerializer(many=True, read_only=True)
    widget_count = serializers.SerializerMethodField()

    class Meta:
        model = Dashboard
        fields = [
            "id",
            "user",
            "name",
            "description",
            "is_default",
            "is_public",
            "layout_config",
            "widgets",
            "widget_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "user"]

    def get_widget_count(self, obj):
        """Conta i widget nella dashboard"""
        return obj.widgets.count()


class DashboardListSerializer(serializers.ModelSerializer):
    """Serializer semplificato per lista dashboard"""

    widget_count = serializers.SerializerMethodField()
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Dashboard
        fields = [
            "id",
            "name",
            "username",
            "is_default",
            "is_public",
            "widget_count",
            "updated_at",
        ]

    def get_widget_count(self, obj):
        return obj.widgets.count()


class DashboardCreateSerializer(serializers.ModelSerializer):
    """Serializer per creazione dashboard"""

    class Meta:
        model = Dashboard
        fields = [
            "name",
            "description",
            "is_default",
            "is_public",
            "layout_config",
        ]

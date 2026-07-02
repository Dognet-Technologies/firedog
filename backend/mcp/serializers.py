"""Serializers per la gestione delle API key MCP (config utente in Settings)."""

from django.utils import timezone
from rest_framework import serializers

from .models import MCPAPIKey


class MCPAPIKeySerializer(serializers.ModelSerializer):
    """Rappresentazione di una chiave: mai la chiave in chiaro, solo il prefisso."""

    class Meta:
        model = MCPAPIKey
        fields = [
            "id",
            "name",
            "key_prefix",
            "is_active",
            "created_at",
            "expires_at",
            "last_used_at",
        ]
        read_only_fields = [
            "id",
            "key_prefix",
            "is_active",
            "created_at",
            "last_used_at",
        ]

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("La scadenza deve essere nel futuro.")
        return value

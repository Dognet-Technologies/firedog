"""
Serializers per l'app Discovery
"""
from rest_framework import serializers
from .models import DiscoveredHost


class DiscoveredHostSerializer(serializers.ModelSerializer):
    """Serializer per il modello DiscoveredHost"""
    
    display_name = serializers.ReadOnlyField()
    is_recently_discovered = serializers.ReadOnlyField()
    
    class Meta:
        model = DiscoveredHost
        fields = [
            'id',
            'ip_address',
            'mac_address',
            'hostname',
            'vendor',
            'network',
            'netmask',
            'discovered_at',
            'last_seen',
            'scan_count',
            'is_alive',
            'is_imported',
            'notes',
            'display_name',
            'is_recently_discovered',
        ]
        read_only_fields = [
            'discovered_at',
            'last_seen',
            'scan_count',
            'is_alive',
        ]


class DiscoveredHostListSerializer(serializers.ModelSerializer):
    """Serializer semplificato per lista host scoperti"""
    
    class Meta:
        model = DiscoveredHost
        fields = [
            'id',
            'ip_address',
            'mac_address',
            'hostname',
            'vendor',
            'is_alive',
            'is_imported',
            'last_seen',
        ]

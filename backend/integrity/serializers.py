"""
Serializers per l'app Integrity
"""
from rest_framework import serializers
from .models import FileIntegrity


class FileIntegritySerializer(serializers.ModelSerializer):
    """Serializer per il modello FileIntegrity"""
    
    approved_by_username = serializers.CharField(source='approved_by.username', read_only=True)
    needs_attention = serializers.ReadOnlyField()
    
    class Meta:
        model = FileIntegrity
        fields = [
            'id',
            'file_path',
            'file_type',
            'sha512_hash',
            'previous_hash',
            'file_size',
            'file_permissions',
            'file_owner',
            'status',
            'last_checked',
            'last_modified',
            'change_detected_at',
            'is_change_approved',
            'approved_by',
            'approved_by_username',
            'approved_at',
            'change_notes',
            'alert_sent',
            'created_at',
            'needs_attention',
        ]
        read_only_fields = [
            'sha512_hash',
            'previous_hash',
            'last_checked',
            'change_detected_at',
            'approved_by',
            'approved_at',
            'created_at',
        ]


class FileIntegrityListSerializer(serializers.ModelSerializer):
    """Serializer semplificato per lista file integrity"""
    
    class Meta:
        model = FileIntegrity
        fields = [
            'id',
            'file_path',
            'status',
            'is_change_approved',
            'last_checked',
            'change_detected_at',
        ]

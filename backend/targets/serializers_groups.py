"""
Serializers per Target Groups
CREA QUESTO FILE: backend/targets/serializers_groups.py
"""

from rest_framework import serializers
from .models import Target, TargetGroup, GroupRuleTemplate
from django.core.validators import RegexValidator
import re


class GroupRuleTemplateSerializer(serializers.ModelSerializer):
    """Serializer per template di regole di gruppo"""

    class Meta:
        model = GroupRuleTemplate
        fields = [
            "id",
            "name",
            "protocol",
            "port",
            "source_ip",
            "action",
            "comment",
            "priority",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_port(self, value):
        """Validazione porta (OWASP: Input Validation)"""
        if value is not None:
            if value < 1 or value > 65535:
                raise serializers.ValidationError("Port must be between 1 and 65535")
        return value

    def validate_name(self, value):
        """Validazione nome (NIST: Sanitization)"""
        # Previeni XSS e injection
        if re.search(r"[<>\"\'&;]", value):
            raise serializers.ValidationError("Name contains invalid characters")
        if len(value) > 255:
            raise serializers.ValidationError("Name too long (max 255 characters)")
        return value.strip()

    def validate_comment(self, value):
        """Validazione commento"""
        if value:
            # Limita lunghezza per prevenire DoS
            if len(value) > 1000:
                raise serializers.ValidationError(
                    "Comment too long (max 1000 characters)"
                )
            # Sanitize
            value = value.strip()
        return value


class TargetGroupListSerializer(serializers.ModelSerializer):
    """Serializer leggero per lista gruppi"""

    target_count = serializers.IntegerField(read_only=True)
    online_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = TargetGroup
        fields = [
            "id",
            "name",
            "description",
            "color",
            "icon",
            "target_count",
            "online_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "target_count",
            "online_count",
            "created_at",
            "updated_at",
        ]


class TargetGroupDetailSerializer(serializers.ModelSerializer):
    """Serializer completo per dettagli gruppo"""

    targets = serializers.SerializerMethodField()
    rule_templates = GroupRuleTemplateSerializer(many=True, read_only=True)
    target_count = serializers.IntegerField(read_only=True)
    online_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = TargetGroup
        fields = [
            "id",
            "name",
            "description",
            "color",
            "icon",
            "targets",
            "target_count",
            "online_count",
            "rule_templates",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "target_count",
            "online_count",
            "created_at",
            "updated_at",
        ]

    def get_targets(self, obj):
        """Restituisce lista target del gruppo"""
        return [
            {
                "id": t.id,
                "ip_address": t.ip_address,
                "hostname": t.hostname,
                "status": t.status,
                "last_seen": t.last_seen,
            }
            for t in obj.targets.all()
        ]

    def validate_name(self, value):
        """Validazione nome gruppo (OWASP)"""
        # Previeni XSS
        if re.search(r"[<>\"\'&;]", value):
            raise serializers.ValidationError("Name contains invalid characters")
        # Lunghezza massima
        if len(value) > 100:
            raise serializers.ValidationError("Name too long (max 100 characters)")
        return value.strip()

    def validate_color(self, value):
        """Validazione colore esadecimale"""
        if not re.match(r"^#[0-9A-Fa-f]{6}$", value):
            raise serializers.ValidationError("Invalid color format (use #RRGGBB)")
        return value.lower()

    def validate_description(self, value):
        """Validazione descrizione"""
        if value:
            if len(value) > 1000:
                raise serializers.ValidationError(
                    "Description too long (max 1000 characters)"
                )
            value = value.strip()
        return value


class TargetGroupCreateSerializer(serializers.ModelSerializer):
    """Serializer per creazione gruppo"""

    target_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        help_text="Lista di ID target da aggiungere al gruppo",
    )

    class Meta:
        model = TargetGroup
        fields = ["name", "description", "color", "icon", "target_ids"]

    def validate_target_ids(self, value):
        """Valida che tutti i target esistano"""
        if value:
            existing_ids = set(
                Target.objects.filter(id__in=value).values_list("id", flat=True)
            )
            invalid_ids = set(value) - existing_ids
            if invalid_ids:
                raise serializers.ValidationError(
                    f"Invalid target IDs: {', '.join(map(str, invalid_ids))}"
                )
        return value

    def create(self, validated_data):
        """Crea gruppo e assegna target"""
        target_ids = validated_data.pop("target_ids", [])
        group = TargetGroup.objects.create(**validated_data)

        if target_ids:
            targets = Target.objects.filter(id__in=target_ids)
            group.targets.set(targets)

        return group


class AssignTargetsSerializer(serializers.Serializer):
    """Serializer per assegnazione/rimozione target da gruppo"""

    target_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        help_text="Lista di ID target da aggiungere/rimuovere",
    )

    def validate_target_ids(self, value):
        """Valida esistenza target"""
        if not value:
            raise serializers.ValidationError("At least one target ID required")

        existing_ids = set(
            Target.objects.filter(id__in=value).values_list("id", flat=True)
        )
        invalid_ids = set(value) - existing_ids

        if invalid_ids:
            raise serializers.ValidationError(
                f"Invalid target IDs: {', '.join(map(str, invalid_ids))}"
            )

        return value

"""
Views per Target Groups
CREA QUESTO FILE: backend/targets/views_groups.py
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import Target, TargetGroup, GroupRuleTemplate
from .serializers_groups import (
    TargetGroupListSerializer,
    TargetGroupDetailSerializer,
    TargetGroupCreateSerializer,
    GroupRuleTemplateSerializer,
    AssignTargetsSerializer,
)
from audit.models import AuditLog

import logging

logger = logging.getLogger(__name__)


class TargetGroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet per gestione gruppi di target

    Endpoints:
    - GET    /api/groups/              -> Lista tutti i gruppi
    - POST   /api/groups/              -> Crea nuovo gruppo
    - GET    /api/groups/{id}/         -> Dettagli gruppo
    - PUT    /api/groups/{id}/         -> Aggiorna gruppo
    - DELETE /api/groups/{id}/         -> Elimina gruppo
    - POST   /api/groups/{id}/add_targets/    -> Aggiungi target al gruppo
    - POST   /api/groups/{id}/remove_targets/ -> Rimuovi target dal gruppo
    """

    queryset = TargetGroup.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Seleziona serializer in base all'azione"""
        if self.action == "list":
            return TargetGroupListSerializer
        elif self.action == "create":
            return TargetGroupCreateSerializer
        else:
            return TargetGroupDetailSerializer

    def list(self, request):
        """Lista gruppi con conteggi"""
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)

            logger.info(
                f"User {request.user.id} retrieved {len(serializer.data)} groups"
            )

            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error listing groups: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @transaction.atomic
    def create(self, request):
        """Crea nuovo gruppo"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            group = serializer.save()

            # Audit log
            AuditLog.log_action(
                action="create",
                description=f"Created target group: {group.name}",
                user=request.user,
                content_object=group,
                new_values={
                    "name": group.name,
                    "target_count": group.target_count,
                },
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
                success=True,
            )
            logger.info(f"User {request.user.id} created group '{group.name}'")

            # Restituisci dettagli completi
            detail_serializer = TargetGroupDetailSerializer(group)
            return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating group: {e}")

            # Audit log errore
            try:
                AuditLog.log_action(
                    action="create",
                    description=f"Failed to create target group",
                    user=request.user,
                    ip_address=request.META.get("REMOTE_ADDR"),
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
                    success=False,
                    error_message=str(e),
                )
            except:
                pass

            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, pk=None):
        """Dettagli gruppo con target e rule templates"""
        try:
            group = get_object_or_404(TargetGroup, pk=pk)
            serializer = self.get_serializer(group)

            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error retrieving group {pk}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    def update(self, request, pk=None):
        """Aggiorna gruppo"""
        try:
            group = get_object_or_404(TargetGroup, pk=pk)
            old_values = {
                "name": group.name,
                "description": group.description,
                "color": group.color,
                "icon": group.icon,
            }

            serializer = self.get_serializer(group, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            updated_group = serializer.save()

            new_values = {
                "name": updated_group.name,
                "description": updated_group.description,
                "color": updated_group.color,
                "icon": updated_group.icon,
            }

            # Audit log
            AuditLog.log_action(
                action="update",
                description=f"Updated target group: {updated_group.name}",
                user=request.user,
                content_object=updated_group,
                old_values=old_values,
                new_values=new_values,
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
                success=True,
            )

            logger.info(f"User {request.user.id} updated group '{updated_group.name}'")

            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error updating group {pk}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def destroy(self, request, pk=None):
        """Elimina gruppo"""
        try:
            group = get_object_or_404(TargetGroup, pk=pk)
            group_name = group.name
            target_count = group.target_count

            # Audit log prima dell'eliminazione
            AuditLog.log_action(
                action="delete",
                description=f"Deleted target group: {group_name} ({target_count} targets)",
                user=request.user,
                old_values={
                    "name": group_name,
                    "target_count": target_count,
                },
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
                success=True,
            )

            group.delete()

            logger.info(f"User {request.user.id} deleted group '{group_name}'")

            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.error(f"Error deleting group {pk}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def add_targets(self, request, pk=None):
        """
        Aggiungi target al gruppo
        Body: { "target_ids": [1, 2, 3] }
        """
        try:
            group = get_object_or_404(TargetGroup, pk=pk)

            serializer = AssignTargetsSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            target_ids = serializer.validated_data["target_ids"]
            targets = Target.objects.filter(id__in=target_ids)

            # Aggiungi target (many-to-many, non rimuove gli esistenti)
            group.targets.add(*targets)

            # Audit log
            AuditLog.log_action(
                action="update",
                description=f"Added {len(targets)} target(s) to group: {group.name}",
                user=request.user,
                content_object=group,
                new_values={
                    "added_targets": [t.ip_address for t in targets],
                    "total_targets": group.target_count,
                },
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
                success=True,
            )

            logger.info(
                f"User {request.user.id} added {len(targets)} targets to group '{group.name}'"
            )

            # Restituisci dettagli aggiornati
            detail_serializer = TargetGroupDetailSerializer(group)
            return Response(
                {
                    "message": f"Added {len(targets)} target(s) to group",
                    "group": detail_serializer.data,
                }
            )

        except Exception as e:
            logger.error(f"Error adding targets to group {pk}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def remove_targets(self, request, pk=None):
        """
        Rimuovi target dal gruppo
        Body: { "target_ids": [1, 2, 3] }
        """
        try:
            group = get_object_or_404(TargetGroup, pk=pk)

            serializer = AssignTargetsSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            target_ids = serializer.validated_data["target_ids"]
            targets = Target.objects.filter(id__in=target_ids)

            # Rimuovi target
            group.targets.remove(*targets)

            # Audit log
            AuditLog.log_action(
                action="update",
                description=f"Removed {len(targets)} target(s) from group: {group.name}",
                user=request.user,
                content_object=group,
                new_values={
                    "removed_targets": [t.ip_address for t in targets],
                    "total_targets": group.target_count,
                },
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
                success=True,
            )

            logger.info(
                f"User {request.user.id} removed {len(targets)} targets from group '{group.name}'"
            )

            # Restituisci dettagli aggiornati
            detail_serializer = TargetGroupDetailSerializer(group)
            return Response(
                {
                    "message": f"Removed {len(targets)} target(s) from group",
                    "group": detail_serializer.data,
                }
            )

        except Exception as e:
            logger.error(f"Error removing targets from group {pk}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def available_targets(self, request, pk=None):
        """
        Restituisce target NON ancora nel gruppo
        Utile per UI di assegnazione
        """
        try:
            group = get_object_or_404(TargetGroup, pk=pk)

            # Target non nel gruppo
            available = Target.objects.exclude(groups=group)

            data = [
                {
                    "id": t.id,
                    "ip_address": t.ip_address,
                    "hostname": t.hostname,
                    "status": t.status,
                    "last_seen": t.last_seen,
                }
                for t in available
            ]

            return Response({"count": len(data), "targets": data})

        except Exception as e:
            logger.error(f"Error getting available targets for group {pk}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GroupRuleTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet per gestione template di regole per gruppo

    Endpoints:
    - GET    /api/group-rules/?group={group_id}  -> Lista regole di un gruppo
    - POST   /api/group-rules/                   -> Crea nuova regola template
    - GET    /api/group-rules/{id}/              -> Dettagli regola
    - PUT    /api/group-rules/{id}/              -> Aggiorna regola
    - DELETE /api/group-rules/{id}/              -> Elimina regola
    """

    queryset = GroupRuleTemplate.objects.all()
    serializer_class = GroupRuleTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtra per gruppo se specificato"""
        queryset = super().get_queryset()
        group_id = self.request.query_params.get("group", None)

        if group_id:
            queryset = queryset.filter(group_id=group_id)

        return queryset

    @transaction.atomic
    def create(self, request):
        """Crea template regola"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            rule = serializer.save()

            # Audit log
            AuditLog.log_action(
                action="create",
                description=f"Created rule template for group: {rule.group.name}",
                user=request.user,
                content_object=rule,
                new_values={
                    "group": rule.group.name,
                    "name": rule.name,
                    "protocol": rule.protocol,
                    "port": rule.port,
                    "action": rule.action,
                },
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
                success=True,
            )

            logger.info(
                f"User {request.user.id} created rule template '{rule.name}' "
                f"for group '{rule.group.name}'"
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating rule template: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def destroy(self, request, pk=None):
        """Elimina template regola"""
        try:
            rule = get_object_or_404(GroupRuleTemplate, pk=pk)
            group_name = rule.group.name
            rule_name = rule.name

            # Audit log
            AuditLog.log_action(
                action="delete",
                description=f"Deleted rule template: {rule_name} from group: {group_name}",
                user=request.user,
                old_values={
                    "group": group_name,
                    "name": rule_name,
                    "protocol": rule.protocol,
                    "port": rule.port,
                },
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
                success=True,
            )

            rule.delete()

            logger.info(
                f"User {request.user.id} deleted rule template '{rule_name}' "
                f"from group '{group_name}'"
            )

            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.error(f"Error deleting rule template {pk}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

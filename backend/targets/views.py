"""
Views per l'app Targets - API endpoints per gestione target remoti
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
import logging

from .models import Target
from .serializers import TargetSerializer, TargetListSerializer, TargetCreateSerializer
from core.ssh_manager import SSHManager, SSHConnectionError
from audit.models import AuditLog

"""
Views per Whitelist e BlockedIPs
API endpoints completi con logging audit e validazioni
"""
from django.utils import timezone
from django.db.models import Count, Sum, Q
from datetime import timedelta
import logging

from .models import WhitelistEntry, BlockedIP, FirewallStats
from .serializers import (
    WhitelistEntrySerializer,
    WhitelistEntryCreateSerializer,
    BlockedIPSerializer,
    BlockedIPCreateSerializer,
    BlockedIPStatsSerializer,
    FirewallStatsSerializer,
)
from targets.models import Target
from audit.models import AuditLog

logger = logging.getLogger("firedog.targets")


class TargetViewSet(viewsets.ModelViewSet):
    """ViewSet per gestione Target"""

    queryset = Target.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    serializer_class = TargetSerializer
    filterset_fields = ["status", "ip_address"]

    def get_serializer_class(self):
        if self.action == "list":
            return TargetListSerializer
        elif self.action == "create":
            return TargetCreateSerializer
        return TargetSerializer

    @action(detail=True, methods=["post"])
    def test_connection(self, request, pk=None):
        """Testa connessione SSH al target"""
        target = self.get_object()

        try:
            ssh = SSHManager(
                host=target.ip_address, port=target.ssh_port, username=target.ssh_user
            )
            ssh.connect()
            user_exists = ssh.check_user_exists(target.ssh_user)
            exit_code, stdout, stderr = ssh.execute_command("whoami")
            ssh.disconnect()

            target.mark_online()

            return Response(
                {
                    "success": True,
                    "message": "Connessione SSH riuscita",
                    "user_exists": user_exists,
                    "whoami": stdout.strip(),
                }
            )

        except SSHConnectionError as e:
            target.mark_offline(str(e))
            return Response(
                {"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"])
    def install(self, request, pk=None):
        """Installa pacchetto firedog sul target"""
        target = self.get_object()

        # Permetti reinstall se richiesto esplicitamente
        force_reinstall = request.data.get("force_reinstall", False)

        if target.status == "online" and target.firedog_version and not force_reinstall:
            return Response(
                {
                    "error": "Firedog già installato",
                    "hint": "Use force_reinstall=true to reinstall",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Se è una reinstall, logga l'evento
        if target.status == "online" and target.firedog_version:
            from audit.models import AuditLog

            AuditLog.objects.create(
                username=request.user.username,
                action="target.reinstall",
                target=target,
                details={"previous_version": target.firedog_version},
                ip_address=request.META.get("REMOTE_ADDR"),
            )

        target.status = "installing"
        target.save(update_fields=["status"])

        # Qui verrà chiamato il task Celery
        from targets.tasks import install_firedog_on_target

        install_firedog_on_target.delay(target.id, request.user.id)

        return Response(
            {
                "success": True,
                "message": "Installazione avviata",
                "status": "installing",
            }
        )

    def destroy(self, request, *args, **kwargs):
        """
        Elimina FISICAMENTE il target dal database (hard delete)
        DELETE /api/targets/{id}/
        """
        target = self.get_object()
        target_ip = target.ip_address
        target_hostname = target.hostname
        target_id = target.id

        try:
            # Audit log PRIMA di eliminare (senza content_object per evitare problemi con FK)
            AuditLog.log_action(
                action="delete",
                description=f"Deleted target {target_hostname or target_ip} (IP: {target_ip})",
                user=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
                old_values={
                    "id": target_id,
                    "ip_address": target_ip,
                    "hostname": target_hostname,
                    "status": target.status,
                },
            )

            # HARD DELETE - elimina fisicamente dal database
            target.delete()

            logger.info(f"Target deleted: {target_ip} (ID: {target_id})")

            return Response(
                {
                    "success": True,
                    "message": f"Target {target_ip} eliminato permanentemente",
                    "deleted_id": target_id,
                },
                status=status.HTTP_204_NO_CONTENT,
            )

        except Exception as e:
            logger.error(f"Error deleting target {target_ip}: {str(e)}", exc_info=True)
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="check-ip")
    def check_ip(self, request):
        """
        Verifica se un IP è già registrato
        GET /api/targets/check-ip/?ip=192.168.1.100
        """
        ip_address = request.query_params.get("ip")

        if not ip_address:
            return Response({"error": "IP address required"}, status=400)

        exists = Target.objects.filter(ip_address=ip_address).exists()

        if exists:
            target = Target.objects.get(ip_address=ip_address)
            return Response(
                {
                    "exists": True,
                    "target": {
                        "id": target.id,
                        "hostname": target.hostname,
                        "status": target.status,
                        "created_at": target.created_at,
                    },
                }
            )
        else:
            return Response({"exists": False, "message": "IP disponibile"})


class WhitelistEntryViewSet(viewsets.ModelViewSet):
    """
    ViewSet per gestione Whitelist

    Endpoints:
    - GET /api/whitelist/ - Lista entries
    - GET /api/whitelist/{id}/ - Dettaglio entry
    - POST /api/whitelist/ - Crea entry
    - PATCH /api/whitelist/{id}/ - Aggiorna entry
    - DELETE /api/whitelist/{id}/ - Elimina entry
    - POST /api/whitelist/{id}/deactivate/ - Disattiva entry
    - POST /api/whitelist/{id}/activate/ - Riattiva entry
    - GET /api/whitelist/by_target/ - Filtra per target
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["target", "is_active"]

    def get_queryset(self):
        return (
            WhitelistEntry.objects.all().select_related("target").order_by("-added_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return WhitelistEntryCreateSerializer
        return WhitelistEntrySerializer

    def perform_create(self, serializer):
        """Crea entry con logging audit"""
        entry = serializer.save()

        # Log audit
        AuditLog.log_action(
            action="create",
            description=f"Added {entry.ip_address} to whitelist",
            user=self.request.user,
            content_object=entry,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            new_values={"ip_address": entry.ip_address, "target": entry.target.id},
        )

        logger.info(
            f"Whitelist entry created: {entry.ip_address} on target {entry.target.id}"
        )

    def perform_destroy(self, instance):
        """Elimina entry con logging audit"""
        ip_address = instance.ip_address
        target_id = instance.target.id

        # Log audit
        AuditLog.log_action(
            action="delete",
            description=f"Removed {ip_address} from whitelist",
            user=self.request.user,
            content_object=instance,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            old_values={"ip_address": ip_address, "target": target_id},
        )

        instance.delete()
        logger.info(f"Whitelist entry deleted: {ip_address} on target {target_id}")

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """Disattiva entry (soft delete)"""
        entry = self.get_object()
        entry.is_active = False
        entry.save(update_fields=["is_active"])

        # Log audit
        AuditLog.log_action(
            action="update",
            description=f"Deactivated whitelist entry {entry.ip_address}",
            user=request.user,
            content_object=entry,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return Response({"message": "Entry deactivated successfully"})

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """Riattiva entry"""
        entry = self.get_object()
        entry.is_active = True
        entry.save(update_fields=["is_active"])

        # Log audit
        AuditLog.log_action(
            action="update",
            description=f"Activated whitelist entry {entry.ip_address}",
            user=request.user,
            content_object=entry,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return Response({"message": "Entry activated successfully"})

    @action(detail=False, methods=["get"])
    def by_target(self, request):
        """
        Filtra whitelist per target specifico
        GET /api/whitelist/by_target/?target_id=1
        """
        target_id = request.query_params.get("target_id")

        if not target_id:
            return Response(
                {"error": "target_id parameter required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entries = self.get_queryset().filter(target_id=target_id)
        serializer = self.get_serializer(entries, many=True)

        return Response({"count": entries.count(), "results": serializer.data})


class BlockedIPViewSet(viewsets.ModelViewSet):
    """
    ViewSet per gestione IP bloccati

    Endpoints:
    - GET /api/blocked-ips/ - Lista IP bloccati
    - GET /api/blocked-ips/{id}/ - Dettaglio IP
    - POST /api/blocked-ips/ - Blocca IP
    - DELETE /api/blocked-ips/{id}/ - Elimina blocco
    - POST /api/blocked-ips/{id}/unblock/ - Sblocca IP
    - GET /api/blocked-ips/stats/ - Statistiche
    - GET /api/blocked-ips/by_target/ - Filtra per target
    - POST /api/blocked-ips/cleanup_expired/ - Rimuovi blocchi scaduti
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["target", "is_active", "block_reason"]

    def get_queryset(self):
        return BlockedIP.objects.all().select_related("target").order_by("-blocked_at")

    def get_serializer_class(self):
        if self.action == "create":
            return BlockedIPCreateSerializer
        elif self.action == "stats":
            return BlockedIPStatsSerializer
        return BlockedIPSerializer

    def perform_create(self, serializer):
        """Crea blocco con logging audit"""
        block = serializer.save()

        # Log audit
        AuditLog.log_action(
            action="create",
            description=f"Blocked IP {block.ip_address} (reason: {block.block_reason})",
            user=self.request.user,
            content_object=block,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            new_values={
                "ip_address": block.ip_address,
                "target": block.target.id,
                "reason": block.block_reason,
            },
        )

        logger.warning(
            f"IP blocked: {block.ip_address} on target {block.target.id} - Reason: {block.block_reason}"
        )

    def perform_destroy(self, instance):
        """Elimina blocco con logging audit"""
        ip_address = instance.ip_address
        target_id = instance.target.id

        # Log audit
        AuditLog.log_action(
            action="delete",
            description=f"Removed block for IP {ip_address}",
            user=self.request.user,
            content_object=instance,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            old_values={"ip_address": ip_address, "target": target_id},
        )

        instance.delete()
        logger.info(f"IP block removed: {ip_address} on target {target_id}")

    @action(detail=True, methods=["post"])
    def unblock(self, request, pk=None):
        """
        Sblocca un IP
        POST /api/blocked-ips/{id}/unblock/
        """
        block = self.get_object()

        if not block.is_active:
            return Response(
                {"error": "IP is already unblocked"}, status=status.HTTP_400_BAD_REQUEST
            )

        block.unblock(unblocked_by=request.user.username)

        # Log audit
        AuditLog.log_action(
            action="update",
            description=f"Unblocked IP {block.ip_address}",
            user=request.user,
            content_object=block,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        logger.info(f"IP unblocked: {block.ip_address} on target {block.target.id}")

        serializer = self.get_serializer(block)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        Statistiche IP bloccati
        GET /api/blocked-ips/stats/?target_id=1
        """
        target_id = request.query_params.get("target_id")

        queryset = self.get_queryset()
        if target_id:
            queryset = queryset.filter(target_id=target_id)

        # Statistiche
        stats = {
            "total_blocked": queryset.count(),
            "active_blocks": queryset.filter(is_active=True).count(),
            "expired_blocks": queryset.filter(
                is_active=True, expires_at__lte=timezone.now()
            ).count(),
            "manual_blocks": queryset.filter(block_reason="manual").count(),
            "automatic_blocks": queryset.exclude(block_reason="manual").count(),
            "total_packets_blocked": queryset.aggregate(total=Sum("packet_count"))[
                "total"
            ]
            or 0,
            "top_blocked_ips": list(
                queryset.filter(is_active=True)
                .values("ip_address", "packet_count", "threat_score", "block_reason")
                .order_by("-packet_count")[:10]
            ),
            "blocks_by_reason": dict(
                queryset.values("block_reason")
                .annotate(count=Count("id"))
                .values_list("block_reason", "count")
            ),
        }

        serializer = self.get_serializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_target(self, request):
        """
        Filtra IP bloccati per target
        GET /api/blocked-ips/by_target/?target_id=1
        """
        target_id = request.query_params.get("target_id")

        if not target_id:
            return Response(
                {"error": "target_id parameter required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        blocks = self.get_queryset().filter(target_id=target_id, is_active=True)
        serializer = self.get_serializer(blocks, many=True)

        return Response({"count": blocks.count(), "results": serializer.data})

    @action(detail=False, methods=["post"])
    def cleanup_expired(self, request):
        """
        Rimuovi blocchi scaduti
        POST /api/blocked-ips/cleanup_expired/
        """
        expired_blocks = self.get_queryset().filter(
            is_active=True, expires_at__lte=timezone.now()
        )

        count = expired_blocks.count()

        for block in expired_blocks:
            block.unblock(unblocked_by="system")

        # Log audit
        AuditLog.log_action(
            action="delete",
            description=f"Cleanup: removed {count} expired blocks",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        logger.info(f"Cleaned up {count} expired IP blocks")

        return Response({"message": f"{count} expired blocks removed", "count": count})


@action(detail=False, methods=["get"], url_path="by-gruppo")
def by_gruppo(self, request):
    """
    Filtra target per gruppo
    GET /api/targets/by-gruppo/?gruppo=web
    """
    gruppo_param = request.query_params.get("gruppo")

    if gruppo_param:
        targets = Target.objects.filter(gruppo=gruppo_param)
        serializer = self.get_serializer(targets, many=True)
        return Response(serializer.data)
    else:
        # Ritorna statistiche per gruppo
        groups = (
            Target.objects.values("gruppo")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return Response(groups)


@action(detail=False, methods=["post"], url_path="bulk-update-gruppo")
def bulk_update_gruppo(self, request):
    """
    Aggiorna gruppo per multipli target
    POST /api/targets/bulk-update-gruppo/
    Body: {"target_ids": [1,2,3], "gruppo": "web"}
    """
    target_ids = request.data.get("target_ids", [])
    gruppo = request.data.get("gruppo")
    gruppo_custom = request.data.get("gruppo_custom")

    if not target_ids or not gruppo:
        return Response({"error": "target_ids e gruppo obbligatori"}, status=400)

    if gruppo == "custom" and not gruppo_custom:
        return Response({"error": "gruppo_custom obbligatorio"}, status=400)

    updated = Target.objects.filter(id__in=target_ids).update(
        gruppo=gruppo, gruppo_custom=gruppo_custom if gruppo == "custom" else None
    )

    return Response({"success": True, "updated_count": updated, "gruppo": gruppo})


class FirewallStatsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet read-only per statistiche firewall (traffico).
    Filtra per target_id e supporta limit per limitare i risultati.
    GET /api/firewall-stats/?target_id=X&limit=48
    """

    serializer_class = FirewallStatsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = FirewallStats.objects.all()
        target_id = self.request.query_params.get("target_id")
        if target_id:
            queryset = queryset.filter(target_id=target_id)
        try:
            limit = int(self.request.query_params.get("limit", 100))
            limit = min(max(limit, 1), 500)
        except (TypeError, ValueError):
            limit = 100
        return queryset[:limit]

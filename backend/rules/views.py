"""
Views per Rules API
Gestione regole firewall sia DB che via SSH
"""

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from accounts.permissions import IsAdminUser, IsAdminOrReadOnly
from .models import FirewallRule
from .serializers import (
    FirewallRuleSerializer,
    FirewallRuleListSerializer,
    AddFirewallRuleViaSSHSerializer,
    RemoveFirewallRuleViaSSHSerializer,
)
from .services import dispatch_add_rule, dispatch_remove_rule
from targets.models import Target
from core.ssh_manager import SSHManager
from audit.models import AuditLog

logger = logging.getLogger("firedog.rules_api")


class FirewallRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet per regole firewall (CRUD su DB)

    Permissions:
    - GET/LIST: Tutti gli utenti autenticati
    - POST/PUT/PATCH/DELETE: Solo Admin
    """

    queryset = FirewallRule.objects.all()
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "target",
        "chain",
        "protocol",
        "action",
        "is_custom",
        "is_synced",
    ]

    def get_serializer_class(self):
        if self.action == "list":
            return FirewallRuleListSerializer
        return FirewallRuleSerializer

    def perform_create(self, serializer):
        """Salva la rule in DB e la dispatcha all'agent del target via WS.

        Se l'agent non è connesso, la rule viene comunque persistita con
        is_synced=False: sarà la successiva snapshot dell'agent a riconciliarla
        (o l'utente potrà ri-applicarla manualmente).
        """
        rule = serializer.save(is_custom=True, is_synced=False)
        dispatch_add_rule(rule)

    def perform_destroy(self, instance):
        """Cancella la rule lato server e chiede all'agent di rimuoverla.

        Per semplicità V1: se l'agent non è connesso, eliminiamo comunque dal DB
        (l'utente potrà fare cleanup manuale o aspettare la prossima snapshot
        che ri-osserverà la rule come is_custom=False).
        """
        target = instance.target
        rule_number = instance.rule_number
        chain = instance.chain
        instance.delete()
        dispatch_remove_rule(target, chain, rule_number)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def add_via_ssh(self, request):
        """
        Aggiunge regola firewall via SSH sul target

        POST /api/rules/add_via_ssh/
        {
            "target_id": 1,
            "chain": "INPUT",
            "port": 80,
            "protocol": "tcp",
            "source_ip": "192.168.1.0/24",  // opzionale
            "comment": "HTTP traffic"        // opzionale
        }

        Permissions: Solo Admin
        """
        serializer = AddFirewallRuleViaSSHSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            # Ottieni target
            target = Target.objects.get(id=data["target_id"])

            # Costruisci comando firewall-manager
            chain_lower = data["chain"].lower()
            cmd_parts = [
                "sudo",
                "/usr/local/bin/firewall-manager",
                f"--add-{chain_lower}",
                str(data["port"]),
                data["protocol"],
            ]

            # Aggiungi source/dest IP se specificato
            if data.get("source_ip"):
                cmd_parts.extend(["--source", data["source_ip"]])

            if data.get("dest_ip"):
                cmd_parts.extend(["--dest", data["dest_ip"]])

            # Aggiungi commento se specificato
            if data.get("comment"):
                cmd_parts.extend(["--comment", f'"{data["comment"]}"'])

            # Esegui via SSH
            ssh = SSHManager(
                host=target.ip_address, port=target.ssh_port, username=target.ssh_user
            )

            ssh.connect()

            cmd = " ".join(cmd_parts)
            exit_code, stdout, stderr = ssh.execute_command(cmd, timeout=30)

            ssh.disconnect()

            # Audit log
            AuditLog.objects.create(
                user=request.user,
                action="add_firewall_rule_ssh",
                target=target,
                details={
                    "chain": data["chain"],
                    "port": data["port"],
                    "protocol": data["protocol"],
                    "source_ip": data.get("source_ip"),
                    "comment": data.get("comment"),
                    "exit_code": exit_code,
                    "command": cmd,
                },
                success=(exit_code == 0),
            )

            if exit_code == 0:
                logger.info(
                    f"Rule added successfully on target {target.id} by {request.user.username}"
                )

                return Response(
                    {
                        "success": True,
                        "message": "Regola aggiunta con successo",
                        "command": cmd,
                        "output": stdout,
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                logger.error(f"Failed to add rule on target {target.id}: {stderr}")

                return Response(
                    {
                        "success": False,
                        "message": "Errore aggiunta regola",
                        "command": cmd,
                        "error": stderr,
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Target.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": f'Target {data["target_id"]} non trovato',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception as e:
            logger.exception(f"Error adding rule via SSH: {e}")

            return Response(
                {"success": False, "message": f"Errore: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def remove_via_ssh(self, request):
        """
        Rimuove regola firewall via SSH sul target

        POST /api/rules/remove_via_ssh/
        {
            "target_id": 1,
            "chain": "INPUT",
            "rule_number": 5
        }

        Permissions: Solo Admin
        """
        serializer = RemoveFirewallRuleViaSSHSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            # Ottieni target
            target = Target.objects.get(id=data["target_id"])

            # Costruisci comando firewall-manager
            cmd = f'sudo /usr/local/bin/firewall-manager --remove {data["chain"]} {data["rule_number"]}'

            # Esegui via SSH
            ssh = SSHManager(
                host=target.ip_address, port=target.ssh_port, username=target.ssh_user
            )

            ssh.connect()

            exit_code, stdout, stderr = ssh.execute_command(cmd, timeout=30)

            ssh.disconnect()

            # Audit log
            AuditLog.objects.create(
                user=request.user,
                action="remove_firewall_rule_ssh",
                target=target,
                details={
                    "chain": data["chain"],
                    "rule_number": data["rule_number"],
                    "exit_code": exit_code,
                    "command": cmd,
                },
                success=(exit_code == 0),
            )

            if exit_code == 0:
                logger.info(
                    f"Rule removed successfully on target {target.id} by {request.user.username}"
                )

                return Response(
                    {
                        "success": True,
                        "message": "Regola rimossa con successo",
                        "command": cmd,
                        "output": stdout,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                logger.error(f"Failed to remove rule on target {target.id}: {stderr}")

                return Response(
                    {
                        "success": False,
                        "message": "Errore rimozione regola",
                        "command": cmd,
                        "error": stderr,
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Target.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": f'Target {data["target_id"]} non trovato',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception as e:
            logger.exception(f"Error removing rule via SSH: {e}")

            return Response(
                {"success": False, "message": f"Errore: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

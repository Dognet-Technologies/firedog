"""
WebSocket Consumer per comunicazione con dog-agent
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import (
    AgentAPIKey,
    PairingSession,
    AgentConnection,
    AgentCommand,
    AgentHeartbeat,
)
from targets.models import Target, Alert, FirewallStats
from threats.models import ThreatLog

logger = logging.getLogger(__name__)


class AgentConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket per comunicazione con gli agent
    URL: ws://server/ws/agent/
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target = None
        self.connection = None

    async def connect(self):
        """
        Accetta connessione WebSocket
        """
        await self.accept()
        logger.info(f"Agent WebSocket connected from {self.scope['client']}")

    async def disconnect(self, close_code):
        """
        Gestisce disconnessione
        """
        if self.connection:
            await self.mark_connection_offline()
            logger.info(f"Agent disconnected: {self.target}")

    async def receive(self, text_data):
        """
        Riceve messaggi dall'agent
        """
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            logger.debug(f"Received message type: {message_type}")

            # Routing messaggi
            if message_type == "pair_request":
                await self.handle_pair_request(data)
            elif message_type == "heartbeat":
                await self.handle_heartbeat(data)
            elif message_type == "threat_log":
                await self.handle_threat_log(data)
            elif message_type == "command_response":
                await self.handle_command_response(data)
            elif message_type == "firewall_stats":
                await self.handle_firewall_stats(data)
            else:
                await self.send_error(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as e:
            logger.error(f"Error in receive: {e}", exc_info=True)
            await self.send_error(f"Internal error: {str(e)}")

    async def handle_pair_request(self, data):
        """
        Gestisce richiesta di pairing dall'agent
        Messaggio: {
            "type": "pair_request",
            "api_key": "...",
            "ip": "192.168.0.15",
            "hostname": "webserver",
            "mac": "AA:BB:CC:DD:EE:FF",
            "group": "production-servers"
        }
        """
        api_key = data.get("api_key")
        ip_address = data.get("ip")
        hostname = data.get("hostname")
        mac_address = data.get("mac")
        group = data.get("group", "default")

        if not all([api_key, ip_address, hostname, mac_address]):
            await self.send_error("Missing required fields for pairing")
            return

        # FASE 1: Verifica API key
        api_verified = await self.verify_api_key(api_key)
        if not api_verified:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "pairing_status",
                        "status": "failed",
                        "phase": 1,
                        "error": "Invalid API key",
                    }
                )
            )
            return

        await self.send(
            text_data=json.dumps(
                {
                    "type": "pairing_status",
                    "status": "verifying",
                    "phase": 1,
                    "phase_1_verified": True,
                }
            )
        )

        # FASE 2: Verifica identity hash
        pairing_session = await self.verify_identity_hash(
            ip_address, hostname, mac_address, group
        )

        if pairing_session:
            # Pairing success!
            self.target = await self.get_target_by_session(pairing_session)

            # Crea/Aggiorna connessione
            self.connection = await self.create_connection(self.target)
            group_name = await self.get_target_group_name(self.target)

            await self.send(
                text_data=json.dumps(
                    {
                        "type": "pairing_status",
                        "status": "success",
                        "phase": 2,
                        "phase_1_verified": True,
                        "phase_2_verified": True,
                        "target_id": self.target.id,
                        "group": group_name,
                    }
                )
            )

            logger.info(f"Pairing successful for target {self.target}")

        else:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "pairing_status",
                        "status": "failed",
                        "phase": 2,
                        "error": "Identity hash verification failed",
                    }
                )
            )

    async def handle_heartbeat(self, data):
        """
        Gestisce heartbeat dall'agent
        Messaggio: {
            "type": "heartbeat",
            "timestamp": "2025-01-14T10:00:00Z",
            "system_stats": {
                "cpu_percent": 25.5,
                "memory_percent": 60.2,
                "disk_percent": 45.0,
                "bytes_sent": 1000000,
                "bytes_recv": 2000000,
                "active_rules_count": 15,
                "blocked_ips_count": 3
            }
        }
        """
        if not self.connection:
            await self.send_error("Not paired. Send pair_request first.")
            return

        system_stats = data.get("system_stats", {})

        # Aggiorna connection heartbeat
        await self.update_heartbeat(system_stats)

        # Salva heartbeat nel database (opzionale, per storico)
        await self.save_heartbeat(system_stats)

        # Invia ACK
        await self.send(
            text_data=json.dumps(
                {"type": "heartbeat_ack", "timestamp": timezone.now().isoformat()}
            )
        )

    async def handle_threat_log(self, data):
        """
        Gestisce log minacce dall'agent
        Messaggio: {
            "type": "threat_log",
            "threats": [
                {
                    "source_ip": "1.2.3.4",
                    "threat_score": 85,
                    "classification": "CRITICAL",
                    "attack_type": "port_scan",
                    "details": {...}
                }
            ]
        }
        """
        if not self.target:
            await self.send_error("Not paired")
            return

        threats = data.get("threats", [])

        for threat in threats:
            # Salva ThreatLog
            await self.save_threat_log(threat)

            # Crea alert se score >= 80
            if threat.get("threat_score", 0) >= 80:
                await self.create_threat_alert(threat)

        # Invia ACK
        await self.send(
            text_data=json.dumps({"type": "threat_ack", "count": len(threats)})
        )

    async def handle_command_response(self, data):
        """
        Gestisce risposta esecuzione comando
        Messaggio: {
            "type": "command_response",
            "command_id": "uuid",
            "status": "success" | "failed",
            "result": {...},
            "error": "..."
        }
        """
        command_id = data.get("command_id")
        command_status = data.get("status")
        result = data.get("result")
        error = data.get("error")

        if not command_id:
            await self.send_error("Missing command_id")
            return

        # Aggiorna comando
        await self.update_command_status(command_id, command_status, result, error)

    async def handle_firewall_stats(self, data):
        """
        Gestisce snapshot firewall+system inviato dall'agent.

        Il payload contiene il JSON prodotto da `firewall-manager --export-json`
        sul target. Lo persistiamo nel model FirewallStats per consultazione
        successiva via /api/firewall-stats/.

        Messaggio: {
            "type": "firewall_stats",
            "timestamp": "<rfc3339, wall-clock dell'agent al momento dell'invio>",
            "payload": { ...output di firewall-manager --export-json... }
        }
        """
        if not self.target:
            await self.send_error("Not paired. Send pair_request first.")
            return

        payload = data.get("payload") or {}
        if not isinstance(payload, dict):
            await self.send_error("firewall_stats: payload must be a JSON object")
            return

        try:
            await self.save_firewall_stats(payload)
        except Exception as e:
            logger.exception("firewall_stats save failed for target %s: %s", self.target.id, e)
            await self.send_error(f"firewall_stats save failed: {e}")
            return

        await self.send(text_data=json.dumps({"type": "firewall_stats_ack"}))

    async def send_command(self, event):
        """
        Invia comando all'agent (chiamato da channel layer)
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "command",
                    "command_id": event["command_id"],
                    "action": event["action"],
                    "payload": event["payload"],
                }
            )
        )

    async def disconnect_agent(self, event):
        """
        Forza disconnessione agent (chiamato da channel layer)
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "disconnect",
                    "reason": event.get("reason", "Server disconnect"),
                }
            )
        )
        await self.close()

    async def send_error(self, message):
        """
        Invia messaggio di errore all'agent
        """
        await self.send(text_data=json.dumps({"type": "error", "message": message}))

    # Database operations (async wrappers)

    @database_sync_to_async
    def verify_api_key(self, raw_key):
        """Verifica API key"""
        try:
            api_key = AgentAPIKey.objects.get(is_active=True)
            return api_key.verify_key(raw_key)
        except AgentAPIKey.DoesNotExist:
            return False

    @database_sync_to_async
    def verify_identity_hash(self, ip_address, hostname, mac_address, group="default"):
        """
        Verifica identity hash e trova sessione di pairing
        """
        import hashlib

        # Calcola identity hash
        identity_text = f"{ip_address}{hostname}{mac_address}"
        calculated_hash = hashlib.sha512(identity_text.encode()).hexdigest()

        # Trova target con questo hash
        try:
            target = Target.objects.get(identity_hash=calculated_hash)

            # Trova sessione di pairing attiva
            pairing_session = (
                PairingSession.objects.filter(
                    target=target,
                    status__in=["waiting", "verifying_api", "verifying_hash"],
                )
                .order_by("-created_at")
                .first()
            )

            if pairing_session and not pairing_session.is_expired:
                # Bootstrap pairing: marca la sessione come success
                pairing_session.phase_1_verified = True
                pairing_session.phase_2_verified = True
                pairing_session.status = "success"
                pairing_session.agent_ip = ip_address
                pairing_session.agent_hostname = hostname
                pairing_session.agent_mac = mac_address
                pairing_session.completed_at = timezone.now()
                pairing_session.save()

                target.status = "online"
                target.last_seen = timezone.now()
                target.save(update_fields=["status", "last_seen"])

                return pairing_session

            # Re-pair persistente: il target era già stato accoppiato in passato
            # (status != "unpaired"). Identity hash + API key bastano per ristabilire
            # la sessione WS senza richiedere una nuova PairingSession nel DB.
            if target.status != "unpaired":
                last_success = (
                    PairingSession.objects.filter(target=target, status="success")
                    .order_by("-completed_at")
                    .first()
                )
                if last_success:
                    target.status = "online"
                    target.last_seen = timezone.now()
                    target.save(update_fields=["status", "last_seen"])
                    return last_success

        except Target.DoesNotExist:
            logger.warning(f"No target found with identity hash: {calculated_hash}")

        return None

    @database_sync_to_async
    def get_target_by_session(self, session):
        """Ottiene target da sessione"""
        return session.target

    @database_sync_to_async
    def get_target_group_name(self, target):
        """Ritorna il nome del primo gruppo associato (o 'default')."""
        first_group = target.groups.first()
        return first_group.name if first_group else "default"

    @database_sync_to_async
    def create_connection(self, target):
        """Crea o aggiorna connessione agent"""
        connection, created = AgentConnection.objects.update_or_create(
            target=target,
            defaults={
                "websocket_channel": self.channel_name,
                "is_online": True,
                "last_heartbeat": timezone.now(),
            },
        )
        return connection

    @database_sync_to_async
    def update_heartbeat(self, system_stats):
        """Aggiorna heartbeat connection"""
        if self.connection:
            self.connection.update_heartbeat(system_stats)

    @database_sync_to_async
    def save_heartbeat(self, system_stats):
        """Salva heartbeat nello storico"""
        if self.target:
            AgentHeartbeat.objects.create(
                target=self.target,
                cpu_percent=system_stats.get("cpu_percent", 0),
                memory_percent=system_stats.get("memory_percent", 0),
                disk_percent=system_stats.get("disk_percent", 0),
                bytes_sent=system_stats.get("bytes_sent", 0),
                bytes_recv=system_stats.get("bytes_recv", 0),
                active_rules_count=system_stats.get("active_rules_count", 0),
                blocked_ips_count=system_stats.get("blocked_ips_count", 0),
                raw_data=system_stats,
            )

    @database_sync_to_async
    def save_firewall_stats(self, payload):
        """Persiste snapshot firewall+system in FirewallStats.

        Si attende la stessa shape prodotta da `firewall-manager --export-json`:
            {
              "hostname": str, "firedog_version": str,
              "system": {"os": str, "kernel": str, "uptime_seconds": int},
              "stats": {
                "total_packets": {"INPUT": int, "OUTPUT": int, "FORWARD": int},
                "pcap_sizes": {"input": int, "output": int}  # opzionale
              },
              "status": str, "timestamp": iso-8601
            }
        I campi mancanti finiscono ai default (0 / "").
        """
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone

        if not self.target:
            return

        system = payload.get("system") or {}
        stats = payload.get("stats") or {}
        total = stats.get("total_packets") or {}
        pcap = stats.get("pcap_sizes") or {}

        collected_at = parse_datetime(payload.get("timestamp") or "") or timezone.now()
        if timezone.is_naive(collected_at):
            collected_at = timezone.make_aware(collected_at, timezone.get_current_timezone())

        FirewallStats.objects.update_or_create(
            target=self.target,
            collected_at=collected_at,
            defaults={
                "hostname": payload.get("hostname", "") or "",
                "firedog_version": payload.get("firedog_version", "") or "",
                "os_version": system.get("os", "") or "",
                "kernel_version": system.get("kernel", "") or "",
                "uptime_seconds": int(system.get("uptime_seconds", 0) or 0),
                "input_packets": int(total.get("INPUT", 0) or 0),
                "output_packets": int(total.get("OUTPUT", 0) or 0),
                "forward_packets": int(total.get("FORWARD", 0) or 0),
                "pcap_input_dropped_bytes": int(pcap.get("input", 0) or 0),
                "pcap_output_dropped_bytes": int(pcap.get("output", 0) or 0),
                "status": payload.get("status", "healthy") or "healthy",
                "raw_json": payload,
            },
        )

    @database_sync_to_async
    def save_threat_log(self, threat):
        """Salva threat log"""
        if self.target:
            ThreatLog.objects.create(
                target=self.target,
                source_ip=threat.get("source_ip"),
                threat_score=threat.get("threat_score", 0),
                classification=threat.get("classification", "MEDIUM"),
                attack_type=threat.get("attack_type", "unknown"),
                details=threat.get("details", {}),
            )

    @database_sync_to_async
    def create_threat_alert(self, threat):
        """Crea alert per minaccia critica"""
        if self.target:
            Alert.objects.create(
                target=self.target,
                severity="critical",
                title=f"Critical Threat Detected: {threat.get('attack_type', 'Unknown')}",
                message=f"Source IP: {threat.get('source_ip')} - Threat Score: {threat.get('threat_score')}",
            )

    @database_sync_to_async
    def update_command_status(self, command_id, command_status, result, error):
        """Aggiorna status comando"""
        try:
            command = AgentCommand.objects.get(command_id=command_id)

            if command_status == "success":
                command.mark_success(result)
            elif command_status == "failed":
                command.mark_failed(error or "Unknown error")
            elif command_status == "executing":
                command.mark_executing()

        except AgentCommand.DoesNotExist:
            logger.error(f"Command not found: {command_id}")

    @database_sync_to_async
    def mark_connection_offline(self):
        """Marca connessione come offline"""
        if self.connection:
            self.connection.mark_offline()

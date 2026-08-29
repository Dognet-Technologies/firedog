"""
WebSocket Consumer per comunicazione con dog-agent
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.db import models
from django.utils import timezone
from .models import (
    AgentAPIKey,
    PairingSession,
    AgentConnection,
    AgentCommand,
    AgentHeartbeat,
)
from targets.models import Target, Alert, FirewallStats, BlockedIP
from threats.models import ThreatLog
from rules.models import FirewallRule

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
        # L'agent Rust serializza il campo come `output` (CommandResponse struct);
        # supportiamo entrambi i nomi per retro-compat.
        result = data.get("result") if data.get("result") is not None else data.get("output")
        error = data.get("error")

        if not command_id:
            await self.send_error("Missing command_id")
            return

        # Side-effect: se la risposta di sync_rules contiene il JSON snapshot
        # di firewall-manager --export-json, ingestialo nelle tabelle come
        # se fosse un firewall_stats — la UI vede le rule fresh subito.
        if command_status == "success" and isinstance(result, str):
            await self._maybe_ingest_sync_rules_output(command_id, result)

        # Aggiorna comando
        await self.update_command_status(command_id, command_status, result, error)

    async def _maybe_ingest_sync_rules_output(self, command_id, output_str):
        """Se il comando era 'sync_rules' e l'agent ha rispedito il JSON
        completo di firewall-manager --export-json nell'output, lo ingestiamo
        nelle stesse tabelle che firewall_stats popola. Così la UI vede le
        rules aggiornate subito dopo il click di "Sync Rules".
        """
        cmd = await self._get_command(command_id)
        if not cmd or cmd.action != "sync_rules":
            return
        try:
            payload = json.loads(output_str)
        except (TypeError, ValueError):
            logger.debug("sync_rules: output non è JSON, skip ingestion")
            return
        if not isinstance(payload, dict):
            return
        # Forza self.target sulla destinazione del comando (handle_command_response
        # NON ha lo stesso target del consumer in tutti i casi: il consumer è
        # legato all'agent che ha risposto, che è il target di destinazione).
        await self.save_firewall_stats(payload)

    @database_sync_to_async
    def _get_command(self, command_id):
        from .models import AgentCommand as _AC
        return _AC.objects.filter(command_id=command_id).first()

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
        """Salva heartbeat nello storico, popolando anche le metriche assolute
        (memory/disk KB, load_avg, uptime) così la UI non deve più derivarle.
        """
        if not self.target:
            return
        load = system_stats.get("load_avg") or [0, 0, 0]
        # load_avg arriva come [1m, 5m, 15m]; tollera anche valori mancanti
        try:
            load_1m = float(load[0]) if len(load) > 0 else 0.0
            load_5m = float(load[1]) if len(load) > 1 else 0.0
            load_15m = float(load[2]) if len(load) > 2 else 0.0
        except (TypeError, ValueError):
            load_1m = load_5m = load_15m = 0.0

        AgentHeartbeat.objects.create(
            target=self.target,
            cpu_percent=system_stats.get("cpu_percent", 0) or 0,
            memory_percent=system_stats.get("memory_percent", 0) or 0,
            disk_percent=system_stats.get("disk_percent", 0) or 0,
            memory_total_kb=int(system_stats.get("memory_total_kb", 0) or 0),
            memory_used_kb=int(system_stats.get("memory_used_kb", 0) or 0),
            disk_total_kb=int(system_stats.get("disk_total_kb", 0) or 0),
            disk_used_kb=int(system_stats.get("disk_used_kb", 0) or 0),
            load_avg_1m=load_1m,
            load_avg_5m=load_5m,
            load_avg_15m=load_15m,
            uptime_seconds=int(system_stats.get("uptime_seconds", 0) or 0),
            bytes_sent=int(system_stats.get("bytes_sent", 0) or 0),
            bytes_recv=int(system_stats.get("bytes_recv", 0) or 0),
            active_rules_count=int(system_stats.get("active_rules_count", 0) or 0),
            blocked_ips_count=int(system_stats.get("blocked_ips_count", 0) or 0),
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
        # `dropped` è il dict con i counter delle chain LOG_INPUT_DROP /
        # LOG_OUTPUT_DROP (aggiunto a firewall-manager --export-json). Quando
        # il firewall non è inizializzato la chain non esiste e i counter sono 0.
        dropped = stats.get("dropped") or {}

        collected_at = parse_datetime(payload.get("timestamp") or "") or timezone.now()
        # Difensivo: timestamp dell'agent senza TZ info viene trattato come
        # UTC (i target Linux registrano ora UTC by default). Prima veniva
        # marcato come Europe/Rome dal middleware Django → 2h di shift al DB.
        if timezone.is_naive(collected_at):
            collected_at = timezone.make_aware(collected_at, timezone.utc)

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
                "dropped_input_packets": int(dropped.get("input", 0) or 0),
                "dropped_output_packets": int(dropped.get("output", 0) or 0),
                # Counter per protocollo da /proc/net/snmp. Validati a un dict
                # per evitare di salvare tipi inattesi (es. None).
                "protocols": payload.get("protocols") if isinstance(payload.get("protocols"), dict) else {},
                # Conntrack: snapshot istantaneo (non delta).
                "conntrack_count": int((payload.get("conntrack") or {}).get("count", 0) or 0),
                "conntrack_max":   int((payload.get("conntrack") or {}).get("max", 0) or 0),
                "status": payload.get("status", "healthy") or "healthy",
                "raw_json": payload,
            },
        )

        # FirewallStats.firedog_version (sopra) non si riflette da solo su
        # Target.firedog_version: sono due modelli distinti e nessun altro
        # punto del codice li sincronizza per il percorso basato su agent
        # (la UI Targets legge Target.firedog_version, non FirewallStats).
        # Senza questo, un target online e perfettamente funzionante mostra
        # sempre "Not installed" in tabella.
        new_version = payload.get("firedog_version") or ""
        if new_version and self.target.firedog_version != new_version:
            self.target.firedog_version = new_version
            self.target.save(update_fields=["firedog_version"])

        # Estensioni: stessa snapshot popola anche regole, IP bloccati e threat log.
        # Ogni helper è sincrono e gira dentro lo stesso wrapper async.
        self._sync_firewall_rules(payload.get("rules") or {})
        self._sync_blocked_ips(payload.get("rules") or {})
        self._sync_threat_log(payload.get("threats") or [])
        self._sync_network_flows(payload.get("network_flows") or [])

    def _sync_network_flows(self, flows):
        """Upsert dei flussi network (peer IP pubblici) ingestiti dall'agent.

        Schema input (ogni elemento): {ip, count, ports}.
        - times_seen incrementato di `count` (snapshot rolling)
        - country_code/name popolato via geoip2 al primo lookup, riconfermato
          se vuoto (per gestire DB aggiunto/sostituito dopo)
        - last_ports unisce le ultime porte viste, max 10 elementi
        """
        from .models import Target  # noqa
        from targets.models import NetworkFlow
        from api.geoip import lookup_country

        if not isinstance(flows, list) or not self.target:
            return

        for flow in flows:
            if not isinstance(flow, dict):
                continue
            ip = flow.get("ip")
            if not ip:
                continue
            count = int(flow.get("count", 0) or 0)
            ports = flow.get("ports") or []
            if not isinstance(ports, list):
                ports = []

            obj, _created = NetworkFlow.objects.get_or_create(
                target=self.target, remote_ip=ip,
                defaults={"times_seen": 0, "last_ports": []},
            )
            obj.times_seen = (obj.times_seen or 0) + max(1, count)

            # Merge ports (set-like, max 10)
            merged = list(obj.last_ports or [])
            for p in ports:
                if isinstance(p, int) and p not in merged:
                    merged.append(p)
            obj.last_ports = merged[-10:]

            # GeoIP lookup se non già fatto
            if not obj.country_code:
                cc, name = lookup_country(ip)
                obj.country_code = cc
                obj.country_name = name

            obj.save()

    def _sync_firewall_rules(self, rules_by_chain):
        """Sincronizza la tabella FirewallRule con lo snapshot ricevuto.

        Per ogni chain (INPUT/OUTPUT/FORWARD) fa upsert sulle regole presenti
        nel payload (chiave = target+chain+rule_number) ed elimina quelle
        non-custom rimaste fuori dallo snapshot (le custom create dalla UI
        restano intoccate finché non risultano sincronizzate).
        """
        import re as _re

        valid_chains = {"INPUT", "OUTPUT", "FORWARD"}
        valid_actions = {"ACCEPT", "DROP", "REJECT"}
        valid_protos = {"tcp", "udp", "icmp", "all"}
        # iptables -L -n stampa i protocolli come numero (es. "1" per ICMP)
        # quando non riconosce il nome short. Mappiamo i casi comuni così la
        # dedup-logic (che confronta `protocol`) combacia con le rule create
        # dalla UI che usano "icmp"/"tcp"/"udp".
        proto_number_to_name = {"1": "icmp", "6": "tcp", "17": "udp", "0": "all"}

        for chain, rules in (rules_by_chain or {}).items():
            if chain not in valid_chains or not isinstance(rules, list):
                continue

            seen_rule_numbers = []
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                action = (rule.get("target") or "").upper()
                if action not in valid_actions:
                    # Target è una chain custom (es. SSH_PROTECT, ICMP_FLOOD):
                    # non rappresentabile come FirewallRule "classica", skip.
                    continue

                proto = (rule.get("prot") or "all").lower()
                proto = proto_number_to_name.get(proto, proto)
                if proto not in valid_protos:
                    proto = "all"

                # Estrai porta da `extra` (es. "tcp dpt:22"). Fallback su None.
                port = None
                extra = rule.get("extra") or ""
                m = _re.search(r"dpt:(\d+)", extra)
                if m:
                    try:
                        p = int(m.group(1))
                        if 1 <= p <= 65535:
                            port = p
                    except ValueError:
                        pass

                source_ip = rule.get("source") or ""
                if source_ip in ("0.0.0.0/0", "::/0", "anywhere", ""):
                    source_ip = None
                else:
                    source_ip = source_ip.split("/")[0]  # CIDR → host part

                dest_ip = rule.get("destination") or ""
                if dest_ip in ("0.0.0.0/0", "::/0", "anywhere", ""):
                    dest_ip = None
                else:
                    dest_ip = dest_ip.split("/")[0]

                rule_number = rule.get("num") or 0
                if rule_number <= 0:
                    continue
                seen_rule_numbers.append(rule_number)

                # Dedup: se esiste già una rule creata dalla UI (is_custom=True)
                # che combacia con questa snapshot, la usiamo invece di crearne
                # una nuova non-custom. Riconciliazione su signature:
                # (chain, action, protocol, port, source_ip, dest_ip).
                # NB: source/dest sono normalizzate (CIDR stripped) per il match,
                # quindi se l'utente ha inserito "10.0.0.0/24" e l'agent vede
                # l'host "10.0.0.0", il match avviene comunque.
                custom_match = (
                    FirewallRule.objects.filter(
                        target=self.target,
                        chain=chain,
                        action=action,
                        protocol=proto,
                        port=port,
                        source_ip=source_ip,
                        dest_ip=dest_ip,
                        is_custom=True,
                    )
                    # Preferisci quella che ha già lo stesso rule_number, poi
                    # quelle synced (già applicate), poi le più recenti.
                    .order_by(
                        models.Case(
                            models.When(rule_number=rule_number, then=0),
                            default=1,
                            output_field=models.IntegerField(),
                        ),
                        "-is_synced",
                        "-updated_at",
                    )
                    .first()
                )

                if custom_match:
                    # Aggiorna in-place senza creare un duplicato non-custom.
                    custom_match.rule_number = rule_number
                    custom_match.is_synced = True
                    if rule.get("comment") and not custom_match.comment:
                        custom_match.comment = (rule.get("comment") or "")[:256]
                    custom_match.save(update_fields=["rule_number", "is_synced", "comment", "updated_at"])
                    # Cleanup retroattivo: rimuovi eventuali duplicati non-custom
                    # creati prima che la dedup-logic fosse attiva.
                    FirewallRule.objects.filter(
                        target=self.target,
                        chain=chain,
                        rule_number=rule_number,
                        is_custom=False,
                    ).exclude(id=custom_match.id).delete()
                    continue

                # Rilevamento marker "[group:NAME]": se il commento iptables
                # contiene quel prefisso, la rule è "applicata da un gruppo".
                # Cerchiamo il TargetGroup omonimo per popolare group_origin
                # (utile quando la rule è stata creata fuori dalla UI, es. da
                # un altro admin via firewall-manager, ma marcata con la stessa
                # convenzione).
                from targets.models import TargetGroup
                group_origin = None
                raw_comment = (rule.get("comment") or "")
                m_grp = _re.match(r"^\[group:([^\]]+)\]", raw_comment)
                if m_grp:
                    group_name = m_grp.group(1).strip()
                    group_origin = TargetGroup.objects.filter(name=group_name).first()

                FirewallRule.objects.update_or_create(
                    target=self.target,
                    chain=chain,
                    rule_number=rule_number,
                    defaults={
                        "protocol": proto,
                        "port": port,
                        "source_ip": source_ip,
                        "dest_ip": dest_ip,
                        "action": action,
                        "comment": raw_comment[:256],
                        "is_custom": False,
                        "is_synced": True,
                        "group_origin": group_origin,
                    },
                )

            # Rimuovi regole non-custom della chain che non sono più presenti
            # nell'ultima snapshot. Le regole custom (create dalla UI) restano
            # intoccate: se la rule è scomparsa lato target, il loro
            # is_synced=True diventa "informazione storica" finché l'admin non
            # decide cosa farne — meglio non eliminarle silenziosamente.
            FirewallRule.objects.filter(
                target=self.target,
                chain=chain,
                is_custom=False,
            ).exclude(rule_number__in=seen_rule_numbers).delete()

    def _sync_blocked_ips(self, rules_by_chain):
        """Deriva BlockedIP dalle regole DROP con un source/destination specifico.

        Politica:
          - INPUT  DROP  -s X  → X è bloccato in ingresso
          - OUTPUT DROP  -d X  → X è bloccato in uscita

        Gli IP osservati vengono upsert-ati con blocked_by="agent-snapshot"; quelli
        che erano in questo set ma non sono più presenti nell'ultima snapshot
        vengono marcati is_active=False (NON eliminati — utile per audit).
        Le entry create dalla UI (blocked_by≠"agent-snapshot") non vengono toccate.
        """
        observed_ips: set[str] = set()

        for chain, rules in (rules_by_chain or {}).items():
            if chain not in {"INPUT", "OUTPUT"} or not isinstance(rules, list):
                continue
            for rule in rules:
                if (rule.get("target") or "").upper() != "DROP":
                    continue
                ip_field = "source" if chain == "INPUT" else "destination"
                ip = rule.get(ip_field) or ""
                if ip in ("0.0.0.0/0", "::/0", "anywhere", ""):
                    continue
                ip = ip.split("/")[0]
                observed_ips.add(ip)

                BlockedIP.objects.update_or_create(
                    target=self.target,
                    ip_address=ip,
                    defaults={
                        "block_reason": "manual",
                        "description": (rule.get("comment") or f"iptables DROP {chain}")[:512],
                        "blocked_by": "agent-snapshot",
                        "packet_count": int(rule.get("pkts") or 0),
                        "is_active": True,
                    },
                )

        BlockedIP.objects.filter(
            target=self.target, blocked_by="agent-snapshot", is_active=True,
        ).exclude(ip_address__in=observed_ips).update(is_active=False)

    def _sync_threat_log(self, threats):
        """Aggiorna ThreatLog dai dati threat estratti dal pcap input_dropped.

        Schema atteso per ciascun threat: {ip, score, attempts, reasons[]}.
        Per evitare bloat, fa update_or_create su (target, source_ip, is_resolved=False):
        un nuovo evento per lo stesso IP aggiorna lo score e il contatore;
        se l'amministratore ha marcato il threat come `is_resolved=True` viene
        creato un nuovo record.
        """
        if not isinstance(threats, list):
            return

        for t in threats:
            if not isinstance(t, dict):
                continue
            ip = t.get("ip")
            if not ip:
                continue
            try:
                score = max(0, min(100, int(t.get("score", 0) or 0)))
            except (TypeError, ValueError):
                continue

            if score >= 80:
                severity = "critical"
            elif score >= 60:
                severity = "high"
            elif score >= 40:
                severity = "medium"
            else:
                severity = "low"

            reasons = t.get("reasons") or []
            if not isinstance(reasons, list):
                reasons = [str(reasons)]

            attempts = int(t.get("attempts", 1) or 1)

            # Protocol/dest_port estratti dal pcap dal lato target.
            # Mancano per record vecchi (pre-arricchimento) e per ICMP (no port).
            proto = (t.get("protocol") or "").lower()
            if proto not in ("tcp", "udp", "icmp", ""):
                proto = ""
            try:
                dest_port = int(t.get("dest_port")) if t.get("dest_port") is not None else None
            except (TypeError, ValueError):
                dest_port = None

            ThreatLog.objects.update_or_create(
                target=self.target,
                source_ip=ip,
                is_resolved=False,
                defaults={
                    "threat_score": score,
                    "severity": severity,
                    "packet_count": attempts,
                    "reasons": reasons,
                    "description": ", ".join(str(r) for r in reasons)[:512],
                    "protocol": proto,
                    "dest_port": dest_port,
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
        """Aggiorna status comando + riconcilia oggetti DB tramite payload._meta."""
        try:
            command = AgentCommand.objects.get(command_id=command_id)

            if command_status == "success":
                command.mark_success(result)
                self._reconcile_command_meta(command)
            elif command_status == "failed":
                command.mark_failed(error or "Unknown error")
            elif command_status == "executing":
                command.mark_executing()

        except AgentCommand.DoesNotExist:
            logger.error(f"Command not found: {command_id}")

    def _reconcile_command_meta(self, command):
        """Mark referenced DB objects as synced when the agent confirms success.

        Riconosce:
          - add_rule  → FirewallRule.is_synced = True (via _meta.rule_id)
          - remove_rule → FirewallRule.objects.filter(id=rule_id).delete()
          - block_ip   → BlockedIP.is_active = True
        """
        meta = (command.payload or {}).get("_meta") or {}
        if not meta:
            return
        action = command.action

        if action == "add_rule" and meta.get("rule_id"):
            FirewallRule.objects.filter(id=meta["rule_id"]).update(is_synced=True)
        elif action == "remove_rule" and meta.get("rule_id"):
            FirewallRule.objects.filter(id=meta["rule_id"]).delete()
        elif action == "block_ip" and meta.get("blocked_ip_id"):
            BlockedIP.objects.filter(id=meta["blocked_ip_id"]).update(is_active=True)

    @database_sync_to_async
    def mark_connection_offline(self):
        """Marca connessione come offline"""
        if self.connection:
            self.connection.mark_offline()

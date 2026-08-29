"""
Django Management Command - Import Targets Status from JSON
Importa i file JSON di stato nel database Django
"""

import json
import logging
from pathlib import Path
from dateutil import parser as date_parser
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from targets.models import Target, FirewallStats
from rules.models import FirewallRule
from threats.models import ThreatLog

logger = logging.getLogger("firedog.import_status")


class Command(BaseCommand):
    help = "Importa file JSON di stato nel database Django"

    def add_arguments(self, parser):
        parser.add_argument(
            "--target-id",
            type=int,
            help="Importa solo da un singolo target (opzionale)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula operazione senza salvare nel DB",
        )
        parser.add_argument(
            "--skip-rules",
            action="store_true",
            help="Skip import regole firewall",
        )
        parser.add_argument(
            "--skip-threats",
            action="store_true",
            help="Skip import minacce",
        )

    def handle(self, *args, **options):
        """Main entry point"""

        target_id = options.get("target_id")
        dry_run = options.get("dry_run")
        skip_rules = options.get("skip_rules")
        skip_threats = options.get("skip_threats")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - Nessun dato verrà salvato nel DB")
            )

        # Base directory
        data_dir = Path(settings.FIREDOG_DATA_DIR)

        if not data_dir.exists():
            self.stdout.write(
                self.style.ERROR(f"Directory dati non trovata: {data_dir}")
            )
            return

        # Ottieni targets
        if target_id:
            targets = Target.objects.filter(id=target_id)
            if not targets.exists():
                self.stdout.write(self.style.ERROR(f"Target {target_id} non trovato"))
                return
        else:
            targets = Target.objects.all()

        self.stdout.write(f"Import status per {targets.count()} target...\n")

        success_count = 0
        error_count = 0
        skipped_count = 0

        for target in targets:
            try:
                result = self.import_target_status(
                    target, data_dir, dry_run, skip_rules, skip_threats
                )
                if result == "success":
                    success_count += 1
                elif result == "skipped":
                    skipped_count += 1
                else:
                    error_count += 1
            except Exception as e:
                logger.exception(f"Errore import target {target.id}: {e}")
                self.stdout.write(self.style.ERROR(f"  ✗ {target.hostname}: {str(e)}"))
                error_count += 1

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"✓ Import riusciti: {success_count}"))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f"⊘ Skipped: {skipped_count}"))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"✗ Errori: {error_count}"))
        self.stdout.write("=" * 60 + "\n")

    def import_target_status(
        self, target, data_dir, dry_run=False, skip_rules=False, skip_threats=False
    ):
        """
        Importa status JSON per un singolo target

        Args:
            target: Target instance
            data_dir: Path to data directory
            dry_run: Se True, simula operazione
            skip_rules: Se True, skip import regole
            skip_threats: Se True, skip import minacce

        Returns:
            str: 'success', 'skipped', or 'error'
        """

        hostname = target.hostname or f"target-{target.id}"

        # Cerca file JSON (può essere in vari percorsi)
        possible_paths = [
            data_dir / "groups" / "default" / hostname / "status.json",
        ]

        # Se il target ha un gruppo, cerca anche lì
        if hasattr(target, "group") and target.group:
            possible_paths.insert(
                0, data_dir / "groups" / target.group.name / hostname / "status.json"
            )

        json_path = None
        for path in possible_paths:
            if path.exists():
                json_path = path
                break

        if not json_path:
            self.stdout.write(f"  ⊘ {hostname}: Nessun file JSON trovato")
            return "skipped"

        self.stdout.write(f"  → {hostname} ({target.ip_address})")

        try:
            # Leggi e valida JSON
            with open(json_path, "r") as f:
                data = json.load(f)

            # Validazione base sicurezza
            if not self.validate_json_data(data):
                self.stdout.write(
                    self.style.ERROR(f"    ✗ JSON non valido o non sicuro")
                )
                return "error"

            if dry_run:
                self.stdout.write(
                    f'    [DRY RUN] JSON validato: {len(data.get("rules", {}).get("INPUT", []))} INPUT rules'
                )
                return "success"

            # Import con transaction atomica
            with transaction.atomic():
                # Parse timestamp
                timestamp_str = data.get("timestamp")
                try:
                    collected_at = date_parser.isoparse(timestamp_str)
                except Exception:
                    collected_at = timezone.now()

                # Verifica se già importato
                if FirewallStats.objects.filter(
                    target=target, collected_at=collected_at
                ).exists():
                    self.stdout.write(
                        self.style.WARNING(f"    ⊘ Già importato: {collected_at}")
                    )
                    return "skipped"

                # Import statistiche
                self.import_stats(target, data, collected_at)

                # Import regole (se non skipped)
                rules_count = 0
                if not skip_rules:
                    rules_count = self.import_rules(target, data)

                # Import minacce (se non skipped)
                threats_count = 0
                if not skip_threats:
                    threats_count = self.import_threats(target, data)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"    ✓ Import OK: {rules_count} rules, {threats_count} threats"
                    )
                )

                logger.info(
                    f"Imported target {target.id} status: {rules_count} rules, {threats_count} threats"
                )

                return "success"

        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f"    ✗ JSON non valido: {str(e)}"))
            return "error"
        except Exception as e:
            logger.exception(f"Error importing target {target.id}: {e}")
            self.stdout.write(self.style.ERROR(f"    ✗ Errore: {str(e)}"))
            return "error"

    def validate_json_data(self, data):
        """
        Valida JSON per sicurezza

        Checks:
        - Struttura base corretta
        - Nessun campo pericoloso
        - Dimensioni ragionevoli

        Returns:
            bool: True se valido
        """
        if not isinstance(data, dict):
            return False

        # Campi required
        required_fields = ["hostname", "ip_address", "timestamp"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"Missing required field: {field}")
                return False

        # Limiti dimensioni (anti-DoS)
        rules = data.get("rules", {})
        total_rules = sum(
            len(rules.get(chain, [])) for chain in ["INPUT", "OUTPUT", "FORWARD"]
        )
        if total_rules > 10000:  # Max 10k regole
            logger.warning(f"Too many rules: {total_rules}")
            return False

        threats = data.get("threats", [])
        if len(threats) > 1000:  # Max 1k minacce per import
            logger.warning(f"Too many threats: {len(threats)}")
            return False

        return True

    def import_stats(self, target, data, collected_at):
        """Import statistiche firewall"""

        system_info = data.get("system", {})
        stats_info = data.get("stats", {})
        pcap_sizes = stats_info.get("pcap_sizes", {})
        total_packets = stats_info.get("total_packets", {})

        stats = FirewallStats.objects.create(
            target=target,
            hostname=self.sanitize_string(data.get("hostname", ""))[:255],
            firedog_version=self.sanitize_string(data.get("firedog_version", ""))[:50],
            os_version=self.sanitize_string(system_info.get("os", ""))[:255],
            kernel_version=self.sanitize_string(system_info.get("kernel", ""))[:255],
            uptime_seconds=self.sanitize_int(system_info.get("uptime_seconds", 0)),
            input_packets=self.sanitize_int(total_packets.get("INPUT", 0)),
            output_packets=self.sanitize_int(total_packets.get("OUTPUT", 0)),
            forward_packets=self.sanitize_int(total_packets.get("FORWARD", 0)),
            pcap_input_dropped_bytes=self.sanitize_int(
                pcap_sizes.get("input_dropped_bytes", 0)
            ),
            pcap_output_dropped_bytes=self.sanitize_int(
                pcap_sizes.get("output_dropped_bytes", 0)
            ),
            status=self.sanitize_string(data.get("status", "healthy"))[:50],
            collected_at=collected_at,
            raw_json=data,  # Salva JSON completo per debug
        )

        return stats

    def import_rules(self, target, data):
        """Import regole firewall"""

        rules_data = data.get("rules", {})
        imported_count = 0

        for chain in ["INPUT", "OUTPUT", "FORWARD"]:
            chain_rules = rules_data.get(chain, [])

            for rule_data in chain_rules:
                # Skip regole di sistema (numero 0 o target non ACCEPT/DROP/REJECT)
                if rule_data.get("num", 0) == 0:
                    continue

                target_action = self.sanitize_string(rule_data.get("target", ""))
                if target_action not in ["ACCEPT", "DROP", "REJECT"]:
                    continue

                # Crea o aggiorna regola
                try:
                    # Estrai porta dal campo 'extra'
                    port = None
                    extra = rule_data.get("extra", "")
                    if "dpt:" in extra:
                        import re

                        match = re.search(r"dpt:(\d+)", extra)
                        if match:
                            port = int(match.group(1))

                    # Crea regola (o update se esiste)
                    rule, created = FirewallRule.objects.update_or_create(
                        target=target,
                        chain=chain,
                        rule_number=self.sanitize_int(rule_data.get("num", 0)),
                        defaults={
                            "protocol": self.sanitize_string(
                                rule_data.get("prot", "tcp")
                            )[:10],
                            "port": port,
                            "source_ip": self.sanitize_ip(rule_data.get("source")),
                            "dest_ip": self.sanitize_ip(rule_data.get("destination")),
                            "action": target_action[:10],
                            "comment": self.sanitize_string(
                                rule_data.get("comment", "")
                            )[:256],
                            "is_custom": False,  # Regole importate sono considerate non-custom
                            "is_synced": True,  # Sono sincronizzate dal target
                        },
                    )

                    if created:
                        imported_count += 1

                except Exception as e:
                    logger.warning(f"Failed to import rule: {e}")
                    continue

        return imported_count

    def import_threats(self, target, data):
        """Import minacce rilevate"""

        threats_data = data.get("threats", [])
        imported_count = 0

        for threat_data in threats_data:
            try:
                source_ip = self.sanitize_ip(threat_data.get("ip"))
                if not source_ip:
                    continue

                threat_score = self.sanitize_int(threat_data.get("score", 0))
                attempts = self.sanitize_int(threat_data.get("attempts", 0))
                reasons = threat_data.get("reasons", [])

                # Calcola severity
                if threat_score >= 80:
                    severity = "critical"
                elif threat_score >= 60:
                    severity = "high"
                elif threat_score >= 30:
                    severity = "medium"
                else:
                    severity = "low"

                # Crea threat log
                threat, created = ThreatLog.objects.get_or_create(
                    target=target,
                    source_ip=source_ip,
                    threat_score=threat_score,
                    detected_at__gte=timezone.now()
                    - timezone.timedelta(hours=1),  # Evita duplicati recenti
                    defaults={
                        "packet_count": attempts,
                        "reasons": reasons if isinstance(reasons, list) else [],
                        "severity": severity,
                        "protocol": "tcp",  # Default
                        "description": f"Threat detected with score {threat_score}",
                    },
                )

                if created:
                    imported_count += 1

            except Exception as e:
                logger.warning(f"Failed to import threat: {e}")
                continue

        return imported_count

    # Funzioni di sanitizzazione per sicurezza

    @staticmethod
    def sanitize_string(value):
        """Sanitizza stringa per prevenire injection"""
        if not isinstance(value, str):
            return ""
        # Remove null bytes e caratteri di controllo
        return value.replace("\x00", "").strip()

    @staticmethod
    def sanitize_int(value):
        """Sanitizza integer"""
        try:
            val = int(value)
            # Limita a valori ragionevoli
            return max(0, min(val, 2**63 - 1))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def sanitize_ip(value):
        """Sanitizza e valida IP address"""
        if not value or value == "0.0.0.0/0" or value == "::/0":
            return None

        # Rimuovi CIDR notation se presente
        if "/" in value:
            value = value.split("/")[0]

        # Valida IP
        import ipaddress

        try:
            ip = ipaddress.ip_address(value)
            return str(ip)
        except ValueError:
            return None

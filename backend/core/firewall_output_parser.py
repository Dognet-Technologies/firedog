"""
Parser per output testuale di firewall-manager.py

Questo modulo converte l'output testuale (con colori ANSI) dei comandi
firewall-manager in dizionari Python strutturati.
"""

import re
from typing import Dict, List, Optional
import logging

logger = logging.getLogger("firedog.parser")


class FirewallOutputParser:
    """Parser per output firewall-manager.py"""

    # Pattern ANSI color codes per rimuoverli
    ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    @classmethod
    def remove_ansi_codes(cls, text: str) -> str:
        """Rimuove codici colore ANSI dal testo"""
        return cls.ANSI_ESCAPE.sub("", text)

    @classmethod
    def parse_stats(cls, output: str) -> Optional[Dict]:
        """
        Parse output di: firewall-manager --stats

        Output esempio:
        ╔════════════════════════════════════════════════════════════════╗
        ║              STATISTICHE FIREWALL                             ║
        ╚════════════════════════════════════════════════════════════════╝

        📊 PACCHETTI
        ├─ INPUT:  123456 pacchetti (98765 MB)
        │  └─ Dropped: 1234 (1.00%)
        └─ OUTPUT: 98765 pacchetti (54321 MB)
           └─ Dropped: 123 (0.12%)

        📁 FILE PCAP
        ├─ INPUT:  45.2 MB (/var/log/ulogd/input_dropped.pcap)
        └─ OUTPUT: 12.3 MB (/var/log/ulogd/output_dropped.pcap)

        Returns:
            Dict con chiavi:
            {
                'input_packets': int,
                'input_bytes': int,
                'input_dropped': int,
                'input_dropped_percent': float,
                'output_packets': int,
                'output_bytes': int,
                'output_dropped': int,
                'output_dropped_percent': float,
                'pcap_input_size': int (bytes),
                'pcap_output_size': int (bytes)
            }
        """
        try:
            clean_output = cls.remove_ansi_codes(output)

            stats = {
                "input_packets": 0,
                "input_bytes": 0,
                "input_dropped": 0,
                "input_dropped_percent": 0.0,
                "output_packets": 0,
                "output_bytes": 0,
                "output_dropped": 0,
                "output_dropped_percent": 0.0,
                "pcap_input_size": 0,
                "pcap_output_size": 0,
            }

            # Parse INPUT packets
            input_match = re.search(
                r"INPUT:\s+(\d+)\s+pacchetti\s+\((\d+(?:\.\d+)?)\s*([KMG]?B)\)",
                clean_output,
            )
            if input_match:
                stats["input_packets"] = int(input_match.group(1))
                stats["input_bytes"] = cls._convert_size_to_bytes(
                    float(input_match.group(2)), input_match.group(3)
                )

            # Parse INPUT dropped
            input_dropped_match = re.search(
                r"INPUT:.*?Dropped:\s*(\d+)\s+\((\d+(?:\.\d+)?)%\)",
                clean_output,
                re.DOTALL,
            )
            if input_dropped_match:
                stats["input_dropped"] = int(input_dropped_match.group(1))
                stats["input_dropped_percent"] = float(input_dropped_match.group(2))

            # Parse OUTPUT packets
            output_match = re.search(
                r"OUTPUT:\s+(\d+)\s+pacchetti\s+\((\d+(?:\.\d+)?)\s*([KMG]?B)\)",
                clean_output,
            )
            if output_match:
                stats["output_packets"] = int(output_match.group(1))
                stats["output_bytes"] = cls._convert_size_to_bytes(
                    float(output_match.group(2)), output_match.group(3)
                )

            # Parse OUTPUT dropped
            output_dropped_match = re.search(
                r"OUTPUT:.*?Dropped:\s*(\d+)\s+\((\d+(?:\.\d+)?)%\)",
                clean_output,
                re.DOTALL,
            )
            if output_dropped_match:
                stats["output_dropped"] = int(output_dropped_match.group(1))
                stats["output_dropped_percent"] = float(output_dropped_match.group(2))

            # Parse PCAP INPUT size
            pcap_input_match = re.search(
                r"INPUT:\s+(\d+(?:\.\d+)?)\s*([KMG]?B)\s+\(/var/log/ulogd/input",
                clean_output,
            )
            if pcap_input_match:
                stats["pcap_input_size"] = cls._convert_size_to_bytes(
                    float(pcap_input_match.group(1)), pcap_input_match.group(2)
                )

            # Parse PCAP OUTPUT size
            pcap_output_match = re.search(
                r"OUTPUT:\s+(\d+(?:\.\d+)?)\s*([KMG]?B)\s+\(/var/log/ulogd/output",
                clean_output,
            )
            if pcap_output_match:
                stats["pcap_output_size"] = cls._convert_size_to_bytes(
                    float(pcap_output_match.group(1)), pcap_output_match.group(2)
                )

            logger.debug(f"Stats parsed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Errore parsing stats: {e}")
            return None

    @classmethod
    def parse_rules(cls, output: str, chain: Optional[str] = None) -> List[Dict]:
        """
        Parse output di: firewall-manager --list [CHAIN]

        Output esempio:
        ╔══════════════════════════════════════════════════════════════════════════════╗
        ║                          REGOLE FIREWALL - INPUT                             ║
        ╚══════════════════════════════════════════════════════════════════════════════╝

        Chain INPUT (policy DROP 1234 packets, 567K bytes)
        num   pkts bytes target     prot opt in     out     source               destination
        1     1234  100K ACCEPT     tcp  --  *      *       0.0.0.0/0            0.0.0.0/0            tcp dpt:22 /* SSH */
        2      567   45K ACCEPT     tcp  --  *      *       192.168.1.0/24       0.0.0.0/0            tcp dpt:8080 /* Grafana */

        Returns:
            List[Dict] con ogni regola contenente:
            {
                'chain': 'INPUT',
                'rule_number': 1,
                'packets': 1234,
                'bytes': 102400,
                'target': 'ACCEPT',
                'protocol': 'tcp',
                'source': '0.0.0.0/0',
                'destination': '0.0.0.0/0',
                'port': 22,
                'comment': 'SSH'
            }
        """
        try:
            clean_output = cls.remove_ansi_codes(output)
            rules = []

            # Trova tutte le chain presenti nell'output
            chain_sections = re.finditer(
                r"Chain\s+(\w+)\s+\(policy\s+(\w+)", clean_output
            )

            for chain_match in chain_sections:
                current_chain = chain_match.group(1)

                # Trova la posizione della chain corrente
                chain_start = chain_match.end()

                # Trova l'inizio della prossima chain o la fine del file
                next_chain = re.search(r"Chain\s+\w+", clean_output[chain_start:])
                chain_end = (
                    chain_start + next_chain.start()
                    if next_chain
                    else len(clean_output)
                )

                # Estrae la sezione della chain corrente
                chain_section = clean_output[chain_match.start() : chain_end]

                # Parse delle singole regole
                # Pattern: num   pkts bytes target     prot opt in     out     source               destination
                rule_pattern = r"^\s*(\d+)\s+(\d+)\s+(\d+[KMG]?)\s+(\w+)\s+(\w+)\s+--\s+\S+\s+\S+\s+(\S+)\s+(\S+)\s*(.*?)$"

                for line in chain_section.split("\n"):
                    rule_match = re.match(rule_pattern, line)
                    if rule_match:
                        rule_num = int(rule_match.group(1))
                        packets = int(rule_match.group(2))
                        bytes_str = rule_match.group(3)
                        target = rule_match.group(4)
                        protocol = rule_match.group(5)
                        source = rule_match.group(6)
                        destination = rule_match.group(7)
                        extra = (
                            rule_match.group(8).strip() if rule_match.group(8) else ""
                        )

                        # Converti bytes
                        bytes_val = cls._parse_iptables_bytes(bytes_str)

                        # Estrai porta dal campo extra
                        port = None
                        port_match = re.search(r"dpt:(\d+)", extra)
                        if port_match:
                            port = int(port_match.group(1))

                        # Estrai commento
                        comment = ""
                        comment_match = re.search(r"/\*\s*(.*?)\s*\*/", extra)
                        if comment_match:
                            comment = comment_match.group(1)

                        rule = {
                            "chain": current_chain,
                            "rule_number": rule_num,
                            "packets": packets,
                            "bytes": bytes_val,
                            "target": target,
                            "protocol": protocol,
                            "source": source,
                            "destination": destination,
                            "port": port,
                            "comment": comment,
                        }

                        rules.append(rule)

            logger.debug(f"Parsed {len(rules)} rules")
            return rules

        except Exception as e:
            logger.error(f"Errore parsing rules: {e}")
            return []

    @classmethod
    def parse_threats(cls, output: str) -> List[Dict]:
        """
        Parse output di: firewall-manager --threats [MIN_SCORE]

        Output esempio:
        IP                 Score    Motivi
        ================================================================================
        203.0.113.45       95       Port Scanning (15 porte), Packets: 150, SYN Flood
        198.51.100.123     70       Port Scanning (8 porte), Packets: 85
        192.0.2.67         45       Packets: 42

        Returns:
            List[Dict] con ogni minaccia:
            {
                'source_ip': '203.0.113.45',
                'threat_score': 95,
                'packets': 150,
                'ports_count': 15,
                'protocols': ['tcp'],
                'threat_type': 'Port Scanning',
                'reasons': ['Port Scanning (15 porte)', 'Packets: 150', 'SYN Flood']
            }
        """
        try:
            clean_output = cls.remove_ansi_codes(output)
            threats = []

            # Salta header e linea di separazione
            lines = clean_output.split("\n")
            parsing = False

            for line in lines:
                # Identifica l'inizio dei dati (dopo la linea con "===")
                if "=" * 10 in line:
                    parsing = True
                    continue

                if not parsing or not line.strip():
                    continue

                # Parse linea minaccia
                # Pattern: IP (spaces) Score (spaces) Motivi
                match = re.match(r"^\s*(\S+)\s+(\d+)\s+(.+)$", line)
                if match:
                    ip = match.group(1)
                    score = int(match.group(2))
                    reasons_str = match.group(3).strip()

                    # Parse reasons per estrarre dettagli
                    reasons = [r.strip() for r in reasons_str.split(",")]

                    # Estrai informazioni dai reasons
                    packets = 0
                    ports_count = 0
                    threat_type = None
                    protocols = []

                    for reason in reasons:
                        # Port Scanning (N porte)
                        ports_match = re.search(
                            r"Port Scanning \((\d+) port[ei]\)", reason
                        )
                        if ports_match:
                            ports_count = int(ports_match.group(1))
                            threat_type = "Port Scanning"

                        # Packets: N
                        packets_match = re.search(r"Packets:\s*(\d+)", reason)
                        if packets_match:
                            packets = int(packets_match.group(1))

                        # SYN Flood
                        if "SYN Flood" in reason:
                            if not threat_type:
                                threat_type = "SYN Flood"
                            else:
                                threat_type += ", SYN Flood"

                        # SSH Brute Force
                        if "SSH Brute Force" in reason:
                            if not threat_type:
                                threat_type = "SSH Brute Force"
                            else:
                                threat_type += ", SSH Brute Force"

                        # ICMP Flood
                        if "ICMP Flood" in reason:
                            if not threat_type:
                                threat_type = "ICMP Flood"
                            else:
                                threat_type += ", ICMP Flood"

                        # Protocol diversity
                        if "Protocolli multipli" in reason:
                            protocols = ["tcp", "udp", "icmp"]

                    # Default protocol
                    if not protocols:
                        protocols = ["tcp"]

                    # Classifica threat in base allo score
                    if score >= 80:
                        classification = "CRITICAL"
                    elif score >= 60:
                        classification = "HIGH"
                    elif score >= 40:
                        classification = "MEDIUM"
                    else:
                        classification = "LOW"

                    threat = {
                        "source_ip": ip,
                        "threat_score": score,
                        "packets": packets,
                        "ports_count": ports_count,
                        "protocols": ",".join(protocols),
                        "threat_type": threat_type or "Unknown",
                        "classification": classification,
                        "reasons": reasons,
                    }

                    threats.append(threat)

            logger.debug(f"Parsed {len(threats)} threats")
            return threats

        except Exception as e:
            logger.error(f"Errore parsing threats: {e}")
            return []

    @classmethod
    def parse_analyze(cls, output: str) -> Optional[Dict]:
        """
        Parse output di: firewall-manager --analyze [HOURS]

        Output esempio:
        ╔══════════════════════════════════════════════════════════════════════════════╗
        ║                    ANALISI TRAFFICO BLOCCATO (ultima 1 ora)                 ║
        ╚══════════════════════════════════════════════════════════════════════════════╝

        📦 PACCHETTI ANALIZZATI: 1234

        🌐 TOP 10 IP SORGENTE
        ├─ 203.0.113.45    : 150 pacchetti (12.2%)
        ├─ 198.51.100.123  : 85 pacchetti (6.9%)
        └─ 192.0.2.67      : 42 pacchetti (3.4%)

        🔌 TOP 10 PORTE DESTINAZIONE
        ├─ 22 (ssh)     : 234 pacchetti
        ├─ 80 (http)    : 123 pacchetti
        └─ 443 (https)  : 98 pacchetti

        📊 PROTOCOLLI
        ├─ TCP: 1100 (89.1%)
        ├─ UDP: 89 (7.2%)
        └─ ICMP: 45 (3.6%)

        Returns:
            Dict con analisi:
            {
                'total_packets': 1234,
                'hours_analyzed': 1,
                'top_sources': [
                    {'ip': '203.0.113.45', 'packets': 150, 'percent': 12.2},
                    ...
                ],
                'top_ports': [
                    {'port': 22, 'service': 'ssh', 'packets': 234},
                    ...
                ],
                'protocols': {
                    'tcp': {'packets': 1100, 'percent': 89.1},
                    'udp': {'packets': 89, 'percent': 7.2},
                    'icmp': {'packets': 45, 'percent': 3.6}
                }
            }
        """
        try:
            clean_output = cls.remove_ansi_codes(output)

            analysis = {
                "total_packets": 0,
                "hours_analyzed": 1,
                "top_sources": [],
                "top_ports": [],
                "protocols": {},
            }

            # Parse total packets
            packets_match = re.search(r"PACCHETTI ANALIZZATI:\s*(\d+)", clean_output)
            if packets_match:
                analysis["total_packets"] = int(packets_match.group(1))

            # Parse hours analyzed
            hours_match = re.search(r"ultima\s+(\d+)\s+ora", clean_output)
            if hours_match:
                analysis["hours_analyzed"] = int(hours_match.group(1))

            # Parse top sources
            sources_section = re.search(
                r"TOP \d+ IP SORGENTE(.*?)(?=TOP \d+ PORTE|$)", clean_output, re.DOTALL
            )
            if sources_section:
                for line in sources_section.group(1).split("\n"):
                    source_match = re.search(
                        r"(\d+\.\d+\.\d+\.\d+)\s*:\s*(\d+)\s+pacchetti\s+\((\d+(?:\.\d+)?)%\)",
                        line,
                    )
                    if source_match:
                        analysis["top_sources"].append(
                            {
                                "ip": source_match.group(1),
                                "packets": int(source_match.group(2)),
                                "percent": float(source_match.group(3)),
                            }
                        )

            # Parse top ports
            ports_section = re.search(
                r"TOP \d+ PORTE DESTINAZIONE(.*?)(?=PROTOCOLLI|$)",
                clean_output,
                re.DOTALL,
            )
            if ports_section:
                for line in ports_section.group(1).split("\n"):
                    port_match = re.search(
                        r"(\d+)\s+\((\w+)\)\s*:\s*(\d+)\s+pacchetti", line
                    )
                    if port_match:
                        analysis["top_ports"].append(
                            {
                                "port": int(port_match.group(1)),
                                "service": port_match.group(2),
                                "packets": int(port_match.group(3)),
                            }
                        )

            # Parse protocols
            proto_section = re.search(r"PROTOCOLLI(.*?)$", clean_output, re.DOTALL)
            if proto_section:
                for line in proto_section.group(1).split("\n"):
                    # TCP: 1100 (89.1%)
                    proto_match = re.search(
                        r"(TCP|UDP|ICMP):\s*(\d+)\s+\((\d+(?:\.\d+)?)%\)",
                        line,
                        re.IGNORECASE,
                    )
                    if proto_match:
                        proto_name = proto_match.group(1).lower()
                        analysis["protocols"][proto_name] = {
                            "packets": int(proto_match.group(2)),
                            "percent": float(proto_match.group(3)),
                        }

            logger.debug(f"Analysis parsed: {analysis['total_packets']} packets")
            return analysis

        except Exception as e:
            logger.error(f"Errore parsing analyze: {e}")
            return None

    @staticmethod
    def _convert_size_to_bytes(value: float, unit: str) -> int:
        """Converte dimensioni (KB, MB, GB) in bytes"""
        units = {
            "B": 1,
            "KB": 1024,
            "MB": 1024**2,
            "GB": 1024**3,
            "K": 1024,  # Alias per iptables
            "M": 1024**2,
            "G": 1024**3,
        }

        # Remove trailing 'B' if present
        unit_clean = unit.rstrip("B").upper()
        multiplier = units.get(unit_clean, units.get(unit.upper(), 1))

        return int(value * multiplier)

    @staticmethod
    def _parse_iptables_bytes(bytes_str: str) -> int:
        """
        Parse formato bytes di iptables (es: "100K", "2M", "123")
        """
        if not bytes_str or bytes_str == "0":
            return 0

        # Estrai numero e unità
        match = re.match(r"(\d+(?:\.\d+)?)([KMG])?", bytes_str)
        if match:
            value = float(match.group(1))
            unit = match.group(2) or ""

            units = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3}

            return int(value * units.get(unit, 1))

        return 0


# Funzioni di utility per facilitare l'uso


def parse_firewall_stats(output: str) -> Optional[Dict]:
    """Shortcut per parsare stats"""
    return FirewallOutputParser.parse_stats(output)


def parse_firewall_rules(output: str, chain: Optional[str] = None) -> List[Dict]:
    """Shortcut per parsare rules"""
    return FirewallOutputParser.parse_rules(output, chain)


def parse_firewall_threats(output: str) -> List[Dict]:
    """Shortcut per parsare threats"""
    return FirewallOutputParser.parse_threats(output)


def parse_firewall_analyze(output: str) -> Optional[Dict]:
    """Shortcut per parsare analyze"""
    return FirewallOutputParser.parse_analyze(output)

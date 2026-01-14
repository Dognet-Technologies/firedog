"""
Threat Detector per Dog Agent
Analizza traffico e rileva minacce
"""
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


class ThreatDetector:
    """Rileva minacce dal traffico di rete"""

    def __init__(self, pcap_input_path: str, pcap_output_path: str, threshold: int = 75):
        """
        Args:
            pcap_input_path: Path al file PCAP input
            pcap_output_path: Path al file PCAP output
            threshold: Soglia threat score per bloccare automaticamente
        """
        self.pcap_input_path = Path(pcap_input_path)
        self.pcap_output_path = Path(pcap_output_path)
        self.threshold = threshold

    def analyze_pcap(self, pcap_path: Path) -> List[Dict]:
        """
        Analizza file PCAP e rileva minacce
        Returns: Lista di minacce rilevate
        """
        threats = []

        if not pcap_path.exists():
            logger.debug(f"PCAP file not found: {pcap_path}")
            return threats

        try:
            from scapy.all import rdpcap, IP

            packets = rdpcap(str(pcap_path))

            # Analizza pacchetti
            ip_stats = {}

            for packet in packets:
                if packet.haslayer(IP):
                    src_ip = packet[IP].src

                    if src_ip not in ip_stats:
                        ip_stats[src_ip] = {
                            'packet_count': 0,
                            'ports': set()
                        }

                    ip_stats[src_ip]['packet_count'] += 1

                    # Rileva port scan
                    if packet.haslayer('TCP'):
                        dst_port = packet['TCP'].dport
                        ip_stats[src_ip]['ports'].add(dst_port)

            # Analizza statistiche e crea threats
            for src_ip, stats in ip_stats.items():
                threat_score = 0
                attack_type = 'unknown'
                classification = 'LOW'

                # Port scan detection
                if len(stats['ports']) > 10:
                    threat_score += 40
                    attack_type = 'port_scan'

                # High packet count
                if stats['packet_count'] > 100:
                    threat_score += 30
                    if attack_type == 'unknown':
                        attack_type = 'high_traffic'

                # Classify
                if threat_score >= 80:
                    classification = 'CRITICAL'
                elif threat_score >= 60:
                    classification = 'HIGH'
                elif threat_score >= 40:
                    classification = 'MEDIUM'

                if threat_score > 0:
                    threats.append({
                        'source_ip': src_ip,
                        'threat_score': threat_score,
                        'classification': classification,
                        'attack_type': attack_type,
                        'details': {
                            'packet_count': stats['packet_count'],
                            'unique_ports': len(stats['ports'])
                        }
                    })

        except Exception as e:
            logger.error(f"Error analyzing PCAP: {e}")

        return threats

    def analyze_traffic(self) -> List[Dict]:
        """Analizza tutto il traffico (input + output)"""
        threats = []

        # Analizza input dropped
        threats.extend(self.analyze_pcap(self.pcap_input_path))

        # Analizza output dropped
        threats.extend(self.analyze_pcap(self.pcap_output_path))

        # Rimuovi duplicati per IP
        seen = set()
        unique_threats = []
        for threat in threats:
            if threat['source_ip'] not in seen:
                seen.add(threat['source_ip'])
                unique_threats.append(threat)

        logger.info(f"Detected {len(unique_threats)} threats")
        return unique_threats

    def should_auto_block(self, threat_score: int) -> bool:
        """Verifica se minaccia deve essere bloccata automaticamente"""
        return threat_score >= self.threshold

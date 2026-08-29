#!/usr/bin/env python3 
"""
Advanced Traffic Analyzer
Analisi intelligente del traffico bloccato con machine learning-like scoring
"""

import subprocess
import os
import sys
from collections import defaultdict, Counter
from datetime import datetime
import json
import re

class TrafficAnalyzer:
    """Analizzatore avanzato traffico con scoring anomalie"""
    
    # Porte comuni legittime
    LEGITIMATE_PORTS = {
        80, 443, 53, 123,  # Web, DNS, NTP
        22,  # SSH (potrebbe essere attacco o legittimo)
        25, 587, 465,  # SMTP
        143, 993, 110, 995,  # IMAP, POP3
    }
    
    # Porte comunemente attaccate
    ATTACK_PORTS = {
        23,    # Telnet
        3389,  # RDP
        1433,  # MS SQL
        3306,  # MySQL
        5432,  # PostgreSQL
        6379,  # Redis
        27017, # MongoDB
        445,   # SMB
        135, 139,  # NetBIOS
        21,    # FTP
    }
    
    # Pattern protocolli sospetti
    SUSPICIOUS_PATTERNS = [
        'TTL=1',  # Traceroute
        'DF',     # Don't Fragment (potenziale scan)
    ]
    
    def __init__(self, pcap_file):
        self.pcap_file = pcap_file
        self.stats = defaultdict(int)
        self.ip_stats = defaultdict(lambda: {
            'packets': 0,
            'ports': set(),
            'protocols': set(),
            'flags': set(),
            'score': 0
        })
    
    def analyze(self):
        """Esegue analisi completa"""
        
        if not os.path.exists(self.pcap_file):
            print(f"Errore: File {self.pcap_file} non trovato")
            return None
        
        print(f"\n{'='*70}")
        print(f"Analisi: {os.path.basename(self.pcap_file)}")
        print(f"{'='*70}\n")
        
        # Estrai informazioni base
        self.extract_basic_stats()
        
        # Analisi IP
        self.analyze_ips()
        
        # Genera report
        return self.generate_report()
    
    def extract_basic_stats(self):
        """Estrae statistiche base dal PCAP"""
        
        try:
            # Conta pacchetti totali
            cmd = f"tcpdump -nn -r {self.pcap_file} 2>/dev/null | wc -l"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            self.stats['total_packets'] = int(result.stdout.strip())
            
            # Conta per protocollo
            for proto in ['tcp', 'udp', 'icmp']:
                cmd = f"tcpdump -nn -r {self.pcap_file} {proto} 2>/dev/null | wc -l"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                self.stats[f'{proto}_packets'] = int(result.stdout.strip())
            
        except Exception as e:
            print(f"Errore estrazione statistiche: {e}")
    
    def analyze_ips(self):
        """Analizza comportamento per IP"""
        
        try:
            # Leggi tutti i pacchetti
            cmd = f"tcpdump -nn -tttt -r {self.pcap_file} 2>/dev/null"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            for line in result.stdout.split('\n'):
                if not line.strip():
                    continue
                
                # Parsing linea tcpdump
                parsed = self.parse_tcpdump_line(line)
                if not parsed:
                    continue
                
                src_ip = parsed['src_ip']
                dst_port = parsed.get('dst_port')
                protocol = parsed.get('protocol')
                flags = parsed.get('flags', '')
                
                # Aggiorna statistiche IP
                self.ip_stats[src_ip]['packets'] += 1
                if dst_port:
                    self.ip_stats[src_ip]['ports'].add(dst_port)
                if protocol:
                    self.ip_stats[src_ip]['protocols'].add(protocol)
                if flags:
                    self.ip_stats[src_ip]['flags'].add(flags)
            
            # Calcola score per ogni IP
            for ip in self.ip_stats:
                self.ip_stats[ip]['score'] = self.calculate_threat_score(ip)
                
        except Exception as e:
            print(f"Errore analisi IP: {e}")
    
    def parse_tcpdump_line(self, line):
        """Parsing linea output tcpdump"""
        
        try:
            # Formato base: timestamp IP > IP: proto ...
            # Esempio: 2025-01-15 10:30:45.123456 IP 192.168.1.1.12345 > 10.0.0.1.80: Flags [S]
            
            parts = line.split()
            if len(parts) < 5:
                return None
            
            # Trova IP sorgente e destinazione
            src_idx = None
            for i, part in enumerate(parts):
                if '>' in part and i > 0:
                    src_idx = i - 1
                    break
            
            if src_idx is None:
                return None
            
            src = parts[src_idx]
            dst = parts[src_idx + 2].rstrip(':')
            
            # Estrai IP e porta
            src_parts = src.rsplit('.', 1)
            dst_parts = dst.rsplit('.', 1)
            
            result = {
                'src_ip': src_parts[0],
                'src_port': src_parts[1] if len(src_parts) > 1 else None,
                'dst_ip': dst_parts[0],
                'dst_port': int(dst_parts[1]) if len(dst_parts) > 1 and dst_parts[1].isdigit() else None,
            }
            
            # Protocol
            if 'tcp' in line.lower():
                result['protocol'] = 'tcp'
            elif 'udp' in line.lower():
                result['protocol'] = 'udp'
            elif 'icmp' in line.lower():
                result['protocol'] = 'icmp'
            
            # TCP Flags
            if 'Flags' in line:
                flags_match = re.search(r'Flags \[([^\]]+)\]', line)
                if flags_match:
                    result['flags'] = flags_match.group(1)
            
            return result
            
        except Exception:
            return None
    
    def calculate_threat_score(self, ip):
        """Calcola threat score per IP (0-100)"""
        
        stats = self.ip_stats[ip]
        score = 0
        
        # Volume pacchetti
        packets = stats['packets']
        if packets > 1000:
            score += 40
        elif packets > 500:
            score += 30
        elif packets > 100:
            score += 20
        elif packets > 50:
            score += 10
        
        # Numero porte diverse (port scanning)
        num_ports = len(stats['ports'])
        if num_ports > 50:
            score += 30
        elif num_ports > 20:
            score += 20
        elif num_ports > 10:
            score += 10
        
        # Porte attaccate
        attack_ports_hit = stats['ports'].intersection(self.ATTACK_PORTS)
        if attack_ports_hit:
            score += len(attack_ports_hit) * 5
        
        # TCP SYN flooding
        if 'S' in stats['flags'] and packets > 100:
            score += 15
        
        # Protocolli multipli (potenziale scanning)
        if len(stats['protocols']) > 2:
            score += 10
        
        # Normalizza 0-100
        return min(100, score)
    
    def generate_report(self):
        """Genera report completo"""
        
        print("\nðŸ“Š STATISTICHE GENERALI")
        print("-" * 70)
        print(f"Pacchetti totali:  {self.stats['total_packets']:>10,}")
        print(f"  - TCP:           {self.stats['tcp_packets']:>10,}")
        print(f"  - UDP:           {self.stats['udp_packets']:>10,}")
        print(f"  - ICMP:          {self.stats['icmp_packets']:>10,}")
        
        print("\n\nðŸŽ¯ TOP 20 IP SORGENTI per THREAT SCORE")
        print("-" * 70)
        print(f"{'IP':<18} {'Score':<8} {'Packets':<10} {'Ports':<10} {'Tipo'}")
        print("-" * 70)
        
        # Ordina per score
        sorted_ips = sorted(
            self.ip_stats.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )[:20]
        
        for ip, stats in sorted_ips:
            threat_type = self.classify_threat(stats)
            color = self.get_color_for_score(stats['score'])
            
            print(f"{color}{ip:<18}{stats['score']:<8}{stats['packets']:<10}"
                  f"{len(stats['ports']):<10}{threat_type}\033[0m")
        
        print("\n\nðŸš¨ ANALISI MINACCE")
        print("-" * 70)
        
        # Classifica minacce
        threats = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': []
        }
        
        for ip, stats in self.ip_stats.items():
            score = stats['score']
            if score >= 80:
                threats['critical'].append((ip, score))
            elif score >= 60:
                threats['high'].append((ip, score))
            elif score >= 40:
                threats['medium'].append((ip, score))
            elif score >= 20:
                threats['low'].append((ip, score))
        
        print(f"ðŸ”´ CRITICHE (score >= 80):  {len(threats['critical']):>3}")
        print(f"ðŸŸ  ALTE     (score >= 60):  {len(threats['high']):>3}")
        print(f"ðŸŸ¡ MEDIE    (score >= 40):  {len(threats['medium']):>3}")
        print(f"ðŸŸ¢ BASSE    (score >= 20):  {len(threats['low']):>3}")
        
        # Dettagli minacce critiche
        if threats['critical']:
            print("\n\nðŸ”´ DETTAGLIO MINACCE CRITICHE")
            print("-" * 70)
            for ip, score in threats['critical']:
                stats = self.ip_stats[ip]
                print(f"\nIP: {ip} (Score: {score})")
                print(f"  Packets: {stats['packets']:,}")
                print(f"  Porte target: {len(stats['ports'])}")
                if stats['ports']:
                    ports_str = ', '.join(str(p) for p in sorted(list(stats['ports']))[:10])
                    if len(stats['ports']) > 10:
                        ports_str += f" ... (+{len(stats['ports'])-10} altre)"
                    print(f"    {ports_str}")
                print(f"  Protocolli: {', '.join(stats['protocols'])}")
                print(f"  Tipo attacco: {self.classify_threat(stats)}")
        
        print("\n\nðŸ’¡ RACCOMANDAZIONI")
        print("-" * 70)
        self.generate_recommendations(threats)
        
        return {
            'stats': dict(self.stats),
            'threats': threats,
            'top_ips': sorted_ips[:20]
        }
    
    def classify_threat(self, stats):
        """Classifica tipo di minaccia"""
        
        num_ports = len(stats['ports'])
        packets = stats['packets']
        
        if num_ports > 50:
            return "Port Scanning"
        elif packets > 500 and 'S' in stats['flags']:
            return "SYN Flood"
        elif stats['ports'].intersection(self.ATTACK_PORTS):
            return "Service Attack"
        elif packets > 100:
            return "Volumetric Attack"
        else:
            return "Suspicious Activity"
    
    def get_color_for_score(self, score):
        """Restituisce codice colore per score"""
        if score >= 80:
            return '\033[0;31m'  # Rosso
        elif score >= 60:
            return '\033[0;33m'  # Giallo
        elif score >= 40:
            return '\033[1;37m'  # Bianco
        else:
            return '\033[0;32m'  # Verde
    
    def generate_recommendations(self, threats):
        """Genera raccomandazioni basate su analisi"""
        
        if threats['critical']:
            print("\nðŸ”´ AZIONE IMMEDIATA RICHIESTA:")
            print("   - Bloccare permanentemente IP critici con:")
            print("     firewall-manager --add-input <PORT> tcp --source <IP> --comment 'Block attacker'")
            print("   - Considerare blocco a livello upstream/ISP")
        
        if threats['high'] or threats['critical']:
            print("\nðŸŸ  AZIONI CONSIGLIATE:")
            print("   - Attivare fail2ban per protezione automatica")
            print("   - Ridurre timeout connessioni TCP")
            print("   - Implementare rate limiting piÃ¹ aggressivo")
        
        if threats['medium']:
            print("\nðŸŸ¡ MONITORAGGIO:")
            print("   - Continuare osservazione pattern IP a medio rischio")
            print("   - Verificare se traffico Ã¨ legittimo (crawlers, monitoring)")
        
        # Raccomandazioni generiche
        print("\nðŸ’¡ BEST PRACTICES:")
        print("   - Eseguire analisi regolari: firewall-manager --analyze 24")
        print("   - Verificare log ulogd: tail -f /var/log/ulogd/ulogd.log")
        print("   - Mantenere sistema aggiornato (apt upgrade / zypper update)")


def main():
    """Main entry point"""
    
    if len(sys.argv) > 1:
        pcap_file = sys.argv[1]
    else:
        # Default: analizza INPUT dropped
        pcap_file = "/var/log/ulogd/input_dropped.pcap"
    
    if not os.path.exists(pcap_file):
        print(f"Errore: File {pcap_file} non trovato")
        print("\nUso: traffic-analyzer.py [file.pcap]")
        print("     Se omesso, analizza /var/log/ulogd/input_dropped.pcap")
        sys.exit(1)
    
    # Verifica tcpdump
    if subprocess.run(['which', 'tcpdump'], capture_output=True).returncode != 0:
        print("Errore: tcpdump non trovato. Installa con: apt install tcpdump / zypper install tcpdump")
        sys.exit(1)
    
    analyzer = TrafficAnalyzer(pcap_file)
    result = analyzer.analyze()
    
    # Salva report JSON opzionale
    if result and '--json' in sys.argv:
        output_file = 'traffic_report.json'
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n\nReport JSON salvato in: {output_file}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrotto dall'utente")
        sys.exit(0)

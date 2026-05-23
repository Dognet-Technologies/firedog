#!/usr/bin/env python3
"""
Firewall Manager CLI
Gestione avanzata firewall iptables con analisi traffico e scoring anomalie
Conforme a OWASP/NIST security standards
"""

import argparse
import subprocess
import sys
import os
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import ipaddress

# Configurazione
CONFIG = {
    'rules_file': '/etc/firewall/iptables.rules',
    'custom_rules': '/etc/firewall/custom_rules.conf',
    'log_dir': '/var/log/ulogd',
    'state_file': '/var/lib/firewall/state.json',
    'min_uid': 1000  # UID minimo per sicurezza
}

# Porte comuni e servizi
COMMON_SERVICES = {
    'ssh': 22,
    'http': 80,
    'https': 443,
    'dns': 53,
    'smtp': 25,
    'smtps': 587,
    'imap': 143,
    'imaps': 993,
    'pop3': 110,
    'pop3s': 995,
    'ftp': 21,
    'mysql': 3306,
    'postgresql': 5432,
    'redis': 6379,
    'mongodb': 27017,
}

class Colors:
    """Codici colore ANSI per output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[1;37m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class FirewallManager:
    """Classe principale per gestione firewall"""
    
    def __init__(self):
        self.check_root()
        self.ensure_directories()
    
    def check_root(self):
        """Verifica privilegi root"""
        if os.geteuid() != 0:
            self.error("Questo comando richiede privilegi root. Usa sudo.")
            sys.exit(1)
    
    def ensure_directories(self):
        """Crea directory necessarie"""
        Path(CONFIG['log_dir']).mkdir(parents=True, exist_ok=True)
        Path('/var/lib/firewall').mkdir(parents=True, exist_ok=True)
        Path('/etc/firewall').mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def success(msg: str):
        """Stampa messaggio successo"""
        print(f"{Colors.GREEN}[âœ“]{Colors.RESET} {msg}")
    
    @staticmethod
    def error(msg: str):
        """Stampa messaggio errore"""
        print(f"{Colors.RED}[âœ—]{Colors.RESET} {msg}", file=sys.stderr)
    
    @staticmethod
    def warning(msg: str):
        """Stampa warning"""
        print(f"{Colors.YELLOW}[!]{Colors.RESET} {msg}")
    
    @staticmethod
    def info(msg: str):
        """Stampa informazione"""
        print(f"{Colors.CYAN}[i]{Colors.RESET} {msg}")
    
    def run_command(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Esegue comando shell in modo sicuro"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=check
            )
            return result
        except subprocess.CalledProcessError as e:
            self.error(f"Errore esecuzione comando: {e.stderr}")
            raise
    
    def validate_ip(self, ip: str) -> bool:
        """Valida indirizzo IP"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def validate_port(self, port: str) -> bool:
        """Valida porta"""
        try:
            p = int(port)
            return 1 <= p <= 65535
        except ValueError:
            return False
    
    def validate_protocol(self, proto: str) -> bool:
        """Valida protocollo"""
        return proto.lower() in ['tcp', 'udp', 'icmp']
    
    def add_rule_input(self, port: str, protocol: str = 'tcp', 
                      source_ip: Optional[str] = None, comment: str = ''):
        """Aggiunge regola INPUT"""
        
        # Validazione input
        if not self.validate_port(port):
            self.error(f"Porta non valida: {port}")
            return False
        
        if not self.validate_protocol(protocol):
            self.error(f"Protocollo non valido: {protocol}")
            return False
        
        if source_ip and not self.validate_ip(source_ip):
            self.error(f"IP sorgente non valido: {source_ip}")
            return False
        
        # Costruisci regola
        rule_parts = [
            'iptables', '-I', 'INPUT', '1',
            '-p', protocol,
            '--dport', port,
            '-m', 'conntrack', '--ctstate', 'NEW'
        ]
        
        if source_ip:
            rule_parts.extend(['-s', source_ip])
        
        rule_parts.extend(['-j', 'ACCEPT'])
        
        if comment:
            rule_parts.extend(['-m', 'comment', '--comment', comment[:256]])
        
        try:
            self.run_command(rule_parts)
            
            # Salva regola personalizzata
            self.save_custom_rule(' '.join(rule_parts), comment)
            
            # Persisti regole
            self.save_rules()
            
            src_info = f" da {source_ip}" if source_ip else ""
            self.success(f"Regola INPUT aggiunta: {protocol.upper()}/{port}{src_info}")
            return True
            
        except subprocess.CalledProcessError:
            self.error("Impossibile aggiungere regola")
            return False
    
    def add_rule_output(self, port: str, protocol: str = 'tcp',
                       dest_ip: Optional[str] = None, comment: str = ''):
        """Aggiunge regola OUTPUT"""
        
        if not self.validate_port(port):
            self.error(f"Porta non valida: {port}")
            return False
        
        if not self.validate_protocol(protocol):
            self.error(f"Protocollo non valido: {protocol}")
            return False
        
        if dest_ip and not self.validate_ip(dest_ip):
            self.error(f"IP destinazione non valido: {dest_ip}")
            return False
        
        rule_parts = [
            'iptables', '-I', 'OUTPUT', '1',
            '-p', protocol,
            '--dport', port,
            '-m', 'conntrack', '--ctstate', 'NEW'
        ]
        
        if dest_ip:
            rule_parts.extend(['-d', dest_ip])
        
        rule_parts.extend(['-j', 'ACCEPT'])
        
        if comment:
            rule_parts.extend(['-m', 'comment', '--comment', comment[:256]])
        
        try:
            self.run_command(rule_parts)
            self.save_custom_rule(' '.join(rule_parts), comment)
            self.save_rules()
            
            dest_info = f" verso {dest_ip}" if dest_ip else ""
            self.success(f"Regola OUTPUT aggiunta: {protocol.upper()}/{port}{dest_info}")
            return True
            
        except subprocess.CalledProcessError:
            self.error("Impossibile aggiungere regola")
            return False
    
    def save_custom_rule(self, rule: str, comment: str):
        """Salva regola personalizzata nel file di configurazione"""
        with open(CONFIG['custom_rules'], 'a') as f:
            if comment:
                f.write(f"# {comment}\n")
            f.write(f"{rule}\n")
    
    def remove_rule(self, chain: str, rule_num: int):
        """Rimuove regola per numero"""
        
        chain = chain.upper()
        if chain not in ['INPUT', 'OUTPUT', 'FORWARD']:
            self.error("Chain non valida. Usa: INPUT, OUTPUT, FORWARD")
            return False
        
        try:
            self.run_command(['iptables', '-D', chain, str(rule_num)])
            self.save_rules()
            self.success(f"Regola #{rule_num} rimossa da chain {chain}")
            return True
        except subprocess.CalledProcessError:
            self.error(f"Impossibile rimuovere regola #{rule_num} da {chain}")
            return False
    
    def list_rules(self, chain: Optional[str] = None):
        """Lista regole firewall"""
        
        print(f"\n{Colors.BOLD}=== Regole Firewall Attive ==={Colors.RESET}\n")
        
        chains = [chain.upper()] if chain else ['INPUT', 'OUTPUT', 'FORWARD']
        
        for ch in chains:
            if ch not in ['INPUT', 'OUTPUT', 'FORWARD']:
                self.warning(f"Chain '{ch}' non valida, ignorata")
                continue
            
            result = self.run_command(['iptables', '-L', ch, '-n', '-v', '--line-numbers'])
            
            print(f"{Colors.CYAN}Chain: {ch}{Colors.RESET}")
            print("=" * 100)
            print(result.stdout)
            print()
    
    def save_rules(self):
        """Salva regole correnti"""
        try:
            result = self.run_command(['iptables-save'])
            with open(CONFIG['rules_file'], 'w') as f:
                f.write(result.stdout)
            os.chmod(CONFIG['rules_file'], 0o600)
        except Exception as e:
            self.error(f"Errore salvataggio regole: {e}")
    
    def restore_rules(self):
        """Ripristina regole salvate"""
        if not os.path.exists(CONFIG['rules_file']):
            self.error("File regole non trovato")
            return False
        
        try:
            with open(CONFIG['rules_file'], 'r') as f:
                self.run_command(['iptables-restore'], check=True)
                # Passa il contenuto via stdin
                subprocess.run(
                    ['iptables-restore'],
                    input=f.read(),
                    text=True,
                    check=True
                )
            self.success("Regole ripristinate")
            return True
        except Exception as e:
            self.error(f"Errore ripristino regole: {e}")
            return False
    
    def analyze_dropped_traffic(self, hours: int = 1, limit: int = 50):
        """Analizza traffico bloccato dai PCAP"""
        
        self.info(f"Analisi traffico bloccato ultime {hours} ora/e...")
        
        # Verifica presenza tcpdump/tshark
        analyzer = 'tshark' if self.check_command('tshark') else 'tcpdump'
        
        if not self.check_command(analyzer):
            self.error("Richiesto tcpdump o tshark per analisi. Installa con: apt install tcpdump o apt install tshark")
            return
        
        pcap_files = [
            f"{CONFIG['log_dir']}/input_dropped.pcap",
            f"{CONFIG['log_dir']}/output_dropped.pcap"
        ]
        
        for pcap in pcap_files:
            if not os.path.exists(pcap):
                self.warning(f"File {pcap} non trovato")
                continue
            
            direction = "INPUT" if "input" in pcap else "OUTPUT"
            print(f"\n{Colors.BOLD}=== Analisi {direction} ==={Colors.RESET}\n")
            
            # Analisi con tcpdump
            if analyzer == 'tcpdump':
                self.analyze_with_tcpdump(pcap, hours, limit)
            else:
                self.analyze_with_tshark(pcap, hours, limit)
    
    def analyze_with_tcpdump(self, pcap: str, hours: int, limit: int):
        """Analizza PCAP con tcpdump"""
        try:
            # Top IP sorgenti
            cmd = f"tcpdump -nn -r {pcap} 2>/dev/null | awk '{{print $3}}' | cut -d'.' -f1-4 | sort | uniq -c | sort -rn | head -{limit}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.stdout:
                print(f"{Colors.YELLOW}Top {limit} IP sorgenti bloccati:{Colors.RESET}")
                print(result.stdout)
            
        except Exception as e:
            self.error(f"Errore analisi: {e}")
    
    def analyze_with_tshark(self, pcap: str, hours: int, limit: int):
        """Analisi avanzata con tshark"""
        try:
            # Statistiche porte destinazione
            cmd = [
                'tshark', '-r', pcap, '-q', '-z', f'io,phs,tcp.dstport',
                '-Y', f'frame.time_relative <= {hours * 3600}'
            ]
            result = self.run_command(cmd, check=False)
            
            if result.stdout:
                print(f"{Colors.YELLOW}Statistiche porte destinazione:{Colors.RESET}")
                print(result.stdout[:1000])  # Limita output
            
        except Exception as e:
            self.error(f"Errore analisi tshark: {e}")
    
    def check_command(self, cmd: str) -> bool:
        """Verifica disponibilitÃ  comando"""
        return subprocess.run(
            ['which', cmd],
            capture_output=True
        ).returncode == 0
    
    def show_stats(self):
        """Mostra statistiche firewall"""
        
        print(f"\n{Colors.BOLD}=== Statistiche Firewall ==={Colors.RESET}\n")
        
        # Policy correnti
        result = self.run_command(['iptables', '-L', '-n', '-v'])
        lines = result.stdout.split('\n')
        
        for line in lines[:10]:
            if 'Chain' in line or 'policy' in line:
                print(line)
        
        print(f"\n{Colors.YELLOW}Contatori pacchetti per chain:{Colors.RESET}")
        
        for chain in ['INPUT', 'OUTPUT']:
            result = self.run_command(['iptables', '-L', chain, '-n', '-v', '-x'])
            
            # Estrai totale pacchetti
            match = re.search(r'(\d+)\s+packets', result.stdout)
            if match:
                packets = int(match.group(1))
                print(f"  {chain}: {packets:,} pacchetti processati")
        
        # Dimensione PCAP
        print(f"\n{Colors.YELLOW}Dimensione log PCAP:{Colors.RESET}")
        for pcap in ['input_dropped.pcap', 'output_dropped.pcap']:
            path = f"{CONFIG['log_dir']}/{pcap}"
            if os.path.exists(path):
                size = os.path.getsize(path)
                print(f"  {pcap}: {self.format_bytes(size)}")
    
    @staticmethod
    def format_bytes(bytes_val: int) -> str:
        """Formatta bytes in formato leggibile"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} TB"
    
    def get_threat_score(self, ip: str) -> Tuple[int, List[str]]:
        """Calcola threat score per IP (0-100)"""
        
        score = 0
        reasons = []
        
        # Verifica IP privati (meno sospetti)
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private:
                reasons.append("IP privato (-10)")
                score -= 10
        except:
            pass
        
        # Controlla nel PCAP quante volte compare questo IP
        pcap_input = f"{CONFIG['log_dir']}/input_dropped.pcap"
        
        if os.path.exists(pcap_input):
            try:
                cmd = f"tcpdump -nn -r {pcap_input} 'src host {ip}' 2>/dev/null | wc -l"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                count = int(result.stdout.strip())
                
                if count > 100:
                    score += 50
                    reasons.append(f"Molti tentativi ({count}) +50")
                elif count > 50:
                    score += 30
                    reasons.append(f"Numerosi tentativi ({count}) +30")
                elif count > 10:
                    score += 15
                    reasons.append(f"Alcuni tentativi ({count}) +15")
                
            except:
                pass
        
        # Controlla porte comuni attaccate
        common_attack_ports = [22, 23, 3389, 21, 25]  # SSH, Telnet, RDP, FTP, SMTP
        
        # Normalizza score 0-100
        score = max(0, min(100, score))
        
        return score, reasons
    
    def show_threats(self, min_score: int = 30):
        """Mostra potenziali minacce"""

        print(f"\n{Colors.BOLD}=== Analisi Minacce (score >= {min_score}) ==={Colors.RESET}\n")

        pcap_input = f"{CONFIG['log_dir']}/input_dropped.pcap"

        if not os.path.exists(pcap_input):
            self.warning("Nessun file PCAP trovato")
            return

        # Estrai IP unici
        try:
            cmd = f"tcpdump -nn -r {pcap_input} 2>/dev/null | awk '{{print $3}}' | cut -d'.' -f1-4 | sort -u"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            ips = [ip.strip() for ip in result.stdout.split('\n') if ip.strip()]

            threats = []
            for ip in ips[:50]:  # Limita a 50 IP per performance
                score, reasons = self.get_threat_score(ip)
                if score >= min_score:
                    threats.append((ip, score, reasons))

            # Ordina per score
            threats.sort(key=lambda x: x[1], reverse=True)

            if not threats:
                self.success("Nessuna minaccia significativa rilevata")
                return

            print(f"{'IP':<18} {'Score':<8} {'Motivi'}")
            print("=" * 80)

            for ip, score, reasons in threats:
                color = Colors.RED if score >= 70 else Colors.YELLOW if score >= 50 else Colors.WHITE
                print(f"{color}{ip:<18}{Colors.RESET} {score:<8} {', '.join(reasons)}")

        except Exception as e:
            self.error(f"Errore analisi minacce: {e}")

    def get_threats_data(self, min_score: int = 30) -> List[Dict]:
        """Ottieni dati minacce in formato strutturato"""

        threats = []
        pcap_input = f"{CONFIG['log_dir']}/input_dropped.pcap"

        if not os.path.exists(pcap_input):
            return threats

        try:
            cmd = f"tcpdump -nn -r {pcap_input} 2>/dev/null | awk '{{print $3}}' | cut -d'.' -f1-4 | sort -u"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            ips = [ip.strip() for ip in result.stdout.split('\n') if ip.strip()]

            for ip in ips[:50]:
                score, reasons = self.get_threat_score(ip)
                if score >= min_score:
                    # Conta tentativi
                    cmd_count = f"tcpdump -nn -r {pcap_input} 'src host {ip}' 2>/dev/null | wc -l"
                    count_result = subprocess.run(cmd_count, shell=True, capture_output=True, text=True)
                    attempts = int(count_result.stdout.strip()) if count_result.stdout.strip() else 0

                    threats.append({
                        'ip': ip,
                        'score': score,
                        'attempts': attempts,
                        'reasons': reasons
                    })

            # Ordina per score
            threats.sort(key=lambda x: x['score'], reverse=True)

        except Exception:
            pass

        return threats

    def parse_iptables_rules(self, chain: str) -> List[Dict]:
        """Parsa regole iptables in formato strutturato"""

        rules = []

        try:
            result = self.run_command(['iptables', '-L', chain, '-n', '-v', '--line-numbers'])
            lines = result.stdout.split('\n')

            # Salta header (prime 2 righe)
            for line in lines[2:]:
                if not line.strip():
                    continue

                # Parse line: num pkts bytes target prot opt in out source destination extra
                parts = line.split()
                if len(parts) < 8:
                    continue

                # Estrai commento se presente
                comment = ''
                if '/*' in line:
                    comment_match = re.search(r'/\*\s*(.+?)\s*\*/', line)
                    if comment_match:
                        comment = comment_match.group(1)

                rule = {
                    'num': int(parts[0]) if parts[0].isdigit() else 0,
                    'pkts': int(parts[1]) if parts[1].isdigit() else 0,
                    'bytes': int(parts[2]) if parts[2].isdigit() else 0,
                    'target': parts[3],
                    'prot': parts[4],
                    'opt': parts[5],
                    'in': parts[6],
                    'out': parts[7],
                    'source': parts[8] if len(parts) > 8 else '0.0.0.0/0',
                    'destination': parts[9] if len(parts) > 9 else '0.0.0.0/0',
                    'extra': ' '.join(parts[10:]) if len(parts) > 10 else '',
                    'comment': comment
                }

                rules.append(rule)

        except Exception:
            pass

        return rules

    def get_network_flows(self, limit: int = 200) -> List[Dict]:
        """Snapshot dei peer remoti con cui il target sta dialogando.

        Sorgente: `ss -tun state established` (filtri TCP+UDP, solo connessioni
        attive). Non /proc/net/nf_conntrack perché negli LXC container quel
        file è filtrato e non leggibile.

        Filtra IP locali (127.0.0.0/8) e privati RFC1918/CGNAT (10/8, 172.16/12,
        192.168/16, 100.64/10) — la geo map ha senso solo per IP pubblici.

        Restituisce lista di dict {ip, count, ports}: count = numero di
        connessioni distinte verso quell'IP; ports = lista delle peer-port
        viste (max 10) utile per debug ma compatta nel payload.
        """
        import ipaddress
        out: Dict[str, Dict] = {}

        try:
            # Includiamo anche TIME-WAIT (linger ~60s post-close) e
            # CLOSE-WAIT/FIN-WAIT-* per catturare connessioni brevi (HTTP
            # request/response). `connected` matcha tutti gli stati eccetto
            # LISTEN/CLOSED. Più rumore ma molto meglio per workload "burst".
            # Niente `-H`: non supportato da iproute2 < 5.x (Debian 11).
            result = self.run_command(
                ['ss', '-tun', 'state', 'connected'], check=False
            )
            if result.returncode != 0:
                return []
            for line in result.stdout.split('\n'):
                parts = line.split()
                # Header riga: Netid State Recv-Q Send-Q Local Peer
                # Data row con state: Netid State Recv-Q Send-Q Local Peer
                # Data row senza state (-H): Netid Recv-Q Send-Q Local Peer
                # Skip header line e linee inconsistenti.
                if len(parts) < 5 or parts[0] == 'Netid':
                    continue
                # Determina indice della colonna Peer in base alla presenza di State.
                # Se parts[1] è una STATE word maiuscola (es. ESTAB, TIME-WAIT),
                # Peer è parts[5]; altrimenti parts[4].
                if parts[1].isupper() and not parts[1].isdigit():
                    if len(parts) < 6:
                        continue
                    peer = parts[5]
                else:
                    peer = parts[4]
                # IPv6 brackets: "[2001:db8::1]:443"
                if peer.startswith('['):
                    ip_str, _, port_str = peer.rpartition(':')
                    ip_str = ip_str.strip('[]')
                else:
                    ip_str, _, port_str = peer.rpartition(':')
                if not ip_str or ip_str == '*':
                    continue
                try:
                    ip_obj = ipaddress.ip_address(ip_str)
                except ValueError:
                    continue
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local \
                   or ip_obj.is_multicast or ip_obj.is_unspecified or ip_obj.is_reserved:
                    continue
                entry = out.setdefault(ip_str, {'ip': ip_str, 'count': 0, 'ports': []})
                entry['count'] += 1
                if port_str and port_str.isdigit() and len(entry['ports']) < 10:
                    p = int(port_str)
                    if p not in entry['ports']:
                        entry['ports'].append(p)
        except Exception:
            return []

        # Top N per count (taglia il payload se ci sono migliaia di connessioni)
        flows = sorted(out.values(), key=lambda x: x['count'], reverse=True)[:limit]
        return flows

    def get_conntrack_stats(self) -> Dict:
        """Connessioni tracciate dal modulo netfilter conntrack.

        È il numero di flussi TCP/UDP/ICMP attivi visti dal firewall, non solo
        le sessioni TCP ESTABLISHED — copre anche UDP "pseudo-stateful" e ICMP
        request/reply. Letto da /proc/sys/net/netfilter/nf_conntrack_{count,max}.
        """
        result = {'count': 0, 'max': 0}
        for key, path in (('count', '/proc/sys/net/netfilter/nf_conntrack_count'),
                          ('max',   '/proc/sys/net/netfilter/nf_conntrack_max')):
            try:
                with open(path, 'r') as f:
                    result[key] = int(f.read().strip())
            except (FileNotFoundError, ValueError, PermissionError):
                pass
        return result

    def get_protocol_stats(self) -> Dict:
        """Estrae i counter cumulativi per protocollo da /proc/net/snmp.

        Restituisce InSegs/OutSegs (TCP), InDatagrams/OutDatagrams (UDP),
        InMsgs/OutMsgs (ICMP). I valori sono counter del kernel (mai resettati
        a runtime), il server li scala in delta tra snapshot consecutivi.
        """
        result = {
            'tcp':  {'in_packets': 0, 'out_packets': 0},
            'udp':  {'in_packets': 0, 'out_packets': 0},
            'icmp': {'in_packets': 0, 'out_packets': 0},
        }
        try:
            with open('/proc/net/snmp', 'r') as f:
                lines = f.readlines()
            # Le coppie sono header / values con stesso prefisso (es. "Tcp:")
            headers = {}
            values = {}
            for line in lines:
                if ':' not in line:
                    continue
                proto, rest = line.split(':', 1)
                fields = rest.split()
                if proto in headers:
                    values[proto] = fields
                else:
                    headers[proto] = fields

            def col(proto, name, default=0):
                try:
                    idx = headers[proto].index(name)
                    return int(values[proto][idx])
                except (KeyError, ValueError, IndexError):
                    return default

            result['tcp']['in_packets']  = col('Tcp', 'InSegs')
            result['tcp']['out_packets'] = col('Tcp', 'OutSegs')
            result['udp']['in_packets']  = col('Udp', 'InDatagrams')
            result['udp']['out_packets'] = col('Udp', 'OutDatagrams')
            result['icmp']['in_packets'] = col('Icmp', 'InMsgs')
            result['icmp']['out_packets'] = col('Icmp', 'OutMsgs')
        except Exception:
            pass
        return result

    def get_system_info(self) -> Dict:
        """Ottieni informazioni di sistema"""

        info = {
            'os': 'Unknown',
            'kernel': 'Unknown',
            'uptime_seconds': 0
        }

        try:
            # OS info
            if os.path.exists('/etc/os-release'):
                with open('/etc/os-release', 'r') as f:
                    for line in f:
                        if line.startswith('PRETTY_NAME='):
                            info['os'] = line.split('=')[1].strip().strip('"')
                            break

            # Kernel
            result = self.run_command(['uname', '-r'], check=False)
            if result.returncode == 0:
                info['kernel'] = result.stdout.strip()

            # Uptime
            with open('/proc/uptime', 'r') as f:
                info['uptime_seconds'] = int(float(f.read().split()[0]))

        except Exception:
            pass

        return info

    def get_primary_ip(self) -> str:
        """Ottieni IP primario del sistema"""

        try:
            # Prova a ottenere IP dall'interfaccia di default route
            result = self.run_command(['ip', 'route', 'get', '1.1.1.1'], check=False)
            if result.returncode == 0:
                match = re.search(r'src\s+(\S+)', result.stdout)
                if match:
                    return match.group(1)
        except Exception:
            pass

        return '0.0.0.0'

    def export_json(self, output_path: str = '/opt/sentinelsuite/firedog/export/status.json'):
        """Esporta stato completo firewall in JSON"""

        try:
            # Crea directory se non esiste
            output_dir = os.path.dirname(output_path)
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # Raccogli dati
            data = {
                'hostname': subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip(),
                'ip_address': self.get_primary_ip(),
                # Timestamp ISO-8601 con TZ UTC esplicito. datetime.now() senza
                # argomenti restituisce un naive datetime → il server lo
                # interpreta come ora locale (Europe/Rome) e applica un doppio
                # offset, sfasando di 2h tutto il chart.
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'firedog_version': '1.0.0',
                'system': self.get_system_info(),
                # Counters per protocollo da /proc/net/snmp (cumulativi del kernel).
                # Il server scala in delta per il Protocol Distribution chart.
                'protocols': self.get_protocol_stats(),
                # Connessioni attive tracciate da netfilter conntrack: snapshot
                # istantaneo (non delta), utile per il chart "Connections over
                # time" che usa la serie temporale di snapshot.
                'conntrack': self.get_conntrack_stats(),
                # Peer remoti pubblici con cui il target sta dialogando.
                # Alimenta la GeoMap server-side (geoip2 lookup).
                'network_flows': self.get_network_flows(),
                'rules': {
                    'INPUT': self.parse_iptables_rules('INPUT'),
                    'OUTPUT': self.parse_iptables_rules('OUTPUT'),
                    'FORWARD': self.parse_iptables_rules('FORWARD')
                },
                'stats': {
                    'total_packets': {},
                    # `dropped_packets` (legacy, totale aggregato) resta per
                    # retro-compat; `dropped` espone i counter delle chain di
                    # drop create da firewall-init.sh, separati per direzione.
                    'dropped_packets': 0,
                    'dropped': {
                        'input': 0,
                        'output': 0,
                    },
                    'pcap_sizes': {}
                },
                'threats': self.get_threats_data(min_score=30),
                'status': 'healthy'
            }

            # Statistiche pacchetti per chain
            for chain in ['INPUT', 'OUTPUT', 'FORWARD']:
                try:
                    result = self.run_command(['iptables', '-L', chain, '-n', '-v', '-x'], check=False)
                    if result.returncode == 0:
                        # Somma tutti i pacchetti
                        total = sum(rule['pkts'] for rule in data['rules'][chain])
                        data['stats']['total_packets'][chain] = total
                except Exception:
                    data['stats']['total_packets'][chain] = 0

            # Counters delle chain di drop create da firewall-init.sh.
            # Quando il firewall non è inizializzato, le chain non esistono
            # → mettiamo 0 silenziosamente.
            for direction, chain_name in (('input', 'LOG_INPUT_DROP'), ('output', 'LOG_OUTPUT_DROP')):
                try:
                    res = self.run_command(['iptables', '-L', chain_name, '-v', '-n', '-x'], check=False)
                    if res.returncode != 0:
                        continue
                    # L'header chain è del tipo:
                    #   "Chain LOG_INPUT_DROP (NN references)"
                    # Il riepilogo del totale pacchetti non è nell'header;
                    # sommiamo i pkts di ogni regola della chain.
                    total = 0
                    for line in res.stdout.split('\n'):
                        line = line.strip()
                        if not line or line.startswith('Chain ') or line.startswith('pkts'):
                            continue
                        parts = line.split()
                        if not parts:
                            continue
                        try:
                            total += int(parts[0])
                        except (ValueError, IndexError):
                            continue
                    data['stats']['dropped'][direction] = total
                except Exception:
                    pass
            # Manteniamo `dropped_packets` come somma aggregata per retro-compat.
            data['stats']['dropped_packets'] = (
                data['stats']['dropped']['input'] + data['stats']['dropped']['output']
            )

            # Dimensioni PCAP
            for pcap_name in ['input_dropped.pcap', 'output_dropped.pcap']:
                pcap_path = f"{CONFIG['log_dir']}/{pcap_name}"
                if os.path.exists(pcap_path):
                    data['stats']['pcap_sizes'][f"{pcap_name.replace('.pcap', '_bytes')}"] = os.path.getsize(pcap_path)

            # Scrivi JSON
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)

            # Permessi sicuri
            os.chmod(output_path, 0o644)

            self.success(f"Stato esportato in: {output_path}")
            return True

        except Exception as e:
            self.error(f"Errore export JSON: {e}")
            return False


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description='Firewall Manager - Gestione avanzata iptables',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  %(prog)s --list                          # Lista tutte le regole
  %(prog)s --add-input 8080 tcp            # Apri porta 8080 TCP in INPUT
  %(prog)s --add-output 3306 tcp           # Apri porta 3306 TCP in OUTPUT
  %(prog)s --add-input 22 tcp --source 192.168.1.10 --comment "SSH da admin"
  %(prog)s --remove INPUT 5                # Rimuovi regola #5 da INPUT
  %(prog)s --analyze 24                    # Analizza traffico ultime 24h
  %(prog)s --threats 50                    # Mostra minacce con score >= 50
  %(prog)s --stats                         # Mostra statistiche
  %(prog)s --export-json                   # Esporta stato in JSON (default path)
  %(prog)s --export-json /tmp/fw.json      # Esporta in path custom
        """
    )
    
    # Comandi principali
    parser.add_argument('--list', '-l', metavar='CHAIN',
                       nargs='?', const='', default=None,
                       help='Lista regole (opzionale: INPUT|OUTPUT|FORWARD)')
    
    parser.add_argument('--add-input', metavar='PORT',
                       help='Aggiungi regola INPUT per porta')
    
    parser.add_argument('--add-output', metavar='PORT',
                       help='Aggiungi regola OUTPUT per porta')
    
    parser.add_argument('--protocol', '-p', default='tcp',
                       choices=['tcp', 'udp', 'icmp'],
                       help='Protocollo (default: tcp)')
    
    parser.add_argument('--source', '-s',
                       help='IP sorgente (solo per INPUT)')
    
    parser.add_argument('--dest', '-d',
                       help='IP destinazione (solo per OUTPUT)')
    
    parser.add_argument('--comment', '-c',
                       help='Commento per la regola')
    
    parser.add_argument('--remove', metavar=('CHAIN', 'NUM'),
                       nargs=2,
                       help='Rimuovi regola: CHAIN NUM')
    
    parser.add_argument('--analyze', metavar='HOURS',
                       type=int, nargs='?', const=1,
                       help='Analizza traffico bloccato (default: 1 ora)')
    
    parser.add_argument('--threats', metavar='MIN_SCORE',
                       type=int, nargs='?', const=30,
                       help='Mostra minacce (default: score >= 30)')
    
    parser.add_argument('--stats', action='store_true',
                       help='Mostra statistiche firewall')
    
    parser.add_argument('--save', action='store_true',
                       help='Salva regole correnti')
    
    parser.add_argument('--restore', action='store_true',
                       help='Ripristina regole salvate')

    parser.add_argument('--export-json', metavar='OUTPUT_PATH',
                       nargs='?', const='/opt/sentinelsuite/firedog/export/status.json',
                       help='Esporta stato completo in JSON (default: /opt/sentinelsuite/firedog/export/status.json)')

    args = parser.parse_args()
    
    # Istanzia manager
    fw = FirewallManager()
    
    # Esegui comando
    if args.list is not None:
        fw.list_rules(args.list if args.list else None)
    
    elif args.add_input:
        fw.add_rule_input(
            args.add_input,
            args.protocol,
            args.source,
            args.comment or ''
        )
    
    elif args.add_output:
        fw.add_rule_output(
            args.add_output,
            args.protocol,
            args.dest,
            args.comment or ''
        )
    
    elif args.remove:
        fw.remove_rule(args.remove[0], int(args.remove[1]))
    
    elif args.analyze:
        fw.analyze_dropped_traffic(args.analyze)
    
    elif args.threats is not None:
        fw.show_threats(args.threats)
    
    elif args.stats:
        fw.show_stats()
    
    elif args.save:
        fw.save_rules()
        fw.success("Regole salvate")
    
    elif args.restore:
        fw.restore_rules()

    elif args.export_json is not None:
        fw.export_json(args.export_json)

    else:
        parser.print_help()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrotto dall'utente")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}Errore fatale:{Colors.RESET} {e}", file=sys.stderr)
        sys.exit(1)

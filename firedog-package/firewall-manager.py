#!/usr/bin/env python3
"""
Firewall Manager CLI
Gestione avanzata firewall iptables con analisi traffico e scoring anomalie
Conforme a OWASP/NIST security standards
"""

import argparse
import subprocess
import shlex
import sys
import os
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import ipaddress

# Configurazione
CONFIG = {
    'rules_file': '/etc/firewall/iptables.rules',
    'custom_rules': '/etc/firewall/custom_rules.conf',
    'firedog_conf': '/etc/firewall/firedog.conf',
    'log_dir': '/var/log/ulogd',
    'state_file': '/var/lib/firewall/state.json',
    'min_uid': 1000,  # UID minimo per sicurezza
    # ipset del ban SSH brute-force (vedi SSH_PROTECT_BAN_DURATION in
    # firedog.conf e firewall-init.sh): nome set e file di persistenza
    # devono restare in sync con SSH_BANSET/SSH_BANSET_SAVE là.
    'ssh_banset': 'ssh_banned',
    'ssh_banset_save': '/etc/firewall/ssh_banned.save',
    # Versione installata del pacchetto target, seedata da install.sh —
    # fonte unica, mai più una stringa letterale dentro export_json (era
    # '1.0.1' hardcoded e non si è mai più mosso da lì).
    'version_file': '/opt/sentinelsuite/firedog/VERSION',
    'update_check_state': '/opt/sentinelsuite/firedog/data/update_check.json',
    'update_check_url': 'https://raw.githubusercontent.com/Dognet-Technologies/firedog/stabile/firedog-package/VERSION',
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


def load_firedog_conf(path: str = None) -> Dict[str, str]:
    """Legge /etc/firewall/firedog.conf (formato KEY="value", sourceable da
    bash — vedi firewall-init.sh). Righe vuote/commenti ignorati. File
    assente o illeggibile → dict vuoto (nessuna interfaccia esclusa, nessuna
    porta extra: comportamento di default).
    """
    conf_path = path or CONFIG['firedog_conf']
    values: Dict[str, str] = {}
    try:
        with open(conf_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                values[key.strip()] = value.strip().strip('"').strip("'")
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return values


# Impostazioni pcap configurabili da settings (UI → SystemSettings →
# dog-agent riceve CommandAction::UpdatePcapConfig e scrive queste chiavi
# direttamente in firedog.conf, vedi dog_agent/src/targets/firedog.rs
# update_pcap_config/upsert_conf_line — nessun demone da riavviare, il file
# viene riletto qui ad ogni invocazione). PCAP_SAVE_PATH sovrascrive
# CONFIG['log_dir'] per TUTTI i punti che lo referenziano (nessun altro punto
# di modifica necessario). PCAP_ANALYSIS_TOOL: 'tcpdump' (default, storico) o
# 'tshark', validato a runtime in analyze_dropped_traffic (fallback a tcpdump
# se il binario scelto non è installato). PCAP_FILTER_N (N=1..5): stringhe di
# filtro custom, sintassi opaca al tool scelto (BPF per tcpdump, display
# filter per tshark). Validati per sicurezza (non per correttezza semantica
# BPF/display-filter) in validate_pcap_filter(), chiamata da
# analyze_with_custom_filter prima di ogni esecuzione — un filtro che
# fallisce la validazione viene scartato con un warning, non eseguito.
_firedog_conf = load_firedog_conf()
if _firedog_conf.get('PCAP_SAVE_PATH'):
    CONFIG['log_dir'] = _firedog_conf['PCAP_SAVE_PATH']
CONFIG['pcap_analysis_tool'] = _firedog_conf.get('PCAP_ANALYSIS_TOOL', 'tcpdump').strip() or 'tcpdump'
CONFIG['pcap_custom_filters'] = [
    _firedog_conf[k] for k in sorted(_firedog_conf) if k.startswith('PCAP_FILTER_') and _firedog_conf[k]
][:5]

# Giorni tra un controllo aggiornamenti e il successivo (vedi check_for_updates
# sotto). "0"/vuoto/non numerico = disabilitato: nessuna chiamata di rete
# silenziosa su un target che non l'ha richiesto esplicitamente.
try:
    CONFIG['update_check_interval_days'] = max(0, int((_firedog_conf.get('UPDATE_CHECK_INTERVAL_DAYS') or '0').strip()))
except ValueError:
    CONFIG['update_check_interval_days'] = 0


def read_local_version() -> str:
    """Versione installata del pacchetto target (file VERSION, seedato da
    install.sh). Assente su un install più vecchio di questa feature, o se
    il file è stato rimosso a mano — stringa vuota, non un'eccezione: la UI
    mostra "Not installed" come già fa oggi quando firedog_version è vuota.
    """
    try:
        return Path(CONFIG['version_file']).read_text().strip()
    except (FileNotFoundError, PermissionError, OSError):
        return ''


MAX_PCAP_FILTER_LENGTH = 200


def validate_pcap_filter(filter_str: str) -> Optional[str]:
    """Ritorna un messaggio d'errore se il filtro pcap custom NON è
    accettabile, altrimenti None.

    Vincolo di sicurezza: nessun token (dopo shlex.split) può iniziare con
    '-'. In sintassi BPF (tcpdump) o display-filter (tshark) legittima nessun
    token valido inizia con '-' — sono sempre keyword/operatori/valori (es.
    "host 1.2.3.4 and tcp port 22"). Bloccarlo previene l'injection di flag
    tcpdump arbitrari (es. -z, che esegue un comando esterno se combinato con
    -C/-G) qualora il filtro finisca mai per essere interpretato come più
    argv separati — difesa in profondità: il chiamante deve comunque passare
    il filtro come UN SOLO elemento di argv, mai splittato, questo controllo
    è la seconda rete, non l'unica.
    """
    if not filter_str or not filter_str.strip():
        return "il filtro non può essere vuoto"
    if len(filter_str) > MAX_PCAP_FILTER_LENGTH:
        return f"supera la lunghezza massima di {MAX_PCAP_FILTER_LENGTH} caratteri"
    try:
        tokens = shlex.split(filter_str)
    except ValueError as e:
        return f"sintassi non valida: {e}"
    if any(tok.startswith('-') for tok in tokens):
        return "non può contenere token che iniziano con '-' (riservato a flag, non ammessi in un filtro)"
    return None


def _version_tuple(v: str) -> Tuple[int, ...]:
    """'1.2.10' -> (1, 2, 10). Il primo componente non numerico TRONCA il
    parsing invece di sollevare un'eccezione (es. '1.2.0-rc1' -> (1, 2, 0)),
    così un tag non-standard sul remoto degrada a confronto parziale invece
    di rompere il check."""
    parts: List[int] = []
    for chunk in v.strip().lstrip('v').split('.'):
        if not chunk.isdigit():
            break
        parts.append(int(chunk))
    return tuple(parts)


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

    def _ssh_banset_exists(self) -> bool:
        """Verifica se la ipset dei ban SSH esiste (SSH_PROTECT_BAN_DURATION
        disabilitato o mai attivato -> nessun set creato da firewall-init.sh)."""
        result = self.run_command(
            ['ipset', 'list', '-n', CONFIG['ssh_banset']], check=False
        )
        return result.returncode == 0

    def list_bans(self):
        """Lista gli IP attualmente bannati da SSH_PROTECT (ipset ssh_banned).
        Richiede SSH_PROTECT_BAN_DURATION configurato in firedog.conf."""
        if not self._ssh_banset_exists():
            self.info(
                "Nessun ban attivo: SSH_PROTECT_BAN_DURATION non configurato "
                "(o '0') in /etc/firewall/firedog.conf, oppure firewall-init.sh "
                "non è ancora stato rilanciato dopo averlo impostato."
            )
            return

        result = self.run_command(
            ['ipset', 'list', CONFIG['ssh_banset']], check=False
        )
        if result.returncode != 0:
            self.error(f"Errore lettura ipset {CONFIG['ssh_banset']}: {result.stderr.strip()}")
            return

        # Le entry stanno dopo la riga "Members:"; formato per entry con
        # timeout: "1.2.3.4 timeout 1734" (secondi rimanenti, permanente se
        # il set non ha timeout attivo per quella entry -> nessun suffisso).
        lines = result.stdout.splitlines()
        try:
            start = lines.index('Members:') + 1
        except ValueError:
            start = len(lines)
        members = [l for l in lines[start:] if l.strip()]

        if not members:
            self.info(f"Nessun IP attualmente bannato (ipset {CONFIG['ssh_banset']} vuota)")
            return

        print(f"\n{Colors.BOLD}=== SSH ban attivi ({CONFIG['ssh_banset']}) ==={Colors.RESET}\n")
        for m in members:
            parts = m.split()
            ip = parts[0]
            # ipset stampa sempre "timeout N" per entry quando il set ha il
            # timeout abilitato (creato con 'timeout 0'): N=0 significa
            # nessuna scadenza (ban permanente), non "scaduto adesso".
            secs = int(parts[parts.index('timeout') + 1]) if 'timeout' in parts else 0
            if secs > 0:
                remaining = str(timedelta(seconds=secs))
                print(f"  {ip:<20} scade tra {remaining}")
            else:
                print(f"  {ip:<20} {Colors.RED}permanente{Colors.RESET}")
        print()

    def unban(self, ip: str) -> bool:
        """Rimuove un IP dal ban SSH_PROTECT (ipset ssh_banned), incluso un
        ban permanente."""
        if not self.validate_ip(ip):
            self.error(f"IP non valido: {ip}")
            return False

        if not self._ssh_banset_exists():
            self.error(
                "Nessuna ipset di ban attiva (SSH_PROTECT_BAN_DURATION non "
                "configurato): niente da rimuovere."
            )
            return False

        result = self.run_command(
            ['ipset', 'del', CONFIG['ssh_banset'], ip], check=False
        )
        if result.returncode != 0:
            self.error(f"{ip} non risulta bannato, o errore: {result.stderr.strip()}")
            return False

        # Persisti subito la rimozione, altrimenti un reboot prima del
        # prossimo salvataggio da cron farebbe tornare l'IP bannato
        # ripristinandolo dal file salvato precedente.
        save_result = self.run_command(
            ['ipset', 'save', CONFIG['ssh_banset'], '-f', CONFIG['ssh_banset_save']],
            check=False
        )
        if save_result.returncode != 0:
            self.warning(f"Rimosso ma non persistito su disco: {save_result.stderr.strip()}")

        self.success(f"{ip} rimosso dal ban SSH_PROTECT")
        return True

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

        # Tool scelto esplicitamente in settings (PCAP_ANALYSIS_TOOL), non più
        # auto-rilevato — se il binario scelto non è installato, fallback a
        # tcpdump con avviso invece di scavalcare silenziosamente la scelta.
        analyzer = CONFIG['pcap_analysis_tool']
        if not self.check_command(analyzer):
            if analyzer != 'tcpdump':
                self.warning(f"'{analyzer}' non installato, uso tcpdump")
            analyzer = 'tcpdump'

        if not self.check_command(analyzer):
            self.error("Richiesto tcpdump o tshark per analisi. Installa con: apt install tcpdump (Debian/Ubuntu) o zypper install tcpdump (openSUSE)")
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

            for custom_filter in CONFIG['pcap_custom_filters']:
                print(f"\n{Colors.YELLOW}Filtro custom: {custom_filter}{Colors.RESET}")
                self.analyze_with_custom_filter(pcap, analyzer, custom_filter, limit)

    def analyze_with_custom_filter(self, pcap: str, analyzer: str, custom_filter: str, limit: int):
        """Esegue un filtro custom (BPF per tcpdump, display filter per
        tshark) definito dall'utente in settings, e stampa le righe risultanti
        (troncate a `limit`)."""
        err = validate_pcap_filter(custom_filter)
        if err:
            self.warning(f"Filtro custom scartato (validazione fallita): {err}")
            return
        try:
            if analyzer == 'tcpdump':
                # custom_filter passato come UN SOLO elemento di argv, mai
                # shlex.split() in token separati: tcpdump concatena comunque
                # gli argomenti posizionali in un'unica espressione filtro
                # (stesso risultato per sintassi BPF legittima), ma uno split
                # permetterebbe a un filtro tipo "-C 1 -z /path/evil and host
                # X" di essere interpretato come FLAG separati — incluso -z,
                # che esegue un comando esterno. La validate_pcap_filter sopra
                # è una seconda rete (rifiuta comunque token con '-'), questo
                # è il fix strutturale: mai passare input non fidato come più
                # argv quando un singolo argv produce lo stesso filtro valido.
                cmd = ['tcpdump', '-nn', '-r', pcap, custom_filter]
            else:
                cmd = ['tshark', '-r', pcap, '-Y', custom_filter]
            result = subprocess.run(cmd, capture_output=True, text=True)
            lines = [ln for ln in result.stdout.split('\n') if ln.strip()][:limit]
            if lines:
                print('\n'.join(lines))
            elif result.stderr:
                self.warning(f"Filtro '{custom_filter}' non valido per {analyzer}: {result.stderr.strip()[:200]}")
            else:
                print("(nessun risultato)")
        except Exception as e:
            self.error(f"Errore filtro custom: {e}")
    
    def analyze_with_tcpdump(self, pcap: str, hours: int, limit: int):
        """Analizza PCAP con tcpdump"""
        try:
            # pcap/limit passano per un template di shell (pipeline awk/cut/
            # sort): quotati esplicitamente per evitare command injection —
            # pcap viene da CONFIG['log_dir'] (configurabile da settings),
            # limit da input utente CLI.
            cmd = f"tcpdump -nn -r {shlex.quote(pcap)} 2>/dev/null | awk '{{print $3}}' | cut -d'.' -f1-4 | sort | uniq -c | sort -rn | head -{int(limit)}"
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

        # Verifica IP privati (meno sospetti). ip arriva da un parsing di
        # output tcpdump su dati di rete non fidati (show_threats/
        # get_threats_data): se non è un IP valido, non proseguire — evita
        # sia crash a valle sia interpolazione di valori inattesi nel
        # comando shell sotto.
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private:
                reasons.append("IP privato (-10)")
                score -= 10
        except ValueError:
            return 0, []

        # Controlla nel PCAP quante volte compare questo IP
        pcap_input = f"{CONFIG['log_dir']}/input_dropped.pcap"

        if os.path.exists(pcap_input):
            try:
                cmd = f"tcpdump -nn -r {shlex.quote(pcap_input)} 'src host {shlex.quote(ip)}' 2>/dev/null | wc -l"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                count = int(result.stdout.strip())
                
                # "count" = pacchetti bloccati dal firewall per questo IP,
                # estratti da input_dropped.pcap (catturato via NFLOG/ulogd2
                # dalla catena LOG_INPUT_DROP). Sono tentativi di connessione
                # respinti, non sessioni andate a buon fine.
                if count > 100:
                    score += 50
                    reasons.append(f"Molti pacchetti bloccati dal firewall ({count}) +50")
                elif count > 50:
                    score += 30
                    reasons.append(f"Numerosi pacchetti bloccati dal firewall ({count}) +30")
                elif count > 10:
                    score += 15
                    reasons.append(f"Alcuni pacchetti bloccati dal firewall ({count}) +15")

            except Exception:
                pass
        
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
            cmd = f"tcpdump -nn -r {shlex.quote(pcap_input)} 2>/dev/null | awk '{{print $3}}' | cut -d'.' -f1-4 | sort -u"
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

    @staticmethod
    def _extract_top_port_proto(pcap_lines):
        """Dato l'output di tcpdump per un singolo source IP, ritorna
        (dest_port, protocol) più frequenti.

        Formato righe tcpdump '-nn':
          14:23:01.123 IP 1.2.3.4.5555 > 5.6.7.8.443: Flags [S], ...
          14:23:01.234 IP6 ... > ... : ...
          14:23:02.345 IP 1.2.3.4 > 5.6.7.8: ICMP echo request, ...

        Il protocollo è inferito così:
          - 'ICMP' presente nella riga → icmp
          - 'Flags' presente (TCP SYN/ACK/...) → tcp
          - altrimenti se la riga matcha pattern porta → udp
          - fallback: '' (vuoto, il backend visualizza '-')

        dest_port è preso dopo l'ultimo punto a sinistra dei ':' nel
        token destinazione (es. '5.6.7.8.443' → 443). Mancante per ICMP.
        """
        from collections import Counter
        import re

        port_counter: Counter = Counter()
        proto_counter: Counter = Counter()
        # Pattern destinazione tipo 'a.b.c.d.PORT:' con porta numerica.
        port_re = re.compile(r'>\s+\S+?\.(\d+):')

        for line in pcap_lines:
            if 'ICMP' in line:
                proto_counter['icmp'] += 1
                continue
            m = port_re.search(line)
            if m:
                try:
                    port_counter[int(m.group(1))] += 1
                except ValueError:
                    pass
                # 'Flags' in line ⇒ TCP. Niente Flags + porta valida ⇒ UDP.
                proto_counter['tcp' if 'Flags' in line else 'udp'] += 1

        top_port = port_counter.most_common(1)[0][0] if port_counter else None
        top_proto = proto_counter.most_common(1)[0][0] if proto_counter else ''
        return top_port, top_proto

    def get_threats_data(self, min_score: int = 30) -> List[Dict]:
        """Ottieni dati minacce in formato strutturato"""

        threats = []
        pcap_input = f"{CONFIG['log_dir']}/input_dropped.pcap"

        if not os.path.exists(pcap_input):
            return threats

        try:
            cmd = f"tcpdump -nn -r {shlex.quote(pcap_input)} 2>/dev/null | awk '{{print $3}}' | cut -d'.' -f1-4 | sort -u"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            ips = [ip.strip() for ip in result.stdout.split('\n') if ip.strip()]

            for ip in ips[:50]:
                score, reasons = self.get_threat_score(ip)
                if score >= min_score:
                    # Estraiamo tutte le righe pcap per questo source IP, ci
                    # servono sia il count totale sia il dest_port + protocol
                    # più frequenti.
                    cmd_lines = f"tcpdump -nn -r {shlex.quote(pcap_input)} 'src host {shlex.quote(ip)}' 2>/dev/null"
                    lines_result = subprocess.run(
                        cmd_lines, shell=True, capture_output=True, text=True
                    )
                    pcap_lines = [
                        ln for ln in lines_result.stdout.split('\n') if ln.strip()
                    ]
                    attempts = len(pcap_lines)

                    dest_port, protocol = self._extract_top_port_proto(pcap_lines)

                    threats.append({
                        'ip': ip,
                        'score': score,
                        'attempts': attempts,
                        'reasons': reasons,
                        'dest_port': dest_port,
                        'protocol': protocol,
                    })

            # Ordina per score
            threats.sort(key=lambda x: x['score'], reverse=True)

        except Exception:
            pass

        return threats

    def parse_iptables_rules(self, chain: str) -> Optional[List[Dict]]:
        """Parsa regole iptables in formato strutturato.

        Ritorna None (non []) se il comando o il parsing falliscono: il
        chiamante (export_json) deve poter distinguere "lettura fallita" da
        "la chain è genuinamente vuota". Confondere le due è quello che
        causava la sparizione intermittente delle regole in UI: un fallimento
        transitorio produceva [], export_json lo scriveva nello status.json
        come se la chain fosse vuota, e _sync_firewall_rules lato backend
        interpretava "nessuna regola nello snapshot" come "l'admin le ha
        tutte rimosse", cancellando le FirewallRule non-custom della chain.
        """

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

        except Exception as e:
            self.error(f"Lettura regole chain {chain} fallita, snapshot scartato: {e}")
            return None

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

    def get_interfaces(self) -> List[Dict]:
        """Elenca le interfacce di rete (NIC) dell'host, esclusa loopback.

        Un host può avere più NIC (LAN interna, IP pubblico, rete di
        management...); il server le usa per popolare NetworkInterface e
        permettere regole firewall scoped a una NIC specifica. Usa
        `ip -j addr show` (JSON, supportato da iproute2 da anni su ogni
        distro target) invece di dipendenze pip aggiuntive sul target.

        Filtrata da MONITORED_INTERFACES in /etc/firewall/firedog.conf se
        valorizzata (vuoto/assente = tutte le interfacce rilevate).
        Include i contatori rx/tx (snapshot cumulativo del kernel, non
        delta) da `ip -s -j link show`.
        """

        interfaces = []
        try:
            result = self.run_command(['ip', '-j', 'addr', 'show'], check=False)
            if result.returncode != 0:
                return interfaces

            stats_by_name = self._get_interface_stats()

            conf = load_firedog_conf()
            monitored = {
                n.strip() for n in conf.get('MONITORED_INTERFACES', '').split(',') if n.strip()
            }

            for link in json.loads(result.stdout):
                name = link.get('ifname', '')
                if not name or name == 'lo' or link.get('link_type') == 'loopback':
                    continue
                if monitored and name not in monitored:
                    continue

                ip_address = None
                for addr in link.get('addr_info', []):
                    # Preferisci il primo IPv4 globale; fallback al primo indirizzo
                    # qualsiasi se non ce n'è uno (interfaccia solo IPv6).
                    if addr.get('family') == 'inet' and addr.get('scope') == 'global':
                        ip_address = addr.get('local')
                        break
                if ip_address is None:
                    addr_info = link.get('addr_info', [])
                    if addr_info:
                        ip_address = addr_info[0].get('local')

                stats = stats_by_name.get(name, {})
                interfaces.append({
                    'name': name,
                    'ip_address': ip_address,
                    'mac_address': link.get('address', ''),
                    'is_up': 'UP' in link.get('flags', []),
                    'rx_bytes': stats.get('rx_bytes', 0),
                    'tx_bytes': stats.get('tx_bytes', 0),
                    'rx_packets': stats.get('rx_packets', 0),
                    'tx_packets': stats.get('tx_packets', 0),
                })
        except Exception:
            pass

        return interfaces

    def _get_interface_stats(self) -> Dict[str, Dict]:
        """Contatori rx/tx per NIC via `ip -s -j link show` (cumulativi del
        kernel dal boot, come i counter iptables — il server ne fa il delta
        tra due snapshot se serve una velocità istantanea).
        """
        stats = {}
        try:
            result = self.run_command(['ip', '-s', '-j', 'link', 'show'], check=False)
            if result.returncode != 0:
                return stats
            for link in json.loads(result.stdout):
                name = link.get('ifname', '')
                s = link.get('stats64') or link.get('stats') or {}
                rx = s.get('rx', {})
                tx = s.get('tx', {})
                stats[name] = {
                    'rx_bytes': int(rx.get('bytes', 0) or 0),
                    'tx_bytes': int(tx.get('bytes', 0) or 0),
                    'rx_packets': int(rx.get('packets', 0) or 0),
                    'tx_packets': int(tx.get('packets', 0) or 0),
                }
        except Exception:
            pass
        return stats

    def check_for_updates(self) -> Dict:
        """Confronta la versione locale con quella pubblicata su `stabile`,
        al più una volta ogni UPDATE_CHECK_INTERVAL_DAYS (0 = disabilitato).

        Chiamato anche da export_json ad ogni invocazione (ogni 5 minuti via
        cron): il risultato è cacheato su file e riusato finché non è di
        nuovo "dovuto" — non deve fare una richiesta di rete ad ogni singolo
        export solo perché qualcuno ha configurato un controllo settimanale.
        """
        if CONFIG['update_check_interval_days'] <= 0:
            return {'enabled': False}

        state_path = Path(CONFIG['update_check_state'])
        try:
            cached = json.loads(state_path.read_text())
        except (FileNotFoundError, PermissionError, OSError, json.JSONDecodeError):
            cached = {}

        now = datetime.now(timezone.utc)
        checked_at = cached.get('checked_at')
        if checked_at:
            try:
                last = datetime.fromisoformat(checked_at)
                if now - last < timedelta(days=CONFIG['update_check_interval_days']):
                    return {**cached, 'enabled': True}
            except ValueError:
                pass

        local_version = read_local_version()
        result = {
            'enabled': True,
            'checked_at': now.isoformat(),
            'local_version': local_version,
            'latest_version': cached.get('latest_version', ''),
            'update_available': False,
            'error': None,
        }
        try:
            with urllib.request.urlopen(CONFIG['update_check_url'], timeout=10) as resp:
                remote_version = resp.read().decode('utf-8', errors='replace').strip()
            result['latest_version'] = remote_version
            result['update_available'] = _version_tuple(remote_version) > _version_tuple(local_version)
        except (urllib.error.URLError, OSError, ValueError) as e:
            result['error'] = str(e)

        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(result))
        except (PermissionError, OSError):
            pass

        return result

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
                # Tutte le NIC dell'host (esclusa loopback): alimenta
                # NetworkInterface lato server per il supporto multi-NIC.
                'interfaces': self.get_interfaces(),
                # Timestamp ISO-8601 con TZ UTC esplicito. datetime.now() senza
                # argomenti restituisce un naive datetime → il server lo
                # interpreta come ora locale (Europe/Rome) e applica un doppio
                # offset, sfasando di 2h tutto il chart.
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'firedog_version': read_local_version(),
                # Esito dell'ultimo controllo aggiornamenti (cacheato, vedi
                # check_for_updates): {'enabled': False} se
                # UPDATE_CHECK_INTERVAL_DAYS non è configurato in firedog.conf.
                'update_check': self.check_for_updates(),
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
                # Chain omesse (non incluse nel dict) se parse_iptables_rules
                # ritorna None: una lettura fallita non deve mai apparire come
                # "chain svuotata" al backend, altrimenti _sync_firewall_rules
                # cancella le FirewallRule note per quella chain.
                'rules': {
                    chain: parsed
                    for chain, parsed in (
                        ('INPUT', self.parse_iptables_rules('INPUT')),
                        ('OUTPUT', self.parse_iptables_rules('OUTPUT')),
                        ('FORWARD', self.parse_iptables_rules('FORWARD')),
                    )
                    if parsed is not None
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

            # Statistiche pacchetti per chain. data['rules'] può non avere
            # la chiave (lettura regole fallita, vedi sopra): .get(chain, [])
            # evita un KeyError che farebbe fallire l'intero export.
            for chain in ['INPUT', 'OUTPUT', 'FORWARD']:
                try:
                    result = self.run_command(['iptables', '-L', chain, '-n', '-v', '-x'], check=False)
                    if result.returncode == 0:
                        # Somma tutti i pacchetti
                        total = sum(rule['pkts'] for rule in data['rules'].get(chain, []))
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
  %(prog)s --list-bans                     # IP bannati da SSH_PROTECT (SSH_PROTECT_BAN_DURATION)
  %(prog)s --unban 203.0.113.5             # Rimuovi un ban (anche permanente)
  %(prog)s --version                       # Versione installata del pacchetto target
  %(prog)s --check-updates                 # Controlla aggiornamenti (vedi UPDATE_CHECK_INTERVAL_DAYS)
        """
    )

    parser.add_argument('--version', action='store_true',
                       help='Mostra la versione installata del pacchetto target (file VERSION)')

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

    parser.add_argument('--list-bans', action='store_true',
                       help='Lista IP bannati da SSH_PROTECT (richiede SSH_PROTECT_BAN_DURATION in firedog.conf)')

    parser.add_argument('--unban', metavar='IP',
                       help='Rimuove un IP dal ban SSH_PROTECT (anche permanente)')

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

    parser.add_argument('--check-updates', action='store_true',
                       help='Controlla se è disponibile un aggiornamento (rispetta UPDATE_CHECK_INTERVAL_DAYS in firedog.conf)')

    args = parser.parse_args()

    # --version non richiede privilegi root: nessuna istanza di FirewallManager
    # (che li impone per qualunque altro comando), solo lettura di un file.
    if args.version:
        print(read_local_version() or 'unknown')
        return

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

    elif args.list_bans:
        fw.list_bans()

    elif args.unban:
        fw.unban(args.unban)

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

    elif args.check_updates:
        result = fw.check_for_updates()
        if not result.get('enabled'):
            fw.info("Controllo aggiornamenti disabilitato (UPDATE_CHECK_INTERVAL_DAYS non impostato in firedog.conf)")
        elif result.get('error'):
            fw.warning(f"Controllo aggiornamenti fallito: {result['error']}")
        elif result.get('update_available'):
            fw.warning(f"Aggiornamento disponibile: v{result.get('local_version') or '?'} -> v{result.get('latest_version')}")
        else:
            fw.success(f"Nessun aggiornamento disponibile (locale: v{result.get('local_version') or 'unknown'})")

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

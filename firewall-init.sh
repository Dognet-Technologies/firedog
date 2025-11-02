#!/bin/bash
#
# Firewall Initialization Script
# Implementa policy DROP di default con protezioni avanzate
# Conforme a OWASP/NIST security best practices
#

set -euo pipefail

# Variabili configurazione
LOG_FILE="/var/log/firewall-init.log"
RULES_DIR="/etc/firewall"
CUSTOM_RULES="${RULES_DIR}/custom_rules.conf"

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Funzione di logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error_exit() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    log "ERROR: $1"
    exit 1
}

success() {
    echo -e "${GREEN}[OK]${NC} $1"
    log "SUCCESS: $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    log "WARNING: $1"
}

# Verifica privilegi root
[[ $EUID -ne 0 ]] && error_exit "Questo script richiede privilegi root (usa sudo)"

# Verifica dipendenze
check_dependencies() {
    # log "Verifica dipendenze..."
    
    # local deps=("iptables" "iptables-save" "iptables-restore" "ulogd2")
    # for dep in "${deps[@]}"; do
    #     if ! command -v "$dep" &>/dev/null; then
    #         error_exit "Dipendenza mancante: $dep. Installa con: apt install iptables ulogd2"
    #     fi
    # done
    
    # Verifica moduli kernel
    local modules=("nfnetlink_log" "xt_NFLOG" "xt_recent" "xt_conntrack" "xt_limit")
    for mod in "${modules[@]}"; do
        if ! lsmod | grep -q "^$mod"; then
            modprobe "$mod" 2>/dev/null || warning "Impossibile caricare modulo: $mod"
        fi
    done
    
    success "Dipendenze verificate"
}

# Crea directory configurazione
setup_directories() {
    log "Creazione directory configurazione..."
    mkdir -p "$RULES_DIR"
    touch "$CUSTOM_RULES"
    chmod 600 "$CUSTOM_RULES"
    success "Directory create"
}

# Flush regole esistenti
flush_rules() {
    log "Rimozione regole esistenti..."
    
    iptables -F
    iptables -X
    iptables -t nat -F
    iptables -t nat -X
    iptables -t mangle -F
    iptables -t mangle -X
    iptables -t raw -F
    iptables -t raw -X
    
    # Reset contatori
    iptables -Z
    
    success "Regole precedenti rimosse"
}

# Policy di default DROP
set_default_policy() {
    log "Impostazione policy di default DROP..."
    
    iptables -P INPUT DROP
    iptables -P FORWARD DROP
    iptables -P OUTPUT DROP
    
    success "Policy DROP impostate"
}

# Chain personalizzate per logging e protezione
create_custom_chains() {
    log "Creazione chain personalizzate..."
    
    # Chain per logging INPUT droppato
    iptables -N LOG_INPUT_DROP
    iptables -A LOG_INPUT_DROP -j NFLOG --nflog-group 1 --nflog-prefix "INPUT_DROP: " --nflog-threshold 10
    iptables -A LOG_INPUT_DROP -j DROP
    
    # Chain per logging OUTPUT droppato
    iptables -N LOG_OUTPUT_DROP
    iptables -A LOG_OUTPUT_DROP -j NFLOG --nflog-group 2 --nflog-prefix "OUTPUT_DROP: " --nflog-threshold 10
    iptables -A LOG_OUTPUT_DROP -j DROP
    
    # Chain per port scan detection
    iptables -N PORT_SCAN
    iptables -A PORT_SCAN -m recent --name portscan --set
    iptables -A PORT_SCAN -m recent --name portscan --update --seconds 60 --hitcount 15 -j LOG_INPUT_DROP
    iptables -A PORT_SCAN -j DROP
    
    # Chain per SYN flood protection
    iptables -N SYN_FLOOD
    iptables -A SYN_FLOOD -m limit --limit 10/s --limit-burst 20 -j RETURN
    iptables -A SYN_FLOOD -j LOG_INPUT_DROP
    
    # Chain per SSH brute force protection
    iptables -N SSH_PROTECT
    iptables -A SSH_PROTECT -m recent --name ssh_attack --set
    iptables -A SSH_PROTECT -m recent --name ssh_attack --update --seconds 60 --hitcount 4 -j LOG_INPUT_DROP
    iptables -A SSH_PROTECT -j ACCEPT
    
    # Chain per ICMP flood protection
    iptables -N ICMP_FLOOD
    iptables -A ICMP_FLOOD -m limit --limit 5/s --limit-burst 10 -j RETURN
    iptables -A ICMP_FLOOD -j LOG_INPUT_DROP
    
    success "Chain personalizzate create"
}

# Regole di base per loopback
setup_loopback() {
    log "Configurazione loopback..."
    
    iptables -A INPUT -i lo -j ACCEPT
    iptables -A OUTPUT -o lo -j ACCEPT
    
    success "Loopback configurato"
}

# Protezione contro attacchi comuni
setup_attack_protection() {
    log "Configurazione protezioni anti-attacco..."
    
    # Drop pacchetti invalidi
    iptables -A INPUT -m conntrack --ctstate INVALID -j LOG_INPUT_DROP
    iptables -A OUTPUT -m conntrack --ctstate INVALID -j LOG_OUTPUT_DROP
    
    # Protezione contro NULL packets
    iptables -A INPUT -p tcp --tcp-flags ALL NONE -j LOG_INPUT_DROP
    
    # Protezione contro XMAS packets
    iptables -A INPUT -p tcp --tcp-flags ALL ALL -j LOG_INPUT_DROP
    
    # Protezione contro pacchetti frammentati sospetti
    iptables -A INPUT -f -j LOG_INPUT_DROP
    
    # Protezione contro SYN-FIN packets
    iptables -A INPUT -p tcp --tcp-flags SYN,FIN SYN,FIN -j LOG_INPUT_DROP
    
    # Protezione contro SYN-RST packets
    iptables -A INPUT -p tcp --tcp-flags SYN,RST SYN,RST -j LOG_INPUT_DROP
    
    # SYN flood protection
    iptables -A INPUT -p tcp --syn -j SYN_FLOOD
    
    # Protezione contro spoofing (martian packets)
    iptables -A INPUT -s 127.0.0.0/8 ! -i lo -j LOG_INPUT_DROP
    iptables -A INPUT -s 0.0.0.0/8 -j LOG_INPUT_DROP
    iptables -A INPUT -s 169.254.0.0/16 -j LOG_INPUT_DROP
    iptables -A INPUT -s 224.0.0.0/4 -j LOG_INPUT_DROP
    iptables -A INPUT -s 240.0.0.0/5 -j LOG_INPUT_DROP
    
    success "Protezioni anti-attacco configurate"
}

# Regole INPUT - traffico in ingresso
setup_input_rules() {
    log "Configurazione regole INPUT..."
    
    # Accetta connessioni stabilite e correlate
    iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    
    # ICMP con rate limiting
    iptables -A INPUT -p icmp --icmp-type echo-request -j ICMP_FLOOD
    iptables -A INPUT -p icmp --icmp-type echo-reply -j ACCEPT
    iptables -A INPUT -p icmp --icmp-type destination-unreachable -j ACCEPT
    iptables -A INPUT -p icmp --icmp-type time-exceeded -j ACCEPT
    
    # SSH con protezione brute force (porta 22)
    iptables -A INPUT -p tcp --dport 22 -m conntrack --ctstate NEW -j SSH_PROTECT
    
    # HTTP/HTTPS per servizi web (commentato di default - abilitare se necessario)
    # iptables -A INPUT -p tcp --dport 80 -m conntrack --ctstate NEW -j ACCEPT
    # iptables -A INPUT -p tcp --dport 443 -m conntrack --ctstate NEW -j ACCEPT
    
    success "Regole INPUT configurate"
}

# Regole OUTPUT - traffico in uscita
setup_output_rules() {
    log "Configurazione regole OUTPUT..."
    
    # Accetta connessioni stabilite e correlate
    iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    
    # DNS (UDP e TCP)
    iptables -A OUTPUT -p udp --dport 53 -m conntrack --ctstate NEW -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 53 -m conntrack --ctstate NEW -j ACCEPT
    
    # NTP
    iptables -A OUTPUT -p udp --dport 123 -m conntrack --ctstate NEW -j ACCEPT
    
    # HTTP/HTTPS per aggiornamenti e web
    iptables -A OUTPUT -p tcp --dport 80 -m conntrack --ctstate NEW -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 443 -m conntrack --ctstate NEW -j ACCEPT
    
    # FTP passivo (per repository)
    iptables -A OUTPUT -p tcp --dport 21 -m conntrack --ctstate NEW -j ACCEPT
    
    # ICMP
    iptables -A OUTPUT -p icmp --icmp-type echo-request -j ACCEPT
    iptables -A OUTPUT -p icmp --icmp-type echo-reply -j ACCEPT
    
    success "Regole OUTPUT configurate"
}

# Carica regole personalizzate
load_custom_rules() {
    log "Caricamento regole personalizzate..."
    
    if [[ -f "$CUSTOM_RULES" ]] && [[ -s "$CUSTOM_RULES" ]]; then
        local count=0
        while IFS= read -r line; do
            # Ignora commenti e righe vuote
            [[ "$line" =~ ^#.*$ ]] && continue
            [[ -z "$line" ]] && continue
            
            # Esegui regola
            if eval "$line" 2>/dev/null; then
                ((count++))
            else
                warning "Regola non valida: $line"
            fi
        done < "$CUSTOM_RULES"
        
        success "Caricate $count regole personalizzate"
    else
        log "Nessuna regola personalizzata trovata"
    fi
}

# Regole finali di logging
setup_final_logging() {
    log "Configurazione logging finale..."
    
    # Log tutto il traffico droppato in INPUT
    iptables -A INPUT -j LOG_INPUT_DROP
    
    # Log tutto il traffico droppato in OUTPUT
    iptables -A OUTPUT -j LOG_OUTPUT_DROP
    
    success "Logging configurato"
}

# Salva regole per persistenza
save_rules() {
    log "Salvataggio regole per persistenza..."
    
    iptables-save > "${RULES_DIR}/iptables.rules"
    chmod 600 "${RULES_DIR}/iptables.rules"
    
    # Installa script per ripristino all'avvio
     
echo '#!/bin/bash' >> /etc/network/if-pre-up.d/iptables 
echo '/usr/sbin/iptables-restore < /etc/firewall/iptables.rules' >> /etc/network/if-pre-up.d/iptables 

    
    chmod +x /etc/network/if-pre-up.d/iptables
    
    success "Regole salvate in ${RULES_DIR}/iptables.rules"
}

# Mostra statistiche
show_stats() {
    echo ""
    echo "=========================================="
    echo "  Firewall Inizializzato Correttamente"
    echo "=========================================="
    echo ""
    echo "Policy attive:"
    iptables -L -n -v --line-numbers | head -20
    echo ""
    echo "Usa 'firewall-manager --help' per gestire il firewall"
    echo ""
}

# Main execution
main() {
    log "=== Avvio inizializzazione firewall ==="
    
    check_dependencies
    setup_directories
    flush_rules
    set_default_policy
    create_custom_chains
    setup_loopback
    setup_attack_protection
    setup_input_rules
    setup_output_rules
    load_custom_rules
    setup_final_logging
    save_rules
    show_stats
    
    log "=== Inizializzazione completata con successo ==="
}

# Esegui main
main "$@"

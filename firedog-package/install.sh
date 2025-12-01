#!/bin/bash
#
# Firewall Installation Script
# Installa e configura il sistema di firewall completo
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}"
cat << "EOF"
╔═══════════════════════════════════════════════╗
║   Firewall Installation Script                ║
║   Advanced iptables + ulogd2 + Management CLI ║
╚═══════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Verifica root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[ERROR]${NC} Questo script richiede privilegi root"
    exit 1
fi

# Verifica Debian/Ubuntu
if ! grep -Eiq 'debian|ubuntu' /etc/os-release; then
    echo -e "${YELLOW}[WARNING]${NC} Sistema non Debian/Ubuntu. Continuare? (y/n)"
    read -r response
    [[ "$response" != "y" ]] && exit 0
fi

echo -e "${GREEN}[1/11]${NC} Aggiornamento sistema..."
apt-get update -qq

echo -e "${GREEN}[2/11]${NC} Installazione dipendenze..."
apt-get install -y -qq \
    iptables \
    iptables-persistent \
    ulogd2 \
    python3 \
    python3-pip \
    tcpdump \
    logrotate \
    git

echo -e "${GREEN}[3/11]${NC} Setup utente microcyber..."

# Variabili
FIREDOG_USER="microcyber"
FIREDOG_HOME="/home/${FIREDOG_USER}"
FIREDOG_BASE_DIR="/opt/firedog"
FIREDOG_EXPORT_DIR="${FIREDOG_BASE_DIR}/export"
FIREDOG_SSH_DIR="${FIREDOG_BASE_DIR}/.ssh"
SSH_KEY_FILE="firedog_ssh_key.pub"

# Crea utente microcyber se non esiste con shell /bin/false (sicurezza)
if ! id -u "${FIREDOG_USER}" &>/dev/null; then
    echo "  → Creazione utente ${FIREDOG_USER} con shell /bin/false..."
    useradd -m -s /bin/false "${FIREDOG_USER}"
    echo -e "${GREEN}[OK]${NC} Utente ${FIREDOG_USER} creato"
else
    echo -e "${YELLOW}[INFO]${NC} Utente ${FIREDOG_USER} già esistente"

    # Aggiorna shell a /bin/false per sicurezza
    # Usa usermod se disponibile, altrimenti modifica direttamente /etc/passwd
    if command -v usermod &>/dev/null; then
        usermod -s /bin/false "${FIREDOG_USER}" 2>/dev/null || {
            # Fallback: modifica /etc/passwd direttamente
            sed -i "s|^\(${FIREDOG_USER}:.*:\)[^:]*$|\1/bin/false|" /etc/passwd
        }
    else
        # usermod non disponibile, modifica /etc/passwd direttamente
        sed -i "s|^\(${FIREDOG_USER}:.*:\)[^:]*$|\1/bin/false|" /etc/passwd
    fi

    echo "  → Shell aggiornata a /bin/false per sicurezza"
fi

# Crea directory SSH in /opt/firedog/.ssh (NON in home utente)
echo "  → Configurazione directory SSH in ${FIREDOG_SSH_DIR}..."
mkdir -p "${FIREDOG_SSH_DIR}"
touch "${FIREDOG_SSH_DIR}/authorized_keys"
chmod 700 "${FIREDOG_SSH_DIR}"
chmod 600 "${FIREDOG_SSH_DIR}/authorized_keys"
chown -R "${FIREDOG_USER}:${FIREDOG_USER}" "${FIREDOG_SSH_DIR}"

# Crea symlink da home a /opt/firedog/.ssh
if [[ ! -L "${FIREDOG_HOME}/.ssh" ]]; then
    rm -rf "${FIREDOG_HOME}/.ssh" 2>/dev/null  # Rimuovi se esiste come directory
    ln -s "${FIREDOG_SSH_DIR}" "${FIREDOG_HOME}/.ssh"
    echo "  → Symlink creato: ${FIREDOG_HOME}/.ssh → ${FIREDOG_SSH_DIR}"
fi

# Copia chiave SSH pubblica se fornita
if [[ -f "${SSH_KEY_FILE}" ]]; then
    echo "  → Installazione chiave SSH pubblica..."

    # Leggi chiave
    SSH_PUB_KEY=$(cat "${SSH_KEY_FILE}")

    # Aggiungi a authorized_keys se non già presente
    if ! grep -q "${SSH_PUB_KEY}" "${FIREDOG_SSH_DIR}/authorized_keys" 2>/dev/null; then
        echo "${SSH_PUB_KEY}" >> "${FIREDOG_SSH_DIR}/authorized_keys"
        echo -e "${GREEN}[OK]${NC} Chiave SSH installata in ${FIREDOG_SSH_DIR}/authorized_keys"
    else
        echo -e "${YELLOW}[INFO]${NC} Chiave SSH già presente"
    fi
else
    echo -e "${YELLOW}[WARNING]${NC} File chiave SSH (${SSH_KEY_FILE}) non trovato"
    echo "  → La chiave dovrà essere configurata manualmente o via web interface"
    echo "  → Path authorized_keys: ${FIREDOG_SSH_DIR}/authorized_keys"
fi

echo -e "${GREEN}[4/11]${NC} Creazione directory FireDog..."

# Crea directory export per JSON
mkdir -p "${FIREDOG_EXPORT_DIR}"
chown "${FIREDOG_USER}:${FIREDOG_USER}" "${FIREDOG_EXPORT_DIR}"
chmod 755 "${FIREDOG_EXPORT_DIR}"

echo -e "${GREEN}[OK]${NC} Directory ${FIREDOG_EXPORT_DIR} creata"

echo -e "${GREEN}[5/11]${NC} Installazione script firewall..."

# Copia script inizializzazione
install -m 755 firewall-init.sh /usr/local/sbin/firewall-init.sh

# Copia manager Python
install -m 755 firewall-manager.py /usr/local/bin/firewall-manager
chmod +x /usr/local/bin/firewall-manager

# Copia traffic analyzer Python
install -m 755 traffic-analyzer.py /usr/local/bin/traffic-analyzer
chmod +x /usr/local/bin/traffic-analyzer

# Copia SSH gateway (forced commands wrapper)
install -m 755 firedog-ssh-gateway.sh /usr/local/bin/firedog-ssh-gateway.sh
chmod +x /usr/local/bin/firedog-ssh-gateway.sh

echo "  → firewall-manager installato in /usr/local/bin/firewall-manager"
echo "  → traffic-analyzer installato in /usr/local/bin/traffic-analyzer"
echo "  → firedog-ssh-gateway.sh installato in /usr/local/bin/firedog-ssh-gateway.sh"
echo "  → firewall-init.sh installato in /usr/local/sbin/firewall-init.sh"

echo -e "${GREEN}[6/11]${NC} Configurazione sudoers per ${FIREDOG_USER}..."

# Crea file sudoers per microcyber
SUDOERS_FILE="/etc/sudoers.d/${FIREDOG_USER}"
cat > "${SUDOERS_FILE}" << EOF
# FireDog - Permessi per utente ${FIREDOG_USER}
# ATTENZIONE: Limitare solo a comandi specifici, NO wildcards pericolosi

# ========== FIREWALL MANAGEMENT ==========
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/sbin/iptables -L *
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/sbin/iptables -S *
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/sbin/iptables-save
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/sbin/ip6tables -L *
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/sbin/ip6tables -S *

# ========== FIREDOG BINARIES (read-only commands) ==========
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/local/bin/firewall-manager --list
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/local/bin/firewall-manager --stats
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/local/bin/firewall-manager --export-json *
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/local/bin/firewall-manager --threats *
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/local/bin/firewall-manager --analyze *
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/local/bin/traffic-analyzer *

# ========== FIREDOG BINARIES (write commands - require password) ==========
${FIREDOG_USER} ALL=(ALL) /usr/local/bin/firewall-manager --add-input *
${FIREDOG_USER} ALL=(ALL) /usr/local/bin/firewall-manager --add-output *
${FIREDOG_USER} ALL=(ALL) /usr/local/bin/firewall-manager --delete *
${FIREDOG_USER} ALL=(ALL) /usr/sbin/iptables -A *
${FIREDOG_USER} ALL=(ALL) /usr/sbin/iptables -D *
${FIREDOG_USER} ALL=(ALL) /usr/sbin/iptables-restore

# ========== SYSTEMD SERVICE MANAGEMENT ==========
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /bin/systemctl start firedog
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /bin/systemctl stop firedog
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /bin/systemctl restart firedog
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /bin/systemctl status firedog
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /bin/systemctl reload firedog
EOF

# Imposta permessi corretti
chmod 440 "${SUDOERS_FILE}"

# Verifica sintassi sudoers
if visudo -c -f "${SUDOERS_FILE}" &>/dev/null; then
    echo -e "${GREEN}[OK]${NC} Sudoers configurato per ${FIREDOG_USER}"
else
    echo -e "${RED}[ERROR]${NC} Errore nella configurazione sudoers"
    echo "  → Verifica manuale: visudo -c -f ${SUDOERS_FILE}"
    rm -f "${SUDOERS_FILE}"
    exit 1
fi

echo -e "${GREEN}[7/11]${NC} Configurazione ulogd2..."

# Backup configurazione esistente
if [[ -f /etc/ulogd.conf ]]; then
    cp /etc/ulogd.conf /etc/ulogd.conf.backup.$(date +%s)
fi

# Copia nuova configurazione
cp ulogd.conf /etc/ulogd.conf
chmod 644 /etc/ulogd.conf

# Crea directory log
mkdir -p /var/log/ulogd
chown root:adm /var/log/ulogd
chmod 750 /var/log/ulogd

# Riavvia ulogd2
systemctl enable ulogd2
systemctl restart ulogd2

echo -e "${GREEN}[8/11]${NC} Configurazione logrotate..."
cp firewall-pcap-logrotate /etc/logrotate.d/firewall-pcap
chmod 644 /etc/logrotate.d/firewall-pcap

echo -e "${GREEN}[9/11]${NC} Installazione systemd service..."
cp firewall.service /etc/systemd/system/firewall.service
chmod 644 /etc/systemd/system/firewall.service
systemctl daemon-reload

echo -e "${GREEN}[10/11]${NC} Creazione directory configurazione..."
mkdir -p /etc/firewall
mkdir -p /var/lib/firewall
mkdir -p /var/log/firedog
mkdir -p /opt/firedog/data
mkdir -p /opt/firedog/logs
mkdir -p /opt/firedog/rules
chmod 700 /etc/firewall
chmod 700 /var/lib/firewall
chmod 755 /var/log/firedog
chmod 755 /opt/firedog/data
chmod 755 /opt/firedog/logs
chmod 755 /opt/firedog/rules
chown -R ${FIREDOG_USER}:${FIREDOG_USER} /opt/firedog

# Installazione AppArmor (opzionale, solo se disponibile)
if command -v apparmor_parser &>/dev/null; then
    echo "  → Installazione profilo AppArmor..."
    if [[ -f apparmor-firewall-manager ]]; then
        install -m 644 apparmor-firewall-manager /etc/apparmor.d/usr.local.bin.firewall-manager
        apparmor_parser -r /etc/apparmor.d/usr.local.bin.firewall-manager 2>&1 | grep -v "Warning" || true
        echo -e "${GREEN}[OK]${NC} Profilo AppArmor installato per firewall-manager"
    fi
else
    echo -e "${YELLOW}[INFO]${NC} AppArmor non disponibile, skip profilo di sicurezza"
fi

echo -e "${GREEN}[11/11]${NC} Inizializzazione firewall..."
echo ""

# ========== CONTROLLO PRE-MIGRAZIONE ==========
REINSTALL=false
MIGRATION=false

# Controlla se esiste già una installazione firewall-manager
if [[ -f /usr/local/bin/firewall-manager ]] && command -v firewall-manager &>/dev/null; then
    CURRENT_VERSION=$(firewall-manager --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' || echo "unknown")

    # Controlla se ci sono regole iptables attive
    ACTIVE_RULES=$(iptables -S | wc -l)

    echo -e "${YELLOW}[INFO]${NC} FireDog versione $CURRENT_VERSION già installata"

    if [[ $ACTIVE_RULES -gt 10 ]]; then
        echo -e "${YELLOW}[INFO]${NC} Rilevate $ACTIVE_RULES regole iptables attive"
        echo ""
        echo "Questa sembra una MIGRAZIONE da installazione standalone a web-console."
        echo ""
        echo -e "${CYAN}Operazioni di backup:${NC}"
        echo "  1. Backup regole iptables correnti"
        echo "  2. Backup configurazione firewall esistente"
        echo "  3. Salvataggio in /etc/firewall/pre_console_backup_$(date +%Y%m%d_%H%M%S)/"
        echo ""

        MIGRATION=true
        MIGRATION_BACKUP_DIR="/etc/firewall/pre_console_backup_$(date +%Y%m%d_%H%M%S)"

        read -p "Procedere con MIGRAZIONE e backup? (yes/no): " migration_confirm

        if [[ "$migration_confirm" == "yes" ]]; then
            echo ""
            echo -e "${CYAN}[BACKUP]${NC} Creazione backup pre-migrazione..."

            # Crea directory backup
            mkdir -p "$MIGRATION_BACKUP_DIR"

            # Backup regole iptables
            iptables-save > "$MIGRATION_BACKUP_DIR/iptables_pre_console.rules"
            chmod 600 "$MIGRATION_BACKUP_DIR/iptables_pre_console.rules"
            echo "  → Regole iptables salvate in: iptables_pre_console.rules"

            # Backup configurazione custom se esiste
            if [[ -f /etc/firewall/custom_rules.conf ]]; then
                cp /etc/firewall/custom_rules.conf "$MIGRATION_BACKUP_DIR/custom_rules_pre_console.conf"
                echo "  → Configurazione custom salvata in: custom_rules_pre_console.conf"
            fi

            # Salva versione e metadata
            cat > "$MIGRATION_BACKUP_DIR/migration_info.txt" << EOF
Backup creato: $(date)
Versione precedente: $CURRENT_VERSION
Regole attive: $ACTIVE_RULES
Sistema: $(uname -a)
Hostname: $(hostname)

Ripristino backup (se necessario):
  sudo iptables-restore < $MIGRATION_BACKUP_DIR/iptables_pre_console.rules

Note:
  - Questo backup contiene TUTTE le regole iptables al momento della migrazione
  - La nuova installazione partirà con regole base + web console management
  - È possibile importare regole custom manualmente in /etc/firewall/custom_rules.conf
EOF

            echo -e "${GREEN}[OK]${NC} Backup completato in: $MIGRATION_BACKUP_DIR"
            echo ""

            REINSTALL=true
        else
            echo -e "${YELLOW}Migrazione annullata.${NC}"
            exit 0
        fi
    else
        echo ""
        echo "Versione corrente: $CURRENT_VERSION"
        echo ""
        echo -e "${YELLOW}Attenzione:${NC} La reinstallazione rimuoverà TUTTE le regole firewall esistenti."
        echo "Le seguenti operazioni verranno eseguite:"
        echo "  1. Flush completo iptables (tutti i pacchetti, regole, chain)"
        echo "  2. Rimozione installazione precedente"
        echo "  3. Installazione pulita"
        echo ""
        read -p "Procedere con la REINSTALLAZIONE? (yes/no): " reinstall_confirm

        if [[ "$reinstall_confirm" == "yes" ]]; then
            REINSTALL=true
        else
            echo -e "${YELLOW}Reinstallazione annullata.${NC}"
            exit 0
        fi
    fi
fi

# ========== PULIZIA INSTALLAZIONE PRECEDENTE ==========
if [[ "$REINSTALL" == true ]]; then
    echo ""
    echo -e "${YELLOW}[REINSTALL]${NC} Rimozione installazione esistente..."
        
        # Stop servizio firewall
        systemctl stop firewall.service 2>/dev/null || true
        systemctl disable firewall.service 2>/dev/null || true
        
        # Flush completo iptables
        echo "  → Flush iptables..."
        iptables -F
        iptables -X
        iptables -t nat -F
        iptables -t nat -X
        iptables -t mangle -F
        iptables -t mangle -X
        iptables -t raw -F
        iptables -t raw -X
        iptables -Z
        
        # Reset policy a ACCEPT per evitare lockout
        iptables -P INPUT ACCEPT
        iptables -P FORWARD ACCEPT
        iptables -P OUTPUT ACCEPT
        
        # Rimuovi file installazione precedente
        echo "  → Rimozione file precedenti..."
        rm -rf /etc/firewall/* 2>/dev/null || true
        rm -f /var/lib/firewall/* 2>/dev/null || true
        rm -f /usr/local/bin/firewall-manager 2>/dev/null || true
        rm -f /usr/local/sbin/firewall-init.sh 2>/dev/null || true
        rm -f /etc/systemd/system/firewall.service 2>/dev/null || true
        
        echo -e "${GREEN}[OK]${NC} Sistema pulito, pronto per reinstallazione"
        echo ""
    else
        echo -e "${YELLOW}Reinstallazione annullata.${NC}"
        exit 0
    fi
fi

if [[ "$REINSTALL" == true ]]; then
    echo -e "${YELLOW}Conferma finale:${NC} Stai per installare il firewall con policy DROP."
else
    echo -e "${YELLOW}Attenzione:${NC} Stai per attivare il firewall con policy DROP."
fi
echo "Assicurati di avere accesso fisico o console seriale in caso di problemi."
echo ""
read -p "Procedere con l'inizializzazione? (yes/no): " confirm

if [[ "$confirm" == "yes" ]]; then
    # Esegui inizializzazione
    /usr/local/sbin/firewall-init.sh
    
    # Abilita servizio
    systemctl enable firewall.service

    # Configura export automatico stato firewall
    echo ""
    echo -e "${CYAN}[11/11]${NC} Configurazione export automatico..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "$SCRIPT_DIR/setup-export-cron.sh" ]; then
        bash "$SCRIPT_DIR/setup-export-cron.sh"
    else
        echo -e "${YELLOW}⚠ setup-export-cron.sh non trovato, skip configurazione export${NC}"
    fi

if [[ "$REINSTALL" == true ]]; then
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Reinstallazione completata con successo!  ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
else 
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Installazione completata con successo!    ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Comandi disponibili:"
    echo "  firewall-manager --help          # Mostra aiuto completo"
    echo "  firewall-manager --list          # Lista regole"
    echo "  firewall-manager --stats         # Statistiche"
    echo "  firewall-manager --analyze 24    # Analizza traffico 24h"
    echo "  firewall-manager --threats       # Mostra minacce"
    echo "  firewall-manager --export-json   # Export stato in JSON"
    echo ""
    echo "Servizio systemd:"
    echo "  systemctl status firewall        # Stato servizio"
    echo "  systemctl restart firewall       # Riavvia firewall"
    echo ""
    echo "File di configurazione:"
    echo "  /etc/firewall/custom_rules.conf  # Regole personalizzate"
    echo "  /etc/ulogd.conf                  # Configurazione logging"
    echo "  /var/log/ulogd/*.pcap            # File PCAP"
    echo ""
    echo "Export automatico (FireDog):"
    echo "  /opt/firedog/export/status.json  # Stato esportato (ogni 60s)"
    echo "  /var/log/firedog-export.log      # Log export automatico"
    echo ""
else
    echo -e "${YELLOW}Inizializzazione annullata.${NC}"
    echo "Per avviare manualmente: sudo /usr/local/sbin/firewall-init.sh"
fi

echo ""
echo -e "${GREEN}[INFO]${NC} Log installazione: /var/log/firewall-init.log"

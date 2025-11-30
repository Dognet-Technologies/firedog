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
FIREDOG_EXPORT_DIR="/opt/firedog/export"
SSH_KEY_FILE="firedog_ssh_key.pub"

# Crea utente microcyber se non esiste
if ! id -u "${FIREDOG_USER}" &>/dev/null; then
    echo "  → Creazione utente ${FIREDOG_USER}..."
    useradd -m -s /bin/bash "${FIREDOG_USER}"
    echo -e "${GREEN}[OK]${NC} Utente ${FIREDOG_USER} creato"
else
    echo -e "${YELLOW}[INFO]${NC} Utente ${FIREDOG_USER} già esistente"
fi

# Crea directory SSH
mkdir -p "${FIREDOG_HOME}/.ssh"
touch "${FIREDOG_HOME}/.ssh/authorized_keys"
chmod 700 "${FIREDOG_HOME}/.ssh"
chmod 600 "${FIREDOG_HOME}/.ssh/authorized_keys"
chown -R "${FIREDOG_USER}:${FIREDOG_USER}" "${FIREDOG_HOME}/.ssh"

# Copia chiave SSH pubblica se fornita
if [[ -f "${SSH_KEY_FILE}" ]]; then
    echo "  → Installazione chiave SSH pubblica..."

    # Leggi chiave
    SSH_PUB_KEY=$(cat "${SSH_KEY_FILE}")

    # Aggiungi a authorized_keys se non già presente
    if ! grep -q "${SSH_PUB_KEY}" "${FIREDOG_HOME}/.ssh/authorized_keys" 2>/dev/null; then
        echo "${SSH_PUB_KEY}" >> "${FIREDOG_HOME}/.ssh/authorized_keys"
        echo -e "${GREEN}[OK]${NC} Chiave SSH installata"
    else
        echo -e "${YELLOW}[INFO]${NC} Chiave SSH già presente"
    fi
else
    echo -e "${YELLOW}[WARNING]${NC} File chiave SSH (${SSH_KEY_FILE}) non trovato"
    echo "  → La chiave dovrà essere configurata manualmente o via web interface"
fi

echo -e "${GREEN}[4/11]${NC} Configurazione sudoers per ${FIREDOG_USER}..."

# Crea file sudoers per microcyber
SUDOERS_FILE="/etc/sudoers.d/${FIREDOG_USER}"
cat > "${SUDOERS_FILE}" << EOF
# FireDog - Permessi per utente ${FIREDOG_USER}
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/sbin/iptables
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/sbin/ip6tables
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/sbin/iptables-save
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/sbin/iptables-restore
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/local/bin/firewall-manager
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /usr/local/sbin/firewall-init.sh
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /bin/systemctl restart firewall
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /bin/systemctl status firewall
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /bin/systemctl start firewall
${FIREDOG_USER} ALL=(ALL) NOPASSWD: /bin/systemctl stop firewall
EOF

# Imposta permessi corretti
chmod 440 "${SUDOERS_FILE}"

# Verifica sintassi sudoers
if visudo -c -f "${SUDOERS_FILE}" &>/dev/null; then
    echo -e "${GREEN}[OK]${NC} Sudoers configurato per ${FIREDOG_USER}"
else
    echo -e "${RED}[ERROR]${NC} Errore nella configurazione sudoers"
    rm -f "${SUDOERS_FILE}"
    exit 1
fi

echo -e "${GREEN}[5/11]${NC} Creazione directory FireDog..."

# Crea directory export per JSON
mkdir -p "${FIREDOG_EXPORT_DIR}"
chown "${FIREDOG_USER}:${FIREDOG_USER}" "${FIREDOG_EXPORT_DIR}"
chmod 755 "${FIREDOG_EXPORT_DIR}"

echo -e "${GREEN}[OK]${NC} Directory ${FIREDOG_EXPORT_DIR} creata"

echo -e "${GREEN}[6/11]${NC} Installazione script firewall..."

# Copia script inizializzazione
install -m 755 firewall-init.sh /usr/local/sbin/firewall-init.sh

# Copia manager Python
install -m 755 firewall-manager.py /usr/local/bin/firewall-manager
chmod +x /usr/local/bin/firewall-manager

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

<<<<<<< HEAD
echo -e "${GREEN}[5/8]${NC} Configurazione logrotate..."
cp file_config/firewall-pcap-logrotate /etc/logrotate.d/firewall-pcap
=======
echo -e "${GREEN}[8/11]${NC} Configurazione logrotate..."
cp firewall-pcap-logrotate /etc/logrotate.d/firewall-pcap
>>>>>>> 83c67b8c3a62c54b02b2b6d06cf6acafe42ceea2
chmod 644 /etc/logrotate.d/firewall-pcap

echo -e "${GREEN}[9/11]${NC} Installazione systemd service..."
cp firewall.service /etc/systemd/system/firewall.service
chmod 644 /etc/systemd/system/firewall.service
systemctl daemon-reload

<<<<<<< HEAD
echo -e "${GREEN}[7/8]${NC} Creazione directory configurazione..."
=======
echo -e "${GREEN}[10/11]${NC} Creazione directory configurazione..."
mkdir -p /etc/firewall
>>>>>>> 83c67b8c3a62c54b02b2b6d06cf6acafe42ceea2
mkdir -p /var/lib/firewall
chmod 700 /var/lib/firewall

echo -e "${GREEN}[11/11]${NC} Inizializzazione firewall..."
echo ""

REINSTALL=false
if [[ -f /usr/local/bin/firewall-manager ]] && command -v firewall-manager &>/dev/null; then
    echo -e "${YELLOW}[INFO]${NC} FireDog è già installato su questo sistema."
    echo ""
    echo "Versione corrente: $(firewall-manager --version 2>/dev/null || echo 'sconosciuta')"
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

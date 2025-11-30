#!/bin/bash
#
# FireDog Target Deployment and Testing Script
# Test automatico installazione e configurazione su target
#
# Usage:
#   ./test-target-deployment.sh <target-ip> [--with-ssh-key]
#
# Examples:
#   ./test-target-deployment.sh 192.168.1.50                    # Senza chiave SSH
#   ./test-target-deployment.sh 192.168.1.50 --with-ssh-key     # Con chiave SSH
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Check arguments
if [ -z "$1" ]; then
    echo -e "${RED}Errore: IP target non specificato${NC}"
    echo ""
    echo "Usage: $0 <target-ip> [--with-ssh-key]"
    echo ""
    echo "Examples:"
    echo "  $0 192.168.1.50                    # Installazione senza chiave SSH"
    echo "  $0 192.168.1.50 --with-ssh-key     # Installazione con chiave SSH"
    exit 1
fi

TARGET_IP="$1"
WITH_SSH_KEY=false

if [[ "$2" == "--with-ssh-key" ]]; then
    WITH_SSH_KEY=true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="/tmp/firedog-test-$$"
PACKAGE_DIR="$TEST_DIR/firedog-install"
SSH_KEY_PATH="$TEST_DIR/firedog_master"

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

test_step() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

test_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((TESTS_PASSED++))
}

test_failure() {
    echo -e "${RED}✗ $1${NC}"
    ((TESTS_FAILED++))
}

test_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

test_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Cleanup on exit
cleanup() {
    echo ""
    echo -e "${BLUE}Pulizia file temporanei...${NC}"
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

# ========================================
# INIZIO TEST
# ========================================

echo -e "${GREEN}"
cat << "EOF"
╔═══════════════════════════════════════════════╗
║   FireDog Target Deployment Test Suite       ║
║   Automated Installation and Validation       ║
╚═══════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo "Target IP:     $TARGET_IP"
echo "With SSH Key:  $WITH_SSH_KEY"
echo "Test Dir:      $TEST_DIR"
echo ""

# ========================================
# TEST 1: Pre-requisiti
# ========================================

test_step "TEST 1: Verifica pre-requisiti"

# Test connessione SSH come root
if ssh -o ConnectTimeout=5 -o BatchMode=yes root@$TARGET_IP "echo OK" &>/dev/null; then
    test_success "Connessione SSH root disponibile"
else
    test_failure "Impossibile connettersi come root a $TARGET_IP"
    echo ""
    echo "Suggerimento: Verifica che:"
    echo "  1. Il target sia raggiungibile: ping $TARGET_IP"
    echo "  2. SSH sia abilitato sul target"
    echo "  3. Autenticazione root sia permessa (PermitRootLogin yes in sshd_config)"
    echo "  4. Chiave SSH pubblica sia installata: ssh-copy-id root@$TARGET_IP"
    exit 1
fi

# Verifica OS target
OS_INFO=$(ssh root@$TARGET_IP "cat /etc/os-release" 2>/dev/null || echo "unknown")
if echo "$OS_INFO" | grep -Eiq 'debian|ubuntu'; then
    DISTRO=$(echo "$OS_INFO" | grep -E '^PRETTY_NAME=' | cut -d'"' -f2)
    test_success "OS compatibile: $DISTRO"
else
    test_warning "OS non Debian/Ubuntu, installazione potrebbe fallire"
fi

# ========================================
# TEST 2: Preparazione pacchetto
# ========================================

test_step "TEST 2: Preparazione pacchetto installazione"

mkdir -p "$PACKAGE_DIR"
test_info "Directory creata: $PACKAGE_DIR"

# Copia file package
cp -r "$SCRIPT_DIR"/* "$PACKAGE_DIR/"
test_success "File pacchetto copiati"

# Generazione chiave SSH (se richiesto)
if [[ "$WITH_SSH_KEY" == true ]]; then
    test_info "Generazione chiave SSH per test..."
    ssh-keygen -t ed25519 -f "$SSH_KEY_PATH" -N "" -C "firedog-test-$$" &>/dev/null

    if [[ -f "${SSH_KEY_PATH}.pub" ]]; then
        cp "${SSH_KEY_PATH}.pub" "$PACKAGE_DIR/firedog_ssh_key.pub"
        test_success "Chiave SSH generata e copiata nel pacchetto"
        test_info "Chiave privata: $SSH_KEY_PATH"
        test_info "Chiave pubblica: ${SSH_KEY_PATH}.pub"
    else
        test_failure "Errore generazione chiave SSH"
        exit 1
    fi
else
    test_info "Installazione senza chiave SSH (configurazione manuale dopo)"
fi

# Crea archivio
cd "$TEST_DIR"
tar czf firedog-install.tar.gz firedog-install/
test_success "Archivio creato: firedog-install.tar.gz"

# ========================================
# TEST 3: Transfer su target
# ========================================

test_step "TEST 3: Transfer pacchetto su target"

scp -q firedog-install.tar.gz root@$TARGET_IP:/tmp/
test_success "Pacchetto trasferito su target:/tmp/"

# ========================================
# TEST 4: Installazione su target
# ========================================

test_step "TEST 4: Esecuzione installazione su target"

test_info "Questo processo richiederà conferme interattive sul target..."
echo ""

# Estrai e esegui installazione
ssh -t root@$TARGET_IP "cd /tmp && tar xzf firedog-install.tar.gz && cd firedog-install && chmod +x install.sh && ./install.sh"

INSTALL_EXIT_CODE=$?
if [[ $INSTALL_EXIT_CODE -eq 0 ]]; then
    test_success "Installazione completata con successo"
else
    test_failure "Installazione fallita (exit code: $INSTALL_EXIT_CODE)"
    exit 1
fi

# ========================================
# TEST 5: Verifica installazione
# ========================================

test_step "TEST 5: Verifica componenti installati"

# Verifica utente microcyber
if ssh root@$TARGET_IP "id microcyber" &>/dev/null; then
    SHELL=$(ssh root@$TARGET_IP "grep microcyber /etc/passwd | cut -d: -f7")
    if [[ "$SHELL" == "/bin/false" ]]; then
        test_success "Utente microcyber creato con shell /bin/false"
    else
        test_warning "Utente microcyber creato ma shell è: $SHELL (atteso: /bin/false)"
    fi
else
    test_failure "Utente microcyber non trovato"
fi

# Verifica directory SSH
if ssh root@$TARGET_IP "test -d /opt/firedog/.ssh"; then
    test_success "Directory /opt/firedog/.ssh creata"

    if ssh root@$TARGET_IP "test -f /opt/firedog/.ssh/authorized_keys"; then
        test_success "File authorized_keys presente"

        if [[ "$WITH_SSH_KEY" == true ]]; then
            KEY_COUNT=$(ssh root@$TARGET_IP "wc -l < /opt/firedog/.ssh/authorized_keys")
            if [[ $KEY_COUNT -gt 0 ]]; then
                test_success "Chiave SSH installata in authorized_keys"
            else
                test_failure "authorized_keys vuoto (chiave non installata)"
            fi
        fi
    else
        test_failure "File authorized_keys non trovato"
    fi
else
    test_failure "Directory /opt/firedog/.ssh non trovata"
fi

# Verifica sudoers
if ssh root@$TARGET_IP "test -f /etc/sudoers.d/microcyber"; then
    if ssh root@$TARGET_IP "visudo -c -f /etc/sudoers.d/microcyber" &>/dev/null; then
        test_success "Sudoers configurato correttamente"
    else
        test_failure "Sudoers presente ma sintassi invalida"
    fi
else
    test_failure "File /etc/sudoers.d/microcyber non trovato"
fi

# Verifica script installati
SCRIPTS=(
    "/usr/local/bin/firewall-manager"
    "/usr/local/bin/traffic-analyzer"
    "/usr/local/bin/firedog-ssh-gateway.sh"
    "/usr/local/sbin/firewall-init.sh"
)

for script in "${SCRIPTS[@]}"; do
    if ssh root@$TARGET_IP "test -x $script"; then
        test_success "Script installato: $script"
    else
        test_failure "Script mancante o non eseguibile: $script"
    fi
done

# Verifica systemd service
if ssh root@$TARGET_IP "test -f /etc/systemd/system/firewall.service"; then
    test_success "Systemd service installato"

    if ssh root@$TARGET_IP "systemctl is-enabled firedog" &>/dev/null; then
        test_success "Service firedog abilitato"
    else
        test_warning "Service firedog non abilitato"
    fi

    if ssh root@$TARGET_IP "systemctl is-active firedog" &>/dev/null; then
        test_success "Service firedog attivo"
    else
        test_warning "Service firedog non attivo"
    fi
else
    test_failure "Systemd service non trovato"
fi

# Verifica AppArmor (opzionale)
if ssh root@$TARGET_IP "command -v aa-status" &>/dev/null; then
    if ssh root@$TARGET_IP "aa-status | grep -q firewall-manager" &>/dev/null; then
        test_success "Profilo AppArmor installato e attivo"
    else
        test_warning "AppArmor disponibile ma profilo non attivo"
    fi
else
    test_info "AppArmor non disponibile (opzionale)"
fi

# Verifica regole iptables
IPTABLES_RULES=$(ssh root@$TARGET_IP "iptables -S | wc -l")
if [[ $IPTABLES_RULES -gt 10 ]]; then
    test_success "Regole iptables configurate ($IPTABLES_RULES regole)"
else
    test_warning "Poche regole iptables ($IPTABLES_RULES regole)"
fi

# Verifica policy DROP
INPUT_POLICY=$(ssh root@$TARGET_IP "iptables -L INPUT | head -1 | grep -o 'policy [A-Z]*' | cut -d' ' -f2")
if [[ "$INPUT_POLICY" == "DROP" ]]; then
    test_success "Policy INPUT: DROP (sicurezza attiva)"
else
    test_warning "Policy INPUT: $INPUT_POLICY (atteso: DROP)"
fi

# ========================================
# TEST 6: Test connessione SSH con utente microcyber
# ========================================

test_step "TEST 6: Test connessione SSH microcyber"

if [[ "$WITH_SSH_KEY" == true ]]; then
    test_info "Test autenticazione con chiave SSH..."

    # Test comando SSH
    if ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o BatchMode=yes microcyber@$TARGET_IP "echo 'SSH OK'" &>/dev/null; then
        test_success "Autenticazione SSH key funzionante"

        # Test comando sudo (read-only, NOPASSWD)
        if ssh -i "$SSH_KEY_PATH" microcyber@$TARGET_IP "sudo iptables -L -n" &>/dev/null; then
            test_success "Comando sudo NOPASSWD funzionante (iptables -L)"
        else
            test_failure "Comando sudo fallito"
        fi

        # Test export JSON
        if ssh -i "$SSH_KEY_PATH" microcyber@$TARGET_IP "sudo firewall-manager --export-json /opt/firedog/export/test.json" &>/dev/null; then
            test_success "Export JSON funzionante"

            # Verifica file creato
            if ssh -i "$SSH_KEY_PATH" microcyber@$TARGET_IP "test -f /opt/firedog/export/test.json"; then
                test_success "File JSON creato correttamente"

                # Test SCP pull
                if scp -i "$SSH_KEY_PATH" microcyber@$TARGET_IP:/opt/firedog/export/test.json "$TEST_DIR/" &>/dev/null; then
                    test_success "SCP pull JSON funzionante"

                    # Valida JSON
                    if python3 -m json.tool "$TEST_DIR/test.json" &>/dev/null; then
                        test_success "JSON valido"
                    else
                        test_failure "JSON non valido"
                    fi
                else
                    test_failure "SCP pull fallito"
                fi
            else
                test_failure "File JSON non creato"
            fi
        else
            test_failure "Export JSON fallito"
        fi

    else
        test_failure "Autenticazione SSH key fallita"
        echo ""
        echo "Debug: Testa manualmente con:"
        echo "  ssh -i $SSH_KEY_PATH microcyber@$TARGET_IP"
    fi
else
    test_info "Test SSH skippato (chiave non configurata)"
    echo ""
    echo "Per configurare la chiave SSH manualmente:"
    echo "  1. Genera chiave: ssh-keygen -t ed25519 -f ~/.ssh/firedog_key"
    echo "  2. Imposta password temporanea: ssh root@$TARGET_IP \"echo 'microcyber:TempPass123' | chpasswd\""
    echo "  3. Copia chiave: ssh-copy-id -i ~/.ssh/firedog_key.pub microcyber@$TARGET_IP"
    echo "  4. Test: ssh -i ~/.ssh/firedog_key microcyber@$TARGET_IP \"sudo iptables -L\""
fi

# ========================================
# TEST 7: Test shell /bin/false
# ========================================

test_step "TEST 7: Test sicurezza shell /bin/false"

if [[ "$WITH_SSH_KEY" == true ]]; then
    test_info "Verifica che login interattivo sia bloccato..."

    # Questo DEVE fallire (shell /bin/false blocca login interattivo)
    if ssh -i "$SSH_KEY_PATH" -o BatchMode=yes microcyber@$TARGET_IP "exit" &>/dev/null; then
        # Se arriviamo qui, login ha funzionato (non dovrebbe)
        test_warning "Login interattivo permesso (potenziale problema sicurezza)"
    else
        test_success "Login interattivo bloccato correttamente (/bin/false)"
    fi

    # Ma command execution DEVE funzionare
    if ssh -i "$SSH_KEY_PATH" microcyber@$TARGET_IP "whoami" &>/dev/null; then
        test_success "Command execution funzionante (corretto)"
    else
        test_failure "Command execution fallito (problema configurazione)"
    fi
fi

# ========================================
# RIEPILOGO FINALE
# ========================================

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}RIEPILOGO TEST${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

echo -e "Test passati:  ${GREEN}$TESTS_PASSED${NC}"
echo -e "Test falliti:  ${RED}$TESTS_FAILED${NC}"
echo ""

if [[ $TESTS_FAILED -eq 0 ]]; then
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ TUTTI I TEST PASSATI CON SUCCESSO!     ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Il target $TARGET_IP è pronto per essere aggiunto alla web console."
    echo ""

    if [[ "$WITH_SSH_KEY" == true ]]; then
        echo "Informazioni per configurazione web console:"
        echo "  IP Target:        $TARGET_IP"
        echo "  SSH User:         microcyber"
        echo "  SSH Port:         22"
        echo "  SSH Key (privata): $SSH_KEY_PATH"
        echo ""
        echo "Comando per copiare chiave privata nel master:"
        echo "  sudo cp $SSH_KEY_PATH /opt/firedog/ssh/target_${TARGET_IP//./_}"
        echo "  sudo chown www-data:www-data /opt/firedog/ssh/target_${TARGET_IP//./_}"
    fi

    exit 0
else
    echo -e "${YELLOW}╔════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ⚠ ALCUNI TEST SONO FALLITI               ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Controlla i log sopra per dettagli sui test falliti."
    exit 1
fi

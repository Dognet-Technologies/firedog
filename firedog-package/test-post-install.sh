#!/bin/bash
#
# FireDog Post-Installation Test
# Verifica che l'installazione locale sia andata a buon fine
#
# Usage:
#   ./test-post-install.sh <target-ip> <ssh-key-path>
#
# Example:
#   ./test-post-install.sh 192.168.1.50 /opt/firedog/ssh/target_key
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

if [ -z "$1" ] || [ -z "$2" ]; then
    echo -e "${RED}Errore: Parametri mancanti${NC}"
    echo ""
    echo "Usage: $0 <target-ip> <ssh-key-path>"
    echo ""
    echo "Example:"
    echo "  $0 192.168.1.50 /opt/firedog/ssh/target_key"
    exit 1
fi

TARGET_IP="$1"
SSH_KEY="$2"
TESTS_PASSED=0
TESTS_FAILED=0

test_success() {
    echo -e "${GREEN}✓${NC} $1"
    ((TESTS_PASSED++))
}

test_failure() {
    echo -e "${RED}✗${NC} $1"
    ((TESTS_FAILED++))
}

test_info() {
    echo -e "${CYAN}→${NC} $1"
}

echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  FireDog Post-Installation Test           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo "Target: $TARGET_IP"
echo "SSH Key: $SSH_KEY"
echo ""

# Test 1: SSH key authentication
test_info "Test 1: Autenticazione SSH..."
if ssh -i "$SSH_KEY" -o ConnectTimeout=5 -o BatchMode=yes microcyber@$TARGET_IP "echo OK" &>/dev/null; then
    test_success "Autenticazione SSH key funzionante"
else
    test_failure "Autenticazione SSH fallita"
    echo ""
    echo "Suggerimenti:"
    echo "  1. Verifica che la chiave sia corretta"
    echo "  2. Controlla permessi chiave (chmod 600)"
    echo "  3. Verifica utente microcyber esista sul target"
    echo "  4. Test manuale: ssh -i $SSH_KEY microcyber@$TARGET_IP"
    exit 1
fi

# Test 2: Utente microcyber
test_info "Test 2: Verifica utente microcyber..."
SHELL=$(ssh -i "$SSH_KEY" microcyber@$TARGET_IP "getent passwd microcyber | cut -d: -f7")
if [[ "$SHELL" == "/bin/false" ]]; then
    test_success "Shell /bin/false configurata correttamente"
else
    test_failure "Shell errata: $SHELL (atteso: /bin/false)"
fi

# Test 3: Sudoers
test_info "Test 3: Configurazione sudoers..."
if ssh -i "$SSH_KEY" microcyber@$TARGET_IP "sudo -n iptables -L" &>/dev/null; then
    test_success "Sudoers NOPASSWD funzionante"
else
    test_failure "Sudoers non configurato correttamente"
fi

# Test 4: firewall-manager installato
test_info "Test 4: Script firewall-manager..."
if ssh -i "$SSH_KEY" microcyber@$TARGET_IP "test -x /usr/local/bin/firewall-manager"; then
    VERSION=$(ssh -i "$SSH_KEY" microcyber@$TARGET_IP "sudo /usr/local/bin/firewall-manager --version" 2>&1 | grep -oP '\d+\.\d+\.\d+' || echo "unknown")
    test_success "firewall-manager installato (versione: $VERSION)"
else
    test_failure "firewall-manager non trovato"
fi

# Test 5: traffic-analyzer installato
test_info "Test 5: Script traffic-analyzer..."
if ssh -i "$SSH_KEY" microcyber@$TARGET_IP "test -x /usr/local/bin/traffic-analyzer"; then
    test_success "traffic-analyzer installato"
else
    test_failure "traffic-analyzer non trovato"
fi

# Test 6: firedog-ssh-gateway installato
test_info "Test 6: SSH gateway..."
if ssh -i "$SSH_KEY" microcyber@$TARGET_IP "test -x /usr/local/bin/firedog-ssh-gateway.sh"; then
    test_success "firedog-ssh-gateway.sh installato"
else
    test_failure "firedog-ssh-gateway.sh non trovato"
fi

# Test 7: Systemd service
test_info "Test 7: Systemd service..."
if ssh -i "$SSH_KEY" microcyber@$TARGET_IP "sudo systemctl is-enabled firedog" &>/dev/null; then
    test_success "Service firedog abilitato"
else
    test_failure "Service firedog non abilitato"
fi

if ssh -i "$SSH_KEY" microcyber@$TARGET_IP "sudo systemctl is-active firedog" &>/dev/null; then
    test_success "Service firedog attivo"
else
    test_failure "Service firedog non attivo"
fi

# Test 8: Regole iptables
test_info "Test 8: Regole firewall..."
RULES_COUNT=$(ssh -i "$SSH_KEY" microcyber@$TARGET_IP "sudo iptables -S | wc -l")
if [[ $RULES_COUNT -gt 10 ]]; then
    test_success "Regole iptables configurate ($RULES_COUNT regole)"
else
    test_failure "Poche regole iptables ($RULES_COUNT regole)"
fi

# Test 9: Policy DROP
test_info "Test 9: Policy firewall..."
INPUT_POLICY=$(ssh -i "$SSH_KEY" microcyber@$TARGET_IP "sudo iptables -L INPUT | head -1" | grep -oP 'policy \K[A-Z]+')
if [[ "$INPUT_POLICY" == "DROP" ]]; then
    test_success "Policy INPUT: DROP (sicurezza attiva)"
else
    test_failure "Policy INPUT: $INPUT_POLICY (atteso: DROP)"
fi

# Test 10: Export JSON
test_info "Test 10: Export JSON..."
if ssh -i "$SSH_KEY" microcyber@$TARGET_IP "sudo firewall-manager --export-json /opt/firedog/export/post-install-test.json" &>/dev/null; then
    test_success "Export JSON eseguito"

    # Test 11: Verifica file creato
    if ssh -i "$SSH_KEY" microcyber@$TARGET_IP "test -f /opt/firedog/export/post-install-test.json"; then
        test_success "File JSON creato"

        # Test 12: SCP pull
        test_info "Test 11: SCP pull JSON..."
        if scp -i "$SSH_KEY" -q microcyber@$TARGET_IP:/opt/firedog/export/post-install-test.json /tmp/ &>/dev/null; then
            test_success "SCP pull funzionante"

            # Test 13: Validazione JSON
            if python3 -m json.tool /tmp/post-install-test.json &>/dev/null; then
                test_success "JSON valido e ben formato"
                rm -f /tmp/post-install-test.json
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

# Test 13: AppArmor (opzionale)
test_info "Test 12: AppArmor profile..."
if ssh -i "$SSH_KEY" microcyber@$TARGET_IP "command -v aa-status" &>/dev/null; then
    if ssh -i "$SSH_KEY" microcyber@$TARGET_IP "sudo aa-status | grep -q firewall-manager" &>/dev/null; then
        test_success "Profilo AppArmor attivo"
    else
        test_info "AppArmor disponibile ma profilo non attivo (opzionale)"
    fi
else
    test_info "AppArmor non disponibile (opzionale)"
fi

# Test 14: Shell /bin/false - blocco login interattivo
test_info "Test 13: Sicurezza shell /bin/false..."
# Questo DEVE fallire (login interattivo bloccato)
if ssh -i "$SSH_KEY" -o BatchMode=yes microcyber@$TARGET_IP "exit" &>/dev/null; then
    test_failure "Login interattivo permesso (rischio sicurezza)"
else
    test_success "Login interattivo bloccato (/bin/false)"
fi

# Ma command execution DEVE funzionare
if ssh -i "$SSH_KEY" microcyber@$TARGET_IP "whoami" &>/dev/null; then
    test_success "Command execution funzionante"
else
    test_failure "Command execution fallito"
fi

# Riepilogo
echo ""
echo -e "${CYAN}════════════════════════════════════════════${NC}"
echo -e "${CYAN}RIEPILOGO TEST${NC}"
echo -e "${CYAN}════════════════════════════════════════════${NC}"
echo ""
echo -e "Test passati:  ${GREEN}$TESTS_PASSED${NC}"
echo -e "Test falliti:  ${RED}$TESTS_FAILED${NC}"
echo ""

if [[ $TESTS_FAILED -eq 0 ]]; then
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ INSTALLAZIONE VERIFICATA CON SUCCESSO! ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Il target $TARGET_IP è pronto per essere aggiunto alla web console."
    echo ""
    echo "Prossimi passi:"
    echo "  1. Salva chiave SSH sul master:"
    echo "     sudo cp $SSH_KEY /opt/firedog/ssh/target_${TARGET_IP//./_}"
    echo ""
    echo "  2. Aggiungi target in Django admin:"
    echo "     http://localhost:8000/admin/targets/target/add/"
    echo ""
    echo "  3. Configura pull automatico (cron):"
    echo "     */5 * * * * python manage.py pull_targets_status"
    echo ""
    exit 0
else
    echo -e "${YELLOW}╔════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ⚠ ALCUNI TEST SONO FALLITI               ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Controlla i test falliti sopra e correggi i problemi."
    echo ""
    echo "Debug utili:"
    echo "  ssh -i $SSH_KEY microcyber@$TARGET_IP"
    echo "  ssh -i $SSH_KEY microcyber@$TARGET_IP \"sudo systemctl status firedog\""
    echo "  ssh -i $SSH_KEY microcyber@$TARGET_IP \"sudo journalctl -u firedog -n 50\""
    exit 1
fi

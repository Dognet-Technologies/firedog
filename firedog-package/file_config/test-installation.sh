#!/bin/bash
#
# Test Script - Verifica installazione firewall
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Firewall System - Test Suite         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

PASSED=0
FAILED=0

test_command() {
    local desc="$1"
    local cmd="$2"
    
    echo -n "Testing: $desc ... "
    
    if eval "$cmd" &>/dev/null; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((FAILED++))
        return 1
    fi
}

test_file() {
    local desc="$1"
    local file="$2"
    
    echo -n "Testing: $desc ... "
    
    if [[ -f "$file" ]]; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((FAILED++))
        return 1
    fi
}

test_executable() {
    local desc="$1"
    local file="$2"
    
    echo -n "Testing: $desc ... "
    
    if [[ -x "$file" ]]; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((FAILED++))
        return 1
    fi
}

test_service() {
    local desc="$1"
    local service="$2"
    
    echo -n "Testing: $desc ... "
    
    if systemctl is-active --quiet "$service"; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((FAILED++))
        return 1
    fi
}

echo -e "${YELLOW}[1] Verifica Dipendenze${NC}"
test_command "iptables installed" "which iptables"
test_command "iptables-save installed" "which iptables-save"
test_command "iptables-restore installed" "which iptables-restore"
test_command "ulogd2 installed" "which ulogd2"
test_command "python3 installed" "which python3"
test_command "tcpdump installed" "which tcpdump"

echo ""
echo -e "${YELLOW}[2] Verifica File Script${NC}"
test_executable "firewall-init.sh" "/usr/local/sbin/firewall-init.sh"
test_executable "firewall-manager" "/usr/local/bin/firewall-manager"
test_executable "traffic-analyzer" "/usr/local/bin/traffic-analyzer"

echo ""
echo -e "${YELLOW}[3] Verifica File Configurazione${NC}"
test_file "ulogd.conf" "/etc/ulogd.conf"
test_file "logrotate config" "/etc/logrotate.d/firewall-pcap"
test_file "systemd service" "/etc/systemd/system/firewall.service"

echo ""
echo -e "${YELLOW}[4] Verifica Directory${NC}"
test_command "Directory /etc/firewall" "test -d /etc/firewall"
test_command "Directory /var/log/ulogd" "test -d /var/log/ulogd"
test_command "Directory /var/lib/firewall" "test -d /var/lib/firewall"

echo ""
echo -e "${YELLOW}[5] Verifica Servizi${NC}"
test_service "ulogd2 service" "ulogd2"

echo ""
echo -e "${YELLOW}[6] Verifica Moduli Kernel${NC}"
test_command "Module nfnetlink_log" "lsmod | grep -q nfnetlink_log"
test_command "Module xt_NFLOG" "lsmod | grep -q xt_NFLOG"

echo ""
echo -e "${YELLOW}[7] Verifica Policy iptables${NC}"
if [[ $EUID -eq 0 ]]; then
    test_command "INPUT policy DROP" "iptables -L INPUT -n | grep -q 'policy DROP'"
    test_command "OUTPUT policy DROP" "iptables -L OUTPUT -n | grep -q 'policy DROP'"
    test_command "Chain LOG_INPUT_DROP exists" "iptables -L LOG_INPUT_DROP -n"
    test_command "Chain LOG_OUTPUT_DROP exists" "iptables -L LOG_OUTPUT_DROP -n"
else
    echo -e "${YELLOW}⚠ Skip (richiede root)${NC}"
fi

echo ""
echo -e "${YELLOW}[8] Verifica Permessi File${NC}"
if [[ $EUID -eq 0 ]]; then
    test_command "/etc/firewall permissions 700" "[[ \$(stat -c '%a' /etc/firewall) == '700' ]]"
    if [[ -f /etc/firewall/iptables.rules ]]; then
        test_command "iptables.rules permissions 600" "[[ \$(stat -c '%a' /etc/firewall/iptables.rules) == '600' ]]"
    else
        echo "Testing: iptables.rules permissions 600 ... ${YELLOW}⚠ SKIP (file non esiste)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Skip (richiede root)${NC}"
fi

echo ""
echo "═════════════════════════════════════════"
echo -e "Test Results: ${GREEN}${PASSED} passed${NC}, ${RED}${FAILED} failed${NC}"
echo "═════════════════════════════════════════"

if [[ $FAILED -eq 0 ]]; then
    echo ""
    echo -e "${GREEN}✓ Tutti i test sono passati!${NC}"
    echo ""
    echo "Prossimi passi:"
    echo "  1. Verifica regole: firewall-manager --list"
    echo "  2. Controlla stats: firewall-manager --stats"
    echo "  3. Analizza traffico: sudo firewall-manager --analyze"
    echo ""
    exit 0
else
    echo ""
    echo -e "${RED}✗ Alcuni test sono falliti${NC}"
    echo "Controlla i log per dettagli:"
    echo "  sudo journalctl -u firewall -n 50"
    echo "  sudo journalctl -u ulogd2 -n 50"
    echo ""
    exit 1
fi

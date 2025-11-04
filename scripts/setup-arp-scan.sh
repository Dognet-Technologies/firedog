#!/bin/bash
# setup-arp-scan.sh
#
# Script per installare e configurare arp-scan sul server FireDog
# Permette l'esecuzione senza password per l'utente che esegue il backend

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "[INFO] $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root (use sudo)"
   exit 1
fi

echo ""
echo "============================================"
echo "    FireDog ARP-Scan Setup"
echo "============================================"
echo ""

# ==================== STEP 1: Install arp-scan ====================

log_info "Installing arp-scan..."

if command -v arp-scan &>/dev/null; then
    log_success "arp-scan already installed"
    arp-scan --version
else
    if [[ -f /etc/debian_version ]]; then
        # Debian/Ubuntu
        apt-get update
        apt-get install -y arp-scan
    elif [[ -f /etc/redhat-release ]]; then
        # RedHat/CentOS/Rocky
        yum install -y arp-scan || dnf install -y arp-scan
    else
        log_error "Unsupported distribution"
        exit 1
    fi
    
    log_success "arp-scan installed"
fi

# ==================== STEP 2: Configure sudoers ====================

log_info "Configuring sudoers for arp-scan..."

# Determine which user runs the backend
BACKEND_USER="${1:-www-data}"

log_info "Configuring sudoers for user: $BACKEND_USER"

# Create sudoers file for arp-scan
SUDOERS_FILE="/etc/sudoers.d/firedog-arp-scan"

cat > "$SUDOERS_FILE" << EOF
# FireDog - Permessi per arp-scan
# Creato automaticamente da setup-arp-scan.sh
# OWASP compliant - permessi minimi necessari

# User che esegue il backend Django/Celery
$BACKEND_USER ALL=(ALL) NOPASSWD: /usr/bin/arp-scan
$BACKEND_USER ALL=(ALL) NOPASSWD: /usr/sbin/arp-scan

# Permessi per comandi correlati alla rete (necessari per discovery)
$BACKEND_USER ALL=(ALL) NOPASSWD: /usr/sbin/ip route
$BACKEND_USER ALL=(ALL) NOPASSWD: /usr/bin/ip route
$BACKEND_USER ALL=(ALL) NOPASSWD: /usr/bin/host

# NOTA: Nessun permesso per comandi shell generici
# per prevenire privilege escalation
EOF

# Set correct permissions (440)
chmod 440 "$SUDOERS_FILE"

# Validate sudoers file
if visudo -c -f "$SUDOERS_FILE" >/dev/null 2>&1; then
    log_success "Sudoers file created and validated: $SUDOERS_FILE"
else
    log_error "Sudoers file validation failed"
    rm -f "$SUDOERS_FILE"
    exit 1
fi

# ==================== STEP 3: Test arp-scan ====================

log_info "Testing arp-scan as user $BACKEND_USER..."

# Test se l'utente esiste
if id "$BACKEND_USER" &>/dev/null; then
    # Test comando base
    if sudo -u "$BACKEND_USER" sudo arp-scan --help >/dev/null 2>&1; then
        log_success "arp-scan test successful"
    else
        log_warning "arp-scan test failed (may work in backend context)"
    fi
else
    log_warning "User $BACKEND_USER does not exist yet (will be created during backend setup)"
fi

# ==================== STEP 4: Update arp-scan vendor database ====================

log_info "Updating ARP vendor database..."

if [[ -f /usr/share/arp-scan/ieee-oui.txt ]]; then
    # Download latest IEEE OUI database
    if wget -q -O /tmp/ieee-oui.txt "http://standards-oui.ieee.org/oui/oui.txt" 2>/dev/null; then
        # Convert to arp-scan format
        awk -F'\t' '/base 16/ {print $1 "\t" $3}' /tmp/ieee-oui.txt > /usr/share/arp-scan/ieee-oui.txt
        rm /tmp/ieee-oui.txt
        log_success "Vendor database updated"
    else
        log_warning "Could not download vendor database (network issue?)"
    fi
else
    log_warning "Vendor database not found at expected location"
fi

# ==================== STEP 5: Create test script ====================

log_info "Creating test script..."

TEST_SCRIPT="/usr/local/bin/test-firedog-arp-scan"

cat > "$TEST_SCRIPT" << 'EOF'
#!/bin/bash
# Test script per verificare arp-scan funzionante

echo "Testing arp-scan discovery..."
echo ""

# Get local networks
echo "Local networks:"
ip route | grep -v default | grep -E '^[0-9]+\.' | awk '{print $1}'
echo ""

# Test arp-scan on first network
NETWORK=$(ip route | grep -v default | grep -E '^[0-9]+\.' | head -1 | awk '{print $1}')

if [[ -n "$NETWORK" ]]; then
    echo "Scanning network: $NETWORK"
    echo ""
    
    sudo arp-scan --interface=auto --numeric "$NETWORK" 2>&1 | head -20
    
    echo ""
    echo "Test completed"
else
    echo "No local network found"
    exit 1
fi
EOF

chmod +x "$TEST_SCRIPT"

log_success "Test script created: $TEST_SCRIPT"

# ==================== Summary ====================

echo ""
echo "============================================"
echo "    Setup Completed Successfully"
echo "============================================"
echo ""
echo "✓ arp-scan installed"
echo "✓ sudoers configured for user: $BACKEND_USER"
echo "✓ Test script created: $TEST_SCRIPT"
echo ""
echo "To test manually, run:"
echo "  sudo -u $BACKEND_USER $TEST_SCRIPT"
echo ""
echo "Or as root:"
echo "  $TEST_SCRIPT"
echo ""

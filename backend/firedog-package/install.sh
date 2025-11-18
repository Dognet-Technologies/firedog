#!/bin/bash
#
# FireDog Installation Script
# Installs firewall monitoring and management tools on target system
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_PORT=22
USERNAME="microcyber"
SSH_KEY="/opt/firedog/ssh/id_ed25519"
SSH_PUB_KEY="/opt/firedog/ssh/id_ed25519.pub"
LOG_FILE="/var/log/firewall-init.log"
RULES_DIR="/opt/firedog/firedog-package"
CUSTOM_RULES="${RULES_DIR}/custom_rules.conf"

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


# Logging functions
log_start() {
    echo -e "${BLUE}[STARTING....]${NC} $1"
}

log_info() {
    echo -e "${GREEN}[INFO] ✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN] ✗${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR] ✗${NC} $1"
}

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        log_error "Cannot detect OS"
        exit 1
    fi

    log_info "Detected OS: $OS $VER"
}

# Install dependencies
install_dependencies() {
    log_start "[1/14] Installing dependencies..."

    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        apt-get update -qq
        apt-get install -y -qq \
        iptables \
        python3 \
        iptables-persistent \
        python3-pip \
        tcpdump \
        net-tools \
        iproute2 \
        logrotate \
        git

        # Verifica moduli kernel
        local modules=("nfnetlink_log" "xt_NFLOG" "xt_recent" "xt_conntrack" "xt_limit")
        for mod in "${modules[@]}"; do
            if ! lsmod | grep -q "^$mod"; then
                modprobe "$mod" 2>/dev/null || warning "Impossibile caricare modulo: $mod"
            fi
        done
    success "Dipendenze verificate"
    
    else
        log_warn "Unsupported OS, attempting generic installation..."
    fi

    log_info "Dependencies installed successfully"
}

# Install firedog binaries
install_binaries() {
    log_start "[2/14] Installing FireDog binaries..."

    # Copy scripts to /usr/local/bin
    install -m 755 $RULES_DIR/bin/firewall-manager /usr/local/bin/firewall-manager
    install -m 755 $RULES_DIR/bin/traffic-analyzer /usr/local/bin/traffic-analyzer
    install -m 755 $RULES_DIR/bin/firewall-init.sh /usr/local/bin/firewall-init.sh

    log_info "Binaries installed successfully"
}

# Create firedog directories
create_directories() {
    log_start "[3/14] Creating FireDog directories..."

    mkdir -p /opt/firedog/{logs,data,pcap,rules,ssh}
    mkdir -p /var/log/firedog

    # Set permissions
    chmod 755 /opt/firedog
    chmod 755 /var/log/firedog

    log_info "Directories created successfully"
}

# Install systemd service
install_service() {

    if [ -d /etc/systemd/system ]; then

        log_start "[4/14] Configurazione ulogd2..."

        # Backup configurazione esistente
        if [[ -f /etc/ulogd.conf ]]; then
            sudo cp /etc/ulogd.conf /etc/ulogd.conf.backup.$(date +%s)
        fi

        # Copia nuova configurazione
        sudo cp $RULES_DIR/file_config/ulogd.conf /etc/ulogd.conf
        sudo chmod 644 /etc/ulogd.conf

        # Crea directory log
        sudo mkdir -p /var/log/ulogd
        sudo chown microcyber:adm /var/log/ulogd
        sudo chmod 750 /var/log/ulogd


        log_start "[5/14] Configurazione logrotate..."
        sudo cp $RULES_DIR/file_config/firewall-pcap-logrotate /etc/logrotate.d/firewall-pcap
        sudo chmod 644 /etc/logrotate.d/firewall-pcap

        log_start "[6/14] Installazione systemd service..."
        sudo cp $RULES_DIR/config/firedog-ta.service /etc/systemd/system/firedog-ta.service
        sudo cp $RULES_DIR/config/firedog-fm.service /etc/systemd/system/firedog-fm.service

        sudo chmod 644 /etc/systemd/system/firewall-ta.service
        sudo chmod 644 /etc/systemd/system/firewall-fm.service

        log_start "[7/14] Creazione directory configurazione..."
        sudo mkdir -p /var/lib/firewall
        sudo chmod 700 /var/lib/firewall

        log_start "[8/14] Inizializzazione firewall..."
        echo ""
        sudo systemctl daemon-reload
        # Riavvia ulogd2
        sudo systemctl enable ulogd2
        sudo systemctl restart ulogd2
        # Abilita firedog
        sudo systemctl enable firedog-ta.service
        sudo systemctl enable firedog-fm.service
        log_info "Systemd service installed and enabled"
    else
        log_warn "Systemd not found, skipping service installation"
    fi
}

# Configure firewall
configure_firewall() {
    log_start "[9/14] configuring base firewall rules..."

    # Backup existing rules
    if command -v iptables-save &> /dev/null; then
        sudo iptables-save > /opt/firedog/rules/iptables.backup.$(date +%Y%m%d_%H%M%S)
    fi

    # Create basic allowed rules (SSH, established connections)
    sudo cat > /opt/firedog/rules/base-rules.conf << 'EOF'
# FireDog Base Rules
# Allow loopback
-A INPUT -i lo -j ACCEPT
# Allow established connections
-A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
# Allow SSH (port 22)
-A INPUT -p tcp --dport 22 -j ACCEPT
# Allow ICMP ping
-A INPUT -p icmp --icmp-type echo-request -j ACCEPT
EOF

    log_info "Firewall configuration prepared"
}

# Controllo chiavi SSH
check_ssh_key() {
        log_start "[10/14] Creating ssh key pair..."

    if [ ! -f "$SSH_KEY" ] || [ ! -f "$SSH_PUB_KEY" ]; then
        log_warn "Error: SSH keys not found"
        echo "Generating:: "
        sudo -u microcyber ssh-keygen -t ed25519 -f $SSH_KEY -N 

    fi
    return 0
}

# Create initial config
create_config() {
    log_start "[11/14] Creating initial configuration..."

    sudo cat > /opt/firedog/firedog.conf << EOF
# FireDog Configuration
FIREDOG_VERSION=1.0.0
INSTALL_DATE=$(date +%Y-%m-%d)
LOG_DIR=/var/log/firedog
DATA_DIR=/opt/firedog/data
PCAP_DIR=/opt/firedog/pcap
RULES_DIR=/opt/firedog/rules
MAX_LOG_SIZE=100M
MAX_PCAP_SIZE=500M
ANALYSIS_INTERVAL=300
EOF

    log_info "Configuration created successfully"
}

# Operation: Configure sudoers
op_sudoers() {
    log_start "[12/14] Creating sudoers configuration..."

    echo -e "${BLUE}[SUDOERS]${NC} Configuring sudoers for NOPASSWD..."
    # Install sudoers file
    "sudo cp $RULES_DIR/file_config/udoers-microcyber /etc/sudoers.d/$USERNAME" || {
        log_warn "Failed to install sudoers file"
        return 1
    }

    sudo chmod 440 /etc/sudoers.d/$USERNAME || {
        log_warn "Failed to set sudoers permissions"
        return 1
    }

    # Test sudo without password
    if sudo -n whoami > /dev/null 2>&1; then
        log_info "Sudoers configured successfully"
    else
        log_warn "Sudoers configuration failed"
        return 1
    fi
}

# Operation: Harden SSH
op_ssh_harden() {
    log_start "[13/14] Creating SSH configuration..."

    echo -e "${BLUE}[SSH-HARDEN]${NC} Applying hardened SSH configuration..."

    echo -e "${YELLOW}WARNING: This will disable password authentication!${NC}"
    echo -e "${YELLOW}Ensure SSH key authentication is working first!${NC}"
    read -p "Continue? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_warn "Aborted"
        return 1
    fi

    # Backup current sshd_config
     sudo cp /etc/ssh/sshd_config "/etc/ssh/sshd_config.backup.\$(date +%Y%m%d_%H%M%S)"
    # Copy hardened config
        "sudo cp $RULES_DIR/file_config/sshd_config.hardened  /etc/ssh/sshd_config" || {
        log_warn "Failed to copy sshd_config"
        return 1
    }

    # Test config
    "sudo sshd -t -f /tmp/sshd_config.hardened" || {
        log_warn "sshd_config validation failed"
        return 1
    }

    # Apply config
     sudo systemctl restart sshd ||  {
        log_warn "sshd_service failed to start"
        return 1
    }
    # Wait a bit for SSH to restart
    sleep 2

}

# Operation: Install cron jobs
op_cron() {
    log_start "[14/14] Installing cron jobs..."

    # Install cron file
    "sudo cp $RULES_DIR/firedog-cron /etc/cron.d/firedog" || {
        log_warn "Failed to copy firedog-cron"
        return 1
    }
    "sudo chmod 644 /etc/cron.d/firedog" || {
        log_warn "Failed to set permissions"
        return 1
    }

    log_info "Cron jobs installed"
}

# Operation: Check configuration
op_check() {
    log_start "LAST CONTROLL"
    echo -e "${BLUE}[CHECK]${NC} Verifying local configuration..."
    echo ""

    local all_ok=true

    # Check sudoers
    echo -n "Sudoers NOPASSWD: "
    test "sudo -n whoami" > /dev/null 2>&1; then
        log_info "OK"
    else
        log_warn "FAILED"
        all_ok=false
    fi

    # Check if user exists
    echo -n "User '$USERNAME' exists: "
    if "id $USERNAME" > /dev/null 2>&1; then
        log_info "OK"
    else
        log_warn "FAILED"
        all_ok=false
    fi

    # Check SSH hardening
    echo -n "SSH Password Auth: "
    local pass_auth=$("sudo grep '^PasswordAuthentication' /etc/ssh/sshd_config" || echo "")
    if echo "$pass_auth" | grep -q "no"; then
        log_info "Disabled"
    else
        echo -e "${YELLOW}⚠ Enabled${NC}"
    fi

    # Check sudoers file
    echo -n "Sudoers file: "
    if "sudo test -f /etc/sudoers.d/$USERNAME" > /dev/null 2>&1; then
        log_info "Exists"
    else
        log_warn "Not found"
        all_ok=false
    fi

    echo ""
    if "$all_ok"; then
        log_info "$HOSTNAME is ready for FireDog installation"
        return 0
    else
        log_warn "$HOSTNAME needs additional configuration"
        return 1
    fi
}

# Main installation function
main() {
    log_info "========================================"
    log_info "FireDog Installation Script"
    log_info "========================================"
    echo ""

    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        log_error "Please run as root or with sudo"
        exit 1
    fi

    # Get current directory (where script is located)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$SCRIPT_DIR"

    # Run installation steps
    detect_os
    install_dependencies
    create_directories
    install_binaries
    configure_firewall
    create_config
    install_service
    op_sudoers
    op_ssh_harden
    op_cron
    op_check

    echo ""
    log_info "========================================"
    log_info "Installation completed successfully!"
    log_info "========================================"
    log_info "FireDog binaries:"
    log_info "  - /usr/local/bin/firewall-manager"
    log_info "  - /usr/local/bin/traffic-analyzer"
    log_info ""
    log_info "Configuration:"
    log_info "  - /opt/firedog/firedog.conf"
    log_info ""
    log_info "To start FireDog service:"
    log_info "  sudo systemctl start firedog-init.sh"
    echo ""
}

# Run main function
main "$@"

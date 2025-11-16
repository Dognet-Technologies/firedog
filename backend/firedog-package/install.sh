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
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
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
    log_info "Installing dependencies..."

    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        apt-get update -qq
        apt-get install -y -qq iptables python3 python3-pip tcpdump net-tools iproute2 > /dev/null 2>&1
    elif [[ "$OS" == "centos" ]] || [[ "$OS" == "rhel" ]] || [[ "$OS" == "rocky" ]]; then
        yum install -y -q iptables python3 python3-pip tcpdump net-tools iproute > /dev/null 2>&1
    else
        log_warn "Unsupported OS, attempting generic installation..."
    fi

    log_info "Dependencies installed successfully"
}

# Install firedog binaries
install_binaries() {
    log_info "Installing FireDog binaries..."

    # Copy scripts to /usr/local/bin
    install -m 755 bin/firewall-manager /usr/local/bin/firewall-manager
    install -m 755 bin/traffic-analyzer /usr/local/bin/traffic-analyzer

    log_info "Binaries installed successfully"
}

# Create firedog directories
create_directories() {
    log_info "Creating FireDog directories..."

    mkdir -p /opt/firedog/{logs,data,pcap,rules}
    mkdir -p /var/log/firedog

    # Set permissions
    chmod 755 /opt/firedog
    chmod 755 /var/log/firedog

    log_info "Directories created successfully"
}

# Install systemd service
install_service() {
    log_info "Installing systemd service..."

    if [ -d /etc/systemd/system ]; then
        cp config/firedog.service /etc/systemd/system/firedog.service
        systemctl daemon-reload
        systemctl enable firedog.service
        log_info "Systemd service installed and enabled"
    else
        log_warn "Systemd not found, skipping service installation"
    fi
}

# Configure firewall
configure_firewall() {
    log_info "Configuring base firewall rules..."

    # Backup existing rules
    if command -v iptables-save &> /dev/null; then
        iptables-save > /opt/firedog/rules/iptables.backup.$(date +%Y%m%d_%H%M%S)
    fi

    # Create basic allowed rules (SSH, established connections)
    cat > /opt/firedog/rules/base-rules.conf << 'EOF'
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

# Create initial config
create_config() {
    log_info "Creating initial configuration..."

    cat > /opt/firedog/firedog.conf << EOF
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
    log_info "  sudo systemctl start firedog"
    echo ""
}

# Run main function
main "$@"

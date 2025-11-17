#!/bin/bash
#
# FireDog Target Preconfiguration Script
# Prepares a target for FireDog installation
#
# Usage: ./preconfigure-target.sh <target-ip> <operation>
#
# Operations:
#   all         - Run all configuration steps (ssh-key, sudoers, ssh-harden)
#   ssh-key     - Copy SSH key to target
#   sudoers     - Configure sudoers for NOPASSWD
#   ssh-harden  - Apply hardened SSH configuration
#   cron        - Install cron jobs
#   check       - Verify target configuration
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_PORT=${3:-22}
USERNAME=${4:-microcyber}
SSH_KEY="/opt/firedog/ssh/id_ed25519"
SSH_PUB_KEY="/opt/firedog/ssh/id_ed25519.pub"

# Check arguments
if [ -z "$1" ] || [ -z "$2" ]; then
    echo -e "${RED}Error: Missing arguments${NC}"
    echo ""
    echo "Usage: $0 <target-ip> <operation> [ssh-port] [username]"
    echo ""
    echo "Operations:"
    echo "  all         - Run all configuration steps"
    echo "  ssh-key     - Copy SSH key to target"
    echo "  sudoers     - Configure sudoers for NOPASSWD"
    echo "  ssh-harden  - Apply hardened SSH configuration"
    echo "  cron        - Install cron jobs"
    echo "  check       - Verify target configuration"
    echo ""
    echo "Examples:"
    echo "  $0 192.168.1.100 all"
    echo "  $0 192.168.1.100 ssh-key 22 microcyber"
    echo "  $0 192.168.1.100 check"
    exit 1
fi

TARGET_IP="$1"
OPERATION="$2"

# Functions
ssh_exec() {
    ssh -i "$SSH_KEY" -p "$SSH_PORT" -o StrictHostKeyChecking=no "$USERNAME@$TARGET_IP" "$@"
}

ssh_exec_sudo() {
    ssh_exec "sudo bash -c '$@'"
}

check_ssh_key() {
    if [ ! -f "$SSH_KEY" ] || [ ! -f "$SSH_PUB_KEY" ]; then
        echo -e "${RED}Error: SSH keys not found${NC}"
        echo "Generate with: sudo -u microcyber ssh-keygen -t ed25519 -f $SSH_KEY -N \"\""
        return 1
    fi
    return 0
}

# Operation: Copy SSH Key
op_ssh_key() {
    echo -e "${BLUE}[SSH-KEY]${NC} Copying SSH public key to target..."

    if ! check_ssh_key; then
        return 1
    fi

    # Use password authentication for initial connection
    ssh-copy-id -i "$SSH_PUB_KEY" -p "$SSH_PORT" "$USERNAME@$TARGET_IP" || {
        echo -e "${RED}Failed to copy SSH key${NC}"
        return 1
    }

    # Test key authentication
    if ssh_exec "echo 'Key auth OK'" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ SSH key configured successfully${NC}"
    else
        echo -e "${RED}✗ SSH key authentication failed${NC}"
        return 1
    fi
}

# Operation: Configure sudoers
op_sudoers() {
    echo -e "${BLUE}[SUDOERS]${NC} Configuring sudoers for NOPASSWD..."

    # Copy sudoers file
    scp -i "$SSH_KEY" -P "$SSH_PORT" "$SCRIPT_DIR/sudoers-microcyber" \
        "$USERNAME@$TARGET_IP:/tmp/sudoers-microcyber" || {
        echo -e "${RED}Failed to copy sudoers file${NC}"
        return 1
    }

    # Install sudoers file
    ssh_exec_sudo "mv /tmp/sudoers-microcyber /etc/sudoers.d/$USERNAME" || {
        echo -e "${RED}Failed to install sudoers file${NC}"
        return 1
    }

    ssh_exec_sudo "chmod 440 /etc/sudoers.d/$USERNAME" || {
        echo -e "${RED}Failed to set sudoers permissions${NC}"
        return 1
    }

    # Test sudo without password
    if ssh_exec "sudo -n whoami" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Sudoers configured successfully${NC}"
    else
        echo -e "${RED}✗ Sudoers configuration failed${NC}"
        return 1
    fi
}

# Operation: Harden SSH
op_ssh_harden() {
    echo -e "${BLUE}[SSH-HARDEN]${NC} Applying hardened SSH configuration..."

    echo -e "${YELLOW}WARNING: This will disable password authentication!${NC}"
    echo -e "${YELLOW}Ensure SSH key authentication is working first!${NC}"
    read -p "Continue? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        echo "Aborted"
        return 1
    fi

    # Backup current sshd_config
    ssh_exec_sudo "cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup.\$(date +%Y%m%d_%H%M%S)"

    # Copy hardened config
    scp -i "$SSH_KEY" -P "$SSH_PORT" "$SCRIPT_DIR/sshd_config.hardened" \
        "$USERNAME@$TARGET_IP:/tmp/sshd_config.hardened" || {
        echo -e "${RED}Failed to copy sshd_config${NC}"
        return 1
    }

    # Test config
    ssh_exec_sudo "sshd -t -f /tmp/sshd_config.hardened" || {
        echo -e "${RED}sshd_config validation failed${NC}"
        return 1
    }

    # Apply config
    ssh_exec_sudo "mv /tmp/sshd_config.hardened /etc/ssh/sshd_config"
    ssh_exec_sudo "systemctl restart sshd || service ssh restart"

    # Wait a bit for SSH to restart
    sleep 2

    # Test connection
    if ssh_exec "echo 'SSH restart OK'" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ SSH hardened successfully${NC}"
    else
        echo -e "${RED}✗ SSH hardening failed - connection lost${NC}"
        echo -e "${YELLOW}You may need to restore backup manually on the target${NC}"
        return 1
    fi
}

# Operation: Install cron jobs
op_cron() {
    echo -e "${BLUE}[CRON]${NC} Installing cron jobs..."

    # Copy cron file
    scp -i "$SSH_KEY" -P "$SSH_PORT" "$SCRIPT_DIR/firedog-cron" \
        "$USERNAME@$TARGET_IP:/tmp/firedog-cron" || {
        echo -e "${RED}Failed to copy cron file${NC}"
        return 1
    }

    # Install cron file
    ssh_exec_sudo "mv /tmp/firedog-cron /etc/cron.d/firedog"
    ssh_exec_sudo "chmod 644 /etc/cron.d/firedog"

    echo -e "${GREEN}✓ Cron jobs installed${NC}"
}

# Operation: Check configuration
op_check() {
    echo -e "${BLUE}[CHECK]${NC} Verifying target configuration..."
    echo ""

    local all_ok=true

    # Check SSH key auth
    echo -n "SSH Key Authentication: "
    if ssh_exec "echo 'OK'" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
    else
        echo -e "${RED}✗ FAILED${NC}"
        all_ok=false
    fi

    # Check sudoers
    echo -n "Sudoers NOPASSWD: "
    if ssh_exec "sudo -n whoami" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
    else
        echo -e "${RED}✗ FAILED${NC}"
        all_ok=false
    fi

    # Check if user exists
    echo -n "User '$USERNAME' exists: "
    if ssh_exec "id $USERNAME" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
    else
        echo -e "${RED}✗ FAILED${NC}"
        all_ok=false
    fi

    # Check SSH hardening
    echo -n "SSH Password Auth: "
    local pass_auth=$(ssh_exec "sudo grep '^PasswordAuthentication' /etc/ssh/sshd_config" || echo "")
    if echo "$pass_auth" | grep -q "no"; then
        echo -e "${GREEN}✓ Disabled${NC}"
    else
        echo -e "${YELLOW}⚠ Enabled${NC}"
    fi

    # Check sudoers file
    echo -n "Sudoers file: "
    if ssh_exec "sudo test -f /etc/sudoers.d/$USERNAME" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Exists${NC}"
    else
        echo -e "${RED}✗ Not found${NC}"
        all_ok=false
    fi

    echo ""
    if $all_ok; then
        echo -e "${GREEN}Target is ready for FireDog installation${NC}"
        return 0
    else
        echo -e "${YELLOW}Target needs additional configuration${NC}"
        return 1
    fi
}

# Main
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FireDog Target Preconfiguration${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Target IP:   $TARGET_IP"
echo "SSH Port:    $SSH_PORT"
echo "Username:    $USERNAME"
echo "Operation:   $OPERATION"
echo ""

case "$OPERATION" in
    all)
        op_ssh_key && op_sudoers && op_ssh_harden && op_cron
        ;;
    ssh-key)
        op_ssh_key
        ;;
    sudoers)
        op_sudoers
        ;;
    ssh-harden)
        op_ssh_harden
        ;;
    cron)
        op_cron
        ;;
    check)
        op_check
        ;;
    *)
        echo -e "${RED}Unknown operation: $OPERATION${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Done${NC}"
echo -e "${GREEN}========================================${NC}"

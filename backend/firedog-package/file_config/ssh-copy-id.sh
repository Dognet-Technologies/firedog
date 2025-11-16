#!/bin/bash
#
# FireDog SSH Key Setup Script
# Copies SSH public key to target for passwordless authentication
#
# Usage: ./ssh-copy-id.sh <target-ip> [ssh-port] [username]
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Default values
SSH_PORT=${2:-22}
USERNAME=${3:-microcyber}
SSH_KEY_PATH="/opt/firedog/ssh/id_ed25519.pub"

# Check arguments
if [ -z "$1" ]; then
    echo -e "${RED}Error: Target IP address required${NC}"
    echo "Usage: $0 <target-ip> [ssh-port] [username]"
    echo "Example: $0 192.168.1.100 22 microcyber"
    exit 1
fi

TARGET_IP="$1"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FireDog SSH Key Setup${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Target IP:   $TARGET_IP"
echo "SSH Port:    $SSH_PORT"
echo "Username:    $USERNAME"
echo "Public Key:  $SSH_KEY_PATH"
echo ""

# Check if public key exists
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo -e "${RED}Error: Public key not found at $SSH_KEY_PATH${NC}"
    echo ""
    echo "Generate SSH key pair first:"
    echo "  sudo -u microcyber ssh-keygen -t ed25519 -f /opt/firedog/ssh/id_ed25519 -N \"\""
    exit 1
fi

# Check if user exists on target
echo -e "${YELLOW}[1/4]${NC} Checking if user '$USERNAME' exists on target..."
if ! ssh -p "$SSH_PORT" -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
    "$USERNAME@$TARGET_IP" "exit" 2>/dev/null; then
    echo -e "${YELLOW}Note: Password authentication required${NC}"
fi

# Create .ssh directory on target
echo -e "${YELLOW}[2/4]${NC} Creating .ssh directory on target..."
ssh -p "$SSH_PORT" "$USERNAME@$TARGET_IP" "mkdir -p ~/.ssh && chmod 700 ~/.ssh" || {
    echo -e "${RED}Failed to create .ssh directory${NC}"
    exit 1
}

# Copy public key to target
echo -e "${YELLOW}[3/4]${NC} Copying public key to target..."
cat "$SSH_KEY_PATH" | ssh -p "$SSH_PORT" "$USERNAME@$TARGET_IP" \
    "cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys" || {
    echo -e "${RED}Failed to copy public key${NC}"
    exit 1
}

# Test key-based authentication
echo -e "${YELLOW}[4/4]${NC} Testing key-based authentication..."
if ssh -p "$SSH_PORT" -i "${SSH_KEY_PATH%.pub}" -o PasswordAuthentication=no \
    "$USERNAME@$TARGET_IP" "echo 'SSH key authentication successful'" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ SSH key authentication working!${NC}"
else
    echo -e "${RED}✗ SSH key authentication failed${NC}"
    echo "Try manually: ssh -i ${SSH_KEY_PATH%.pub} $USERNAME@$TARGET_IP"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SSH Key Setup Completed${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "You can now connect without password:"
echo "  ssh -i ${SSH_KEY_PATH%.pub} -p $SSH_PORT $USERNAME@$TARGET_IP"
echo ""
echo "Next steps:"
echo "  1. Configure sudoers: ./preconfigure-target.sh $TARGET_IP sudoers"
echo "  2. Harden SSH: ./preconfigure-target.sh $TARGET_IP ssh-harden"
echo "  3. Install FireDog: Use web console install feature"
echo ""

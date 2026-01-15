#!/bin/bash
#
# FireDog Dog Agent - Installation Script
# This script installs the Dog Agent on the target machine
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Variables
INSTALL_DIR="/opt/sentinelsuite/firedog"
CONFIG_DIR="/etc/dog-agent"
LOG_DIR="/var/log/dog-agent"
SERVICE_NAME="dog-agent"

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}FireDog Dog Agent Installation${NC}"
echo -e "${GREEN}====================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo "Please run: sudo $0"
    exit 1
fi

# Check OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VERSION=$VERSION_ID
else
    echo -e "${RED}Error: Cannot detect OS${NC}"
    exit 1
fi

echo -e "${YELLOW}Detected OS: $OS $VERSION${NC}"

# Install system dependencies
echo -e "${GREEN}[1/8] Installing system dependencies...${NC}"
if [ "$OS" == "debian" ] || [ "$OS" == "ubuntu" ]; then
    apt-get update -qq
    apt-get install -y python3 python3-pip python3-venv iptables > /dev/null 2>&1
else
    echo -e "${RED}Error: Unsupported OS. Only Debian/Ubuntu are supported.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ System dependencies installed${NC}"

# Create directories
echo -e "${GREEN}[2/8] Creating directories...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$LOG_DIR"
echo -e "${GREEN}✓ Directories created${NC}"

# Copy agent files
echo -e "${GREEN}[3/8] Copying agent files...${NC}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cp "$SCRIPT_DIR"/*.py "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/dog_agent.py"
echo -e "${GREEN}✓ Agent files copied${NC}"

# Install Python dependencies
echo -e "${GREEN}[4/8] Installing Python dependencies...${NC}"
pip3 install -q -r "$INSTALL_DIR/requirements.txt"
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Configure agent
echo -e "${GREEN}[5/8] Configuring agent...${NC}"
if [ ! -f "$CONFIG_DIR/agent.conf" ]; then
    cp "$SCRIPT_DIR/agent.conf.example" "$CONFIG_DIR/agent.conf"
    echo -e "${YELLOW}⚠ Configuration file created at $CONFIG_DIR/agent.conf${NC}"
    echo -e "${YELLOW}⚠ Please edit this file with your server URL and API key${NC}"
else
    echo -e "${YELLOW}⚠ Configuration file already exists, skipping...${NC}"
fi
chmod 600 "$CONFIG_DIR/agent.conf"
echo -e "${GREEN}✓ Configuration ready${NC}"

# Create systemd service
echo -e "${GREEN}[6/8] Creating systemd service...${NC}"
cat > /etc/systemd/system/$SERVICE_NAME.service << 'SERVICE_EOF'
[Unit]
Description=FireDog Dog Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/sentinelsuite/firedog
ExecStart=/usr/bin/python3 /opt/sentinelsuite/firedog/dog_agent.py --config /etc/dog-agent/agent.conf
Restart=always
RestartSec=10
StandardOutput=append:/var/log/dog-agent/dog-agent.log
StandardError=append:/var/log/dog-agent/dog-agent.log

[Install]
WantedBy=multi-user.target
SERVICE_EOF
echo -e "${GREEN}✓ Systemd service created${NC}"

# Reload systemd
echo -e "${GREEN}[7/8] Reloading systemd...${NC}"
systemctl daemon-reload
systemctl enable $SERVICE_NAME
echo -e "${GREEN}✓ Service enabled${NC}"

# Final instructions
echo ""
echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}====================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "1. Edit the configuration file:"
echo "   sudo nano $CONFIG_DIR/agent.conf"
echo ""
echo "2. Set your server URL and API key"
echo ""
echo "3. Start the agent:"
echo "   sudo systemctl start $SERVICE_NAME"
echo ""
echo "4. Check status:"
echo "   sudo systemctl status $SERVICE_NAME"
echo ""
echo "5. View logs:"
echo "   sudo journalctl -u $SERVICE_NAME -f"
echo "   or"
echo "   sudo tail -f $LOG_DIR/dog-agent.log"
echo ""
echo -e "${GREEN}For more information, visit the documentation.${NC}"
echo ""


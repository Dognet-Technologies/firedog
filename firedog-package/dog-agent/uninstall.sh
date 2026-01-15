#!/bin/bash
#
# FireDog Dog Agent - Uninstallation Script
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SERVICE_NAME="dog-agent"
INSTALL_DIR="/opt/sentinelsuite/firedog"
CONFIG_DIR="/etc/dog-agent"
LOG_DIR="/var/log/dog-agent"

echo -e "${RED}====================================${NC}"
echo -e "${RED}FireDog Dog Agent Uninstallation${NC}"
echo -e "${RED}====================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root${NC}"
    exit 1
fi

read -p "Are you sure you want to uninstall Dog Agent? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

echo -e "${YELLOW}[1/5] Stopping service...${NC}"
systemctl stop $SERVICE_NAME || true
systemctl disable $SERVICE_NAME || true
echo -e "${GREEN}✓ Service stopped${NC}"

echo -e "${YELLOW}[2/5] Removing systemd service...${NC}"
rm -f /etc/systemd/system/$SERVICE_NAME.service
systemctl daemon-reload
echo -e "${GREEN}✓ Service removed${NC}"

echo -e "${YELLOW}[3/5] Removing agent files...${NC}"
rm -rf "$INSTALL_DIR"
echo -e "${GREEN}✓ Agent files removed${NC}"

read -p "Remove configuration and logs? (yes/no): " -r
if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}[4/5] Removing configuration...${NC}"
    rm -rf "$CONFIG_DIR"
    echo -e "${GREEN}✓ Configuration removed${NC}"
    
    echo -e "${YELLOW}[5/5] Removing logs...${NC}"
    rm -rf "$LOG_DIR"
    echo -e "${GREEN}✓ Logs removed${NC}"
else
    echo -e "${YELLOW}⚠ Configuration and logs preserved${NC}"
    echo "   Config: $CONFIG_DIR"
    echo "   Logs: $LOG_DIR"
fi

echo ""
echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}Uninstallation Complete!${NC}"
echo -e "${GREEN}====================================${NC}"


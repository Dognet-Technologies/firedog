#!/bin/bash
#
# Setup FireDog Master Directory Structure
# Crea la struttura directory standard per il master FireDog
#

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  FireDog Master Directory Setup            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""

# Directory base
FIREDOG_BASE="/opt/firedog"

echo -e "${CYAN}→${NC} Creazione struttura directory in $FIREDOG_BASE..."

# Crea directory
sudo mkdir -p "$FIREDOG_BASE/.ssh"
sudo mkdir -p "$FIREDOG_BASE/logs"
sudo mkdir -p "$FIREDOG_BASE/exports"
sudo mkdir -p "$FIREDOG_BASE/temp"

# Imposta permessi
sudo chmod 700 "$FIREDOG_BASE/.ssh"
sudo chmod 755 "$FIREDOG_BASE/logs"
sudo chmod 755 "$FIREDOG_BASE/exports"
sudo chmod 755 "$FIREDOG_BASE/temp"

# Imposta ownership per www-data (Django)
sudo chown -R www-data:www-data "$FIREDOG_BASE"

echo -e "${GREEN}✓${NC} Directory create:"
echo ""
echo "  $FIREDOG_BASE/.ssh/       (700) - Chiavi SSH private per targets"
echo "  $FIREDOG_BASE/logs/       (755) - Log operazioni master"
echo "  $FIREDOG_BASE/exports/    (755) - Export JSON scaricati da targets"
echo "  $FIREDOG_BASE/temp/       (755) - File temporanei"
echo ""
echo "  Owner: www-data:www-data"
echo ""
echo -e "${GREEN}✓${NC} Setup completato!"
echo ""
echo "Ora puoi:"
echo "  1. Generare chiavi SSH per targets: ./prepare-package.sh --with-ssh-key"
echo "  2. Le chiavi saranno salvate in: $FIREDOG_BASE/.ssh/"
echo ""

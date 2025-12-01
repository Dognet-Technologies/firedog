#!/bin/bash
#
# Installa/Aggiorna i file del pacchetto FireDog sul master
#
# Questo script copia i file sorgente del pacchetto in /opt/firedog/firedog-package
# in modo che prepare-package.sh possa crearli per l'installazione sui target
#
# Usage:
#   sudo ./install-on-master.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Controlla privilegi root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}✗${NC} Questo script deve essere eseguito come root (usa sudo)"
   exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="/opt/firedog/firedog-package"

echo -e "${GREEN}"
cat << "EOF"
╔═══════════════════════════════════════════════╗
║   FireDog Master - Installazione Pacchetto   ║
╚═══════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Crea directory di destinazione
echo -e "${CYAN}→${NC} Creazione directory $DEST_DIR..."
mkdir -p "$DEST_DIR"

# Copia file del pacchetto
echo -e "${CYAN}→${NC} Copia file pacchetto..."
cp -r "$SCRIPT_DIR"/* "$DEST_DIR/" 2>/dev/null || true

# Rimuovi file non necessari
rm -f "$DEST_DIR/install-on-master.sh"
rm -rf "$DEST_DIR/.git" 2>/dev/null || true

# Imposta permessi
echo -e "${CYAN}→${NC} Impostazione permessi..."
chmod +x "$DEST_DIR/prepare-package.sh" 2>/dev/null || true
chmod +x "$DEST_DIR/install.sh" 2>/dev/null || true
chmod +x "$DEST_DIR/setup-master-dirs.sh" 2>/dev/null || true
chmod 644 "$DEST_DIR"/*.conf 2>/dev/null || true
chmod 644 "$DEST_DIR"/*.service 2>/dev/null || true

# Crea directory per chiavi SSH e export
echo -e "${CYAN}→${NC} Configurazione directory master..."
mkdir -p /opt/firedog/.ssh
mkdir -p /opt/firedog/logs
mkdir -p /opt/firedog/exports
mkdir -p /opt/firedog/temp

chmod 700 /opt/firedog/.ssh
chmod 755 /opt/firedog/logs
chmod 755 /opt/firedog/exports
chmod 755 /opt/firedog/temp

# Imposta ownership per www-data (Django)
chown -R www-data:www-data /opt/firedog

# Mantieni /opt/firedog/firedog-package accessibile a tutti per prepare-package.sh
chmod 755 "$DEST_DIR"

echo ""
echo -e "${GREEN}✓${NC} Installazione completata!"
echo ""
echo "File del pacchetto installati in:"
echo "  ${CYAN}$DEST_DIR/${NC}"
echo ""
echo "Struttura directory master:"
echo "  /opt/firedog/"
echo "  ├── firedog-package/  (file sorgente per target)"
echo "  ├── .ssh/             (chiavi SSH per target)"
echo "  ├── exports/          (JSON esportati dai target)"
echo "  ├── logs/             (log operazioni)"
echo "  └── temp/             (file temporanei)"
echo ""
echo "PROSSIMO PASSO:"
echo ""
echo "Per creare un pacchetto per un target:"
echo "  ${CYAN}cd /opt/firedog/firedog-package${NC}"
echo "  ${CYAN}sudo ./prepare-package.sh --with-ssh-key${NC}"
echo ""

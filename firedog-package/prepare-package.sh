#!/bin/bash
#
# Prepara pacchetto FireDog per installazione su target
#
# Usage:
#   ./prepare-package.sh [--with-ssh-key]
#
# Output:
#   firedog-package.tar.gz (pronto per copiare su target)
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Directory sorgente: in produzione i file sono in /opt/firedog/firedog-package
FIREDOG_PACKAGE_DIR="/opt/firedog/firedog-package"
OUTPUT_DIR="/tmp/firedog-package-$$"
WITH_SSH_KEY=false

if [[ "$1" == "--with-ssh-key" ]]; then
    WITH_SSH_KEY=true
fi

echo -e "${GREEN}"
cat << "EOF"
╔═══════════════════════════════════════════════╗
║   FireDog Package Preparation                 ║
╚═══════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Verifica che la directory sorgente esista
if [[ ! -d "$FIREDOG_PACKAGE_DIR" ]]; then
    echo -e "${RED}✗${NC} Errore: directory sorgente non trovata: $FIREDOG_PACKAGE_DIR"
    echo ""
    echo "Assicurati che i file del pacchetto siano installati in:"
    echo "  $FIREDOG_PACKAGE_DIR"
    exit 1
fi

# Crea directory temporanea
mkdir -p "$OUTPUT_DIR"
echo -e "${CYAN}→${NC} Directory temporanea: $OUTPUT_DIR"
echo -e "${CYAN}→${NC} Directory sorgente: $FIREDOG_PACKAGE_DIR"

# Copia tutti i file del pacchetto
echo -e "${CYAN}→${NC} Copia file pacchetto..."
cp -r "$FIREDOG_PACKAGE_DIR"/* "$OUTPUT_DIR/" 2>/dev/null || true

# Rimuovi file non necessari
rm -f "$OUTPUT_DIR/prepare-package.sh"
rm -f "$OUTPUT_DIR/test-target-deployment.sh"
rm -f "$OUTPUT_DIR/TESTING.md"
rm -rf "$OUTPUT_DIR/.git" 2>/dev/null || true

echo -e "${GREEN}✓${NC} File pacchetto copiati"

# Genera chiave SSH se richiesto
if [[ "$WITH_SSH_KEY" == true ]]; then
    echo ""
    echo -e "${CYAN}→${NC} Generazione chiave SSH..."

    # Crea directory per chiavi sul master se non esiste
    FIREDOG_SSH_DIR="/opt/firedog/.ssh"
    if [[ ! -d "$FIREDOG_SSH_DIR" ]]; then
        echo "  → Creazione directory $FIREDOG_SSH_DIR..."
        sudo mkdir -p "$FIREDOG_SSH_DIR"
        sudo chmod 700 "$FIREDOG_SSH_DIR"
    fi

    SSH_KEY_NAME="firedog_target_$(date +%Y%m%d_%H%M%S)"
    SSH_KEY_PATH="$FIREDOG_SSH_DIR/$SSH_KEY_NAME"

    # Genera chiave direttamente in /opt/firedog/.ssh/
    sudo ssh-keygen -t ed25519 -f "$SSH_KEY_PATH" -N "" -C "firedog-master" &>/dev/null

    if [[ -f "${SSH_KEY_PATH}.pub" ]]; then
        # Copia chiave pubblica nel pacchetto
        sudo cp "${SSH_KEY_PATH}.pub" "$OUTPUT_DIR/firedog_ssh_key.pub"

        # Fix ownership per il pacchetto
        sudo chown $USER:$USER "$OUTPUT_DIR/firedog_ssh_key.pub"

        # Verifica che la copia sia riuscita
        if [[ ! -f "$OUTPUT_DIR/firedog_ssh_key.pub" ]]; then
            echo -e "${RED}✗${NC} Errore: chiave pubblica non copiata nel pacchetto"
            exit 1
        fi

        echo -e "${GREEN}✓${NC} Chiave SSH generata e salvata"
        echo ""
        echo -e "  Chiave PRIVATA (master): ${CYAN}$SSH_KEY_PATH${NC}"
        echo "  Chiave PUBBLICA (pacchetto): firedog_ssh_key.pub"
        echo ""
        echo -e "${GREEN}→${NC} La chiave privata è stata salvata in modo permanente in:"
        echo "  $FIREDOG_SSH_DIR/"
    else
        echo -e "${RED}✗${NC} Errore: generazione chiave SSH fallita"
        exit 1
    fi
else
    echo ""
    echo -e "${YELLOW}→${NC} Nessuna chiave SSH generata"
    echo "  La chiave dovrà essere configurata manualmente dopo l'installazione"
fi

# Crea archivio
echo ""
echo -e "${CYAN}→${NC} Creazione archivio..."

# Rimuovi archivio esistente se presente
rm -f /tmp/firedog-package.tar.gz

# Crea archivio con path assoluto
tar czf /tmp/firedog-package.tar.gz -C /tmp "$(basename $OUTPUT_DIR)"

if [[ -f /tmp/firedog-package.tar.gz ]]; then
    SIZE=$(du -h /tmp/firedog-package.tar.gz | cut -f1)
    echo -e "${GREEN}✓${NC} Archivio creato: /tmp/firedog-package.tar.gz ($SIZE)"

    # Verifica contenuto archivio
    if [[ "$WITH_SSH_KEY" == true ]]; then
        echo ""
        echo -e "${CYAN}→${NC} Verifica contenuto archivio..."
        if tar tzf /tmp/firedog-package.tar.gz | grep -q "firedog_ssh_key.pub"; then
            echo -e "${GREEN}✓${NC} Chiave SSH inclusa nel pacchetto"
        else
            echo -e "${RED}✗${NC} ERRORE: Chiave SSH NON trovata nel pacchetto!"
            echo "  Contenuto archivio:"
            tar tzf /tmp/firedog-package.tar.gz | grep -E "(firedog_ssh|\.pub)" || echo "  (nessuna chiave trovata)"
            exit 1
        fi
    fi
else
    echo -e "${RED}✗${NC} Errore creazione archivio"
    exit 1
fi

# Cleanup directory temporanea
rm -rf "$OUTPUT_DIR"

# Istruzioni finali
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Pacchetto pronto per installazione!       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo -e "File creato: ${CYAN}/tmp/firedog-package.tar.gz${NC}"
echo ""
echo "PROSSIMI PASSI:"
echo ""
echo "1. Copia il pacchetto sul target:"
echo -e "   ${CYAN}scp /tmp/firedog-package.tar.gz simone@192.168.1.50:/tmp/${NC}"
echo ""
echo "2. Connettiti al target:"
echo -e "   ${CYAN}ssh simone@192.168.1.50${NC}"
echo ""
echo "3. Estrai ed esegui l'installazione (SUL TARGET):"
echo -e "   ${CYAN}cd /tmp${NC}"
echo -e "   ${CYAN}tar xzf firedog-package.tar.gz${NC}"
echo -e "   ${CYAN}cd firedog-package-*/${NC}"
echo -e "   ${CYAN}sudo ./install.sh${NC}"
echo ""
echo "4. Segui le istruzioni interattive dell'installer"
echo ""

if [[ "$WITH_SSH_KEY" == true ]]; then
    echo "5. Dopo l'installazione, la chiave privata è già salvata in:"
    echo -e "   ${CYAN}$SSH_KEY_PATH${NC}"
    echo ""
    echo "6. Configura ownership per Django/web console:"
    echo -e "   ${CYAN}sudo chown www-data:www-data $SSH_KEY_PATH${NC}"
    echo -e "   ${CYAN}sudo chmod 600 $SSH_KEY_PATH${NC}"
    echo ""
    echo "7. Testa connessione SSH:"
    echo -e "   ${CYAN}ssh -i $SSH_KEY_PATH microcyber@192.168.1.50 \"sudo firewall-manager --list\"${NC}"
    echo ""
fi

echo "NOTE:"
echo "  - L'installazione richiede privilegi root (usa sudo)"
echo "  - L'utente 'microcyber' verrà creato automaticamente durante l'installazione"
echo "  - L'utente con cui ti connetti (es. simone) non viene modificato"
echo ""

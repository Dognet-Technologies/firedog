#!/bin/bash
#
# Setup Export Cron for FireDog
# Configura export automatico stato firewall ogni 60 secondi
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIREWALL_MANAGER="/usr/local/bin/firewall-manager"
EXPORT_DIR="/opt/firedog/export"
CRON_SCRIPT="/usr/local/bin/firedog-export"

echo "🔧 Configurazione export automatico FireDog..."

# Verifica firewall-manager installato
if [ ! -f "$FIREWALL_MANAGER" ]; then
    echo "❌ firewall-manager non trovato in $FIREWALL_MANAGER"
    echo "   Esegui prima install.sh"
    exit 1
fi

# Crea directory export
mkdir -p "$EXPORT_DIR"
chmod 755 "$EXPORT_DIR"

# Crea script wrapper per cron
cat > "$CRON_SCRIPT" << 'EOF'
#!/bin/bash
#
# FireDog Export Wrapper
# Esegue export stato firewall con gestione errori
#

EXPORT_PATH="/opt/firedog/export/status.json"
LOCK_FILE="/var/run/firedog-export.lock"
LOG_FILE="/var/log/firedog-export.log"

# Evita esecuzioni multiple
if [ -f "$LOCK_FILE" ]; then
    # Verifica età lock (max 5 minuti)
    if [ $(($(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0))) -gt 300 ]; then
        rm -f "$LOCK_FILE"
    else
        exit 0
    fi
fi

# Crea lock
touch "$LOCK_FILE"

# Esegui export
{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting export..."
    if sudo /usr/local/bin/firewall-manager --export-json "$EXPORT_PATH" 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Export completed successfully"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Export failed with exit code $?"
    fi
} >> "$LOG_FILE" 2>&1

# Rimuovi lock
rm -f "$LOCK_FILE"

# Limita dimensione log (ultimi 1000 righe)
if [ -f "$LOG_FILE" ]; then
    tail -n 1000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi
EOF

chmod +x "$CRON_SCRIPT"

echo "✓ Script export creato: $CRON_SCRIPT"

# Crea cron job (ogni minuto)
CRON_FILE="/etc/cron.d/firedog-export"

cat > "$CRON_FILE" << EOF
# FireDog - Export automatico stato firewall
# Esegue export ogni 60 secondi

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# Export ogni minuto
* * * * * root $CRON_SCRIPT
EOF

chmod 644 "$CRON_FILE"

echo "✓ Cron job configurato: $CRON_FILE"
echo "✓ Frequenza: ogni 60 secondi"

# Test iniziale
echo ""
echo "🧪 Test export..."
if sudo "$FIREWALL_MANAGER" --export-json "$EXPORT_DIR/status.json"; then
    echo "✓ Export test completato con successo"
    echo "✓ File generato: $EXPORT_DIR/status.json"

    # Mostra dimensione file
    if [ -f "$EXPORT_DIR/status.json" ]; then
        SIZE=$(du -h "$EXPORT_DIR/status.json" | cut -f1)
        echo "✓ Dimensione: $SIZE"
    fi
else
    echo "❌ Export test fallito"
    exit 1
fi

echo ""
echo "✅ Configurazione completata!"
echo ""
echo "📋 Informazioni:"
echo "   - Export path: $EXPORT_DIR/status.json"
echo "   - Frequenza: ogni 60 secondi"
echo "   - Log: /var/log/firedog-export.log"
echo "   - Cron: $CRON_FILE"
echo ""
echo "💡 Per verificare l'export:"
echo "   cat $EXPORT_DIR/status.json | jq ."
echo ""
echo "💡 Per monitorare i log:"
echo "   tail -f /var/log/firedog-export.log"

#!/bin/bash
#
# Setup Pull Cron for FireDog Master
# Configura pull periodico stato target ogni 5 minuti
#

set -e

BACKEND_DIR="/opt/firedog/backend"
VENV_DIR="/opt/firedog/venv"
CRON_SCRIPT="/usr/local/bin/firedog-pull-status"
CRON_FILE="/etc/cron.d/firedog-pull-status"
LOG_FILE="/var/log/firedog-pull-status.log"

echo "🔧 Configurazione pull periodico status target..."

# Verifica Django management command
if [ ! -f "$BACKEND_DIR/manage.py" ]; then
    echo "❌ Django backend non trovato in $BACKEND_DIR"
    echo "   Assicurati che FireDog backend sia installato"
    exit 1
fi

# Crea script wrapper per cron
cat > "$CRON_SCRIPT" << EOF
#!/bin/bash
#
# FireDog Pull Status Wrapper
# Esegue pull periodico stato target con gestione errori
#

BACKEND_DIR="$BACKEND_DIR"
VENV_DIR="$VENV_DIR"
LOG_FILE="$LOG_FILE"
LOCK_FILE="/var/run/firedog-pull-status.lock"

# Evita esecuzioni multiple
if [ -f "\$LOCK_FILE" ]; then
    # Verifica età lock (max 10 minuti)
    if [ \$(($(date +%s) - $(stat -c %Y "\$LOCK_FILE" 2>/dev/null || echo 0))) -gt 600 ]; then
        rm -f "\$LOCK_FILE"
    else
        exit 0
    fi
fi

# Crea lock
touch "\$LOCK_FILE"

# Attiva virtualenv se esiste
if [ -d "\$VENV_DIR" ]; then
    source "\$VENV_DIR/bin/activate"
fi

# Esegui pull
{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting pull..."

    cd "\$BACKEND_DIR"

    if python manage.py pull_targets_status 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pull completed successfully"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pull failed with exit code \$?"
    fi

} >> "\$LOG_FILE" 2>&1

# Rimuovi lock
rm -f "\$LOCK_FILE"

# Limita dimensione log (ultimi 2000 righe)
if [ -f "\$LOG_FILE" ]; then
    tail -n 2000 "\$LOG_FILE" > "\$LOG_FILE.tmp" && mv "\$LOG_FILE.tmp" "\$LOG_FILE"
fi
EOF

chmod +x "$CRON_SCRIPT"

echo "✓ Script pull creato: $CRON_SCRIPT"

# Crea cron job (ogni 5 minuti)
cat > "$CRON_FILE" << EOF
# FireDog - Pull periodico stato target
# Scarica file JSON di stato dai target ogni 5 minuti

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# Pull ogni 5 minuti
*/5 * * * * root $CRON_SCRIPT
EOF

chmod 644 "$CRON_FILE"

echo "✓ Cron job configurato: $CRON_FILE"
echo "✓ Frequenza: ogni 5 minuti"

# Crea directory log
touch "$LOG_FILE"
chmod 644 "$LOG_FILE"

echo ""
echo "🧪 Test pull..."
echo ""

# Test manuale (richiede virtualenv attivo se presente)
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

cd "$BACKEND_DIR"

if python manage.py pull_targets_status --dry-run; then
    echo ""
    echo "✓ Test completato con successo"
else
    echo ""
    echo "❌ Test fallito"
    exit 1
fi

echo ""
echo "✅ Configurazione completata!"
echo ""
echo "📋 Informazioni:"
echo "   - Frequenza: ogni 5 minuti"
echo "   - Log: $LOG_FILE"
echo "   - Cron: $CRON_FILE"
echo "   - Script: $CRON_SCRIPT"
echo ""
echo "💡 Per eseguire pull manuale:"
echo "   cd $BACKEND_DIR"
echo "   source $VENV_DIR/bin/activate  # Se virtualenv presente"
echo "   python manage.py pull_targets_status"
echo ""
echo "💡 Per monitorare i log:"
echo "   tail -f $LOG_FILE"
echo ""
echo "💡 Per pull da singolo target:"
echo "   python manage.py pull_targets_status --target-id 1"

#!/usr/bin/env bash
#
# FireDog — rigenerazione segreti al primo avvio (VM appliance).
#
# Chiamato da firedog-first-boot.service (Type=oneshot) una volta sola. Al
# termine disabilita se stesso: dai prossimi avvii FireDog parte normalmente.
# Progettato per essere idempotente se interrotto e rilanciato.
#
# A differenza dell'equivalente SentinelCore, qui si rigenera ANCHE il
# certificato TLS self-signed: quello generato in fase di build (provision.sh)
# porta il CN/SAN dell'IP del builder, non del clone — ogni istanza deployata
# ha un IP reale diverso e deve avere il proprio certificato.
set -euo pipefail

INSTALL_DIR=/opt/firedog
ENV_FILE="$INSTALL_DIR/backend/.env"
TLS_DIR=/etc/ssl/firedog
DB_NAME=firedog
DB_USER=firedog
LOG=/var/log/firedog-first-boot.log

mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1
echo "=== first-boot $(date '+%Y-%m-%d %H:%M:%S') ==="

# ── 1. Rigenera SSH host keys se rimosse durante build ──────────────────────
# BUG osservato in test (2026-09-21): ssh.service parte PRIMA di
# firedog-first-boot.service e fallisce ripetutamente durante il boot
# perché gli host key non esistono ancora (rimossi da provision.sh prima
# dell'export). systemd esaurisce lo StartLimitBurst e mette l'unit in
# stato "failed (start-limit-hit)": da lì in poi anche un `systemctl
# restart` esplicito fallisce silenziosamente finché non si pulisce lo
# stato con `reset-failed` — SSH restava morto per sempre sul clone.
if ! ls /etc/ssh/ssh_host_*_key 2>/dev/null | grep -q .; then
    echo "[1/9] Rigenerazione SSH host keys..."
    ssh-keygen -A 2>/dev/null || dpkg-reconfigure openssh-server 2>/dev/null || true
else
    echo "[1/9] SSH host keys presenti"
fi
systemctl reset-failed ssh.service 2>/dev/null || true
if ! systemctl restart ssh; then
    echo "ERRORE: ssh.service non riparte nemmeno dopo reset-failed" >&2
fi

# ── 2. IP reale del clone ────────────────────────────────────────────────────
echo "[2/9] Rilevamento IP..."
SERVER_IP="$(ip -4 route get 1.1.1.1 2>/dev/null \
    | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')"
[ -z "$SERVER_IP" ] && SERVER_IP="$(hostname -I | awk '{print $1}')"
[ -z "$SERVER_IP" ] && { echo "ERRORE: impossibile rilevare l'IP"; exit 1; }
echo "    IP: $SERVER_IP"

# ── 3. DB password corrente da .env ──────────────────────────────────────────
echo "[3/9] Lettura config corrente..."
CURRENT_DB_PASS="$(grep '^DB_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
if [ -z "$CURRENT_DB_PASS" ]; then
    echo "ERRORE: impossibile leggere DB_PASSWORD da $ENV_FILE"
    exit 1
fi

# ── 4. Genera nuovi segreti ──────────────────────────────────────────────────
echo "[4/9] Generazione nuovi segreti..."
NEW_DB_PASS="$(openssl rand -hex 24)"
NEW_SECRET_KEY="$(openssl rand -hex 32)"
ADMIN_USER="admin"
ADMIN_PASS="FireDog2026!!"
ROOT_PASS="FireDog1st!"

# ── 5. Aggiorna backend/.env ─────────────────────────────────────────────────
echo "[5/9] Aggiornamento .env..."
sed -i \
    -e "s#^SECRET_KEY=.*#SECRET_KEY=${NEW_SECRET_KEY}#" \
    -e "s#^DB_PASSWORD=.*#DB_PASSWORD=${NEW_DB_PASS}#" \
    -e "s#^ALLOWED_HOSTS=.*#ALLOWED_HOSTS=${SERVER_IP},localhost,127.0.0.1#" \
    -e "s#^CORS_ALLOWED_ORIGINS=.*#CORS_ALLOWED_ORIGINS=https://${SERVER_IP}#" \
    "$ENV_FILE"

# ── 6. Aggiorna password utente PostgreSQL ───────────────────────────────────
echo "[6/9] Aggiornamento credenziali DB..."
sudo -u postgres psql -v ON_ERROR_STOP=1 \
    -c "ALTER ROLE $DB_USER PASSWORD '$NEW_DB_PASS';" >/dev/null

# ── 7. Rigenera certificato TLS per l'IP reale del clone ────────────────────
echo "[7/9] Rigenerazione certificato TLS ($SERVER_IP)..."
mkdir -p "$TLS_DIR"
SAN_TYPE="DNS"
echo "$SERVER_IP" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' && SAN_TYPE="IP"
openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
    -keyout "$TLS_DIR/firedog.key" -out "$TLS_DIR/firedog.crt" \
    -subj "/CN=$SERVER_IP" \
    -addext "subjectAltName=$SAN_TYPE:$SERVER_IP" >/dev/null 2>&1
chmod 600 "$TLS_DIR/firedog.key"
chmod 644 "$TLS_DIR/firedog.crt"
sed -i "s/server_name .*/server_name ${SERVER_IP};/" /etc/nginx/sites-available/firedog
nginx -t && systemctl reload nginx

# ── 8. Riavvia i servizi con la nuova config, verifica admin ────────────────
echo "[8/9] Riavvio servizi e verifica..."
systemctl restart firedog-backend firedog-celery firedog-celerybeat || true

echo "    Attendo risposta backend (max 60s)..."
HEALTH_OK=0
for i in $(seq 1 60); do
    CODE="$(curl -sk -o /dev/null -w '%{http_code}' "https://127.0.0.1/api/token/" 2>/dev/null || true)"
    # /api/token/ accetta solo POST: 405 = Daphne+Django rispondono davvero
    if [ "$CODE" = "405" ]; then
        HEALTH_OK=1; break
    fi
    sleep 1
done

ADMIN_STATUS="ERRORE"
if [ "$HEALTH_OK" = "1" ]; then
    # L'utente admin è già stato creato da install.sh (via provision.sh) con
    # le credenziali fisse dell'appliance. Qui verifichiamo solo che esista.
    EXISTS="$(PGPASSWORD="$NEW_DB_PASS" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -tAc \
        "SELECT 1 FROM auth_user WHERE username='$ADMIN_USER' AND is_superuser" 2>/dev/null || true)"
    [ "$EXISTS" = "1" ] && ADMIN_STATUS="OK"
else
    echo "    WARN: backend non risponde (health=$CODE)"
fi

# ── 9. Scrivi credenziali su /etc/motd + /etc/issue.d/ ──────────────────────
echo "[9/9] Credenziali iniziali → /etc/motd"

if [ "$ADMIN_STATUS" = "OK" ]; then
    CRED_BLOCK="  Web UI:
    Utente:   $ADMIN_USER
    Password: $ADMIN_PASS

  SSH / Console:
    Utente:   root
    Password: $ROOT_PASS

  CAMBIA entrambe le password al primo accesso."
else
    CRED_BLOCK="  Credenziali web admin: verifica non riuscita.
  Vedi: $LOG

  SSH / Console:
    Utente:   root
    Password: $ROOT_PASS"
fi

mkdir -p /etc/issue.d
cat > /etc/issue.d/firedog.issue <<ISSUE

╔══════════════════════════════════════════════════════════════╗
║            FireDog — Credenziali iniziali istanza             ║
╠══════════════════════════════════════════════════════════════╣
  URL:        https://$SERVER_IP/
  (certificato self-signed: il browser avviserà al primo accesso)
$CRED_BLOCK
╚══════════════════════════════════════════════════════════════╝

ISSUE

cat > /etc/motd <<MOTD

╔══════════════════════════════════════════════════════════════╗
║            FireDog — Credenziali iniziali istanza             ║
╠══════════════════════════════════════════════════════════════╣
  URL:        https://$SERVER_IP/
  (certificato self-signed: il browser avviserà al primo accesso)
$CRED_BLOCK
╚══════════════════════════════════════════════════════════════╝
MOTD

echo ""
cat /etc/motd
echo ""

# ── Forza il cambio password root al primo login ─────────────────────────────
# Ultimo step, non prima: gira come root e usa `sudo -u postgres` allo step 6
# — sudo rivalida sempre l'account CHIAMANTE (root) via PAM anche se sei già
# root, e una password già scaduta fa fallire chauthtok in modo non
# interattivo, interrompendo tutto il first-boot a metà (stesso motivo già
# documentato nell'equivalente SentinelCore).
echo "Forzo il cambio password di root al prossimo login..."
chage -d 0 root

systemctl disable firedog-first-boot.service
echo "=== first-boot completato — servizio disabilitato. ==="

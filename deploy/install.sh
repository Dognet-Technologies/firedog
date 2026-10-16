#!/usr/bin/env bash
#
# FireDog — installer del master (backend Django + frontend React + Celery +
# nginx). Scripting automatico dei passi manuali documentati in INSTALL.md,
# più generazione di un certificato TLS self-signed (HTTPS di default).
#
# Uso:
#   sudo ./deploy/install.sh [opzioni]
#
# Opzioni (tutte hanno un fallback via variabile d'ambiente FIREDOG_*, usato
# dal provisioning headless dell'immagine VM — vedi packaging/appliance/):
#   --server-name <ip-o-host>   default: IP rilevato automaticamente
#   --install-user <utente>     default: firedog (creato se assente)
#   --install-dir <path>        default: root del checkout corrente
#   --db-password <pw>          default: generata (openssl rand)
#   --admin-user <user>         default: admin
#   --admin-email <email>       default: admin@localhost
#   --admin-password <pw>       default: generata (openssl rand)
#   --skip-tls                  installa senza HTTPS (nginx solo :80)
#   --force                     reinstalla anche se DB/utente esistono già
#   -h, --help                  mostra questa guida
#
# Idempotenza: pensato per un host pulito, come da INSTALL.md. Se il ruolo
# Postgres esiste già si ferma (usa --force per procedere comunque, a rischio
# di reinizializzare uno stato esistente).
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "\n${CYAN}▶ $*${NC}"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
die()  { echo -e "${RED}[ERRORE]${NC} $*" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── parametri ────────────────────────────────────────────────────────────────
SERVER_NAME="${FIREDOG_SERVER_NAME:-}"
INSTALL_USER="${FIREDOG_INSTALL_USER:-firedog}"
INSTALL_DIR="${FIREDOG_INSTALL_DIR:-$REPO_ROOT}"
DB_PASSWORD="${FIREDOG_DB_PASSWORD:-}"
ADMIN_USER="${FIREDOG_ADMIN_USER:-admin}"
ADMIN_EMAIL="${FIREDOG_ADMIN_EMAIL:-admin@localhost}"
ADMIN_PASSWORD="${FIREDOG_ADMIN_PASSWORD:-}"
SKIP_TLS="${FIREDOG_SKIP_TLS:-false}"
FORCE=false

while [ $# -gt 0 ]; do
    case "$1" in
        --server-name)    SERVER_NAME="$2"; shift 2 ;;
        --install-user)   INSTALL_USER="$2"; shift 2 ;;
        --install-dir)    INSTALL_DIR="$2"; shift 2 ;;
        --db-password)    DB_PASSWORD="$2"; shift 2 ;;
        --admin-user)     ADMIN_USER="$2"; shift 2 ;;
        --admin-email)    ADMIN_EMAIL="$2"; shift 2 ;;
        --admin-password) ADMIN_PASSWORD="$2"; shift 2 ;;
        --skip-tls)       SKIP_TLS=true; shift ;;
        --force)          FORCE=true; shift ;;
        -h|--help)        sed -n '1,25p' "$0"; exit 0 ;;
        *) die "Argomento sconosciuto: $1 (usa --help)" ;;
    esac
done

[[ $EUID -eq 0 ]] || die "Esegui come root (sudo ./deploy/install.sh)"

DB_NAME="firedog"
DB_USER="firedog"
TLS_DIR="/etc/ssl/firedog"

# ── auto-detect server name (stesso metodo di sentinelcore, funziona offline) ─
if [ -z "$SERVER_NAME" ]; then
    SERVER_NAME="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')"
    [ -z "$SERVER_NAME" ] && SERVER_NAME="$(hostname -I | awk '{print $1}')"
fi
[ -z "$SERVER_NAME" ] && die "Impossibile rilevare l'IP, passa --server-name"

echo "Install dir: $INSTALL_DIR   |   Utente: $INSTALL_USER   |   Server name: $SERVER_NAME   |   TLS: $([ "$SKIP_TLS" = true ] && echo NO || echo 'sì (self-signed)')"

# ── funzioni riusate anche da packaging/appliance/first-boot.sh ─────────────

generate_secret() { openssl rand -hex 32; }

# Escape di un valore per l'uso dentro una stringa SQL a apici singoli
# (es. 'valore'): raddoppia gli apici singoli letterali, come richiede la
# sintassi SQL standard. DB_PASSWORD può arrivare da --db-password/env
# (input umano, non solo dal generatore hex sopra) — senza questo, un apice
# nella password spezzerebbe la stringa e permetterebbe SQL arbitrario nella
# sessione psql (eseguita come superuser postgres).
sql_escape() { printf '%s' "$1" | sed "s/'/''/g"; }

# Scrive backend/.env da .env.example sostituendo i segreti. Idempotente:
# sovrascrive sempre (chi la richiama decide quando chiamarla).
write_env() {
    local secret_key="$1" db_pass="$2" tls_enabled="$3"
    local env_file="$INSTALL_DIR/backend/.env"
    cp "$INSTALL_DIR/backend/.env.example" "$env_file"
    sed -i \
        -e "s#^DEBUG=.*#DEBUG=False#" \
        -e "s#^SECRET_KEY=.*#SECRET_KEY=${secret_key}#" \
        -e "s#^ALLOWED_HOSTS=.*#ALLOWED_HOSTS=${SERVER_NAME},localhost,127.0.0.1#" \
        -e "s#^TLS_ENABLED=.*#TLS_ENABLED=${tls_enabled}#" \
        -e "s#^DB_NAME=.*#DB_NAME=${DB_NAME}#" \
        -e "s#^DB_USER=.*#DB_USER=${DB_USER}#" \
        -e "s#^DB_PASSWORD=.*#DB_PASSWORD=${db_pass}#" \
        -e "s#^CORS_ALLOWED_ORIGINS=.*#CORS_ALLOWED_ORIGINS=https://${SERVER_NAME},http://${SERVER_NAME}#" \
        "$env_file" 2>/dev/null || true
    # CORS_ALLOWED_ORIGINS non è in .env.example di default: aggiungila se assente
    grep -q '^CORS_ALLOWED_ORIGINS=' "$env_file" || \
        echo "CORS_ALLOWED_ORIGINS=https://${SERVER_NAME},http://${SERVER_NAME}" >> "$env_file"
    chmod 600 "$env_file"
    chown "$INSTALL_USER:$INSTALL_USER" "$env_file"
}

# Genera un certificato self-signed per $SERVER_NAME. Rieseguibile: sovrascrive.
generate_tls_cert() {
    mkdir -p "$TLS_DIR"
    local san_type="DNS"
    echo "$SERVER_NAME" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' && san_type="IP"
    openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
        -keyout "$TLS_DIR/firedog.key" -out "$TLS_DIR/firedog.crt" \
        -subj "/CN=$SERVER_NAME" \
        -addext "subjectAltName=$san_type:$SERVER_NAME" >/dev/null 2>&1
    chmod 600 "$TLS_DIR/firedog.key"
    chmod 644 "$TLS_DIR/firedog.crt"
}

# ── 1/9 dipendenze ───────────────────────────────────────────────────────────
log "1/9 Dipendenze di sistema"
apt-get update -qq
apt-get install -y -qq python3-venv build-essential libpq-dev postgresql redis-server nginx openssl arp-scan >/dev/null

# ── 2/9 utente di installazione ──────────────────────────────────────────────
log "2/9 Utente di sistema ($INSTALL_USER)"
if ! id "$INSTALL_USER" >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin "$INSTALL_USER"
else
    warn "Utente $INSTALL_USER già esistente, riuso"
fi
chown -R "$INSTALL_USER:$INSTALL_USER" "$INSTALL_DIR"

# Discovery (backend/discovery/tasks.py) lancia `sudo arp-scan` dal worker
# Celery — arp-scan richiede privilegi raw-socket, il worker gira come
# $INSTALL_USER non privilegiato. NOPASSWD limitato al solo binario
# (path assoluto), validato con visudo prima di attivarlo.
SUDOERS_TMP="$(mktemp)"
sed "s#__FIREDOG_USER__#${INSTALL_USER}#g" "$REPO_ROOT/deploy/sudoers-arp-scan" > "$SUDOERS_TMP"
if visudo -cf "$SUDOERS_TMP" >/dev/null 2>&1; then
    install -m 0440 -o root -g root "$SUDOERS_TMP" /etc/sudoers.d/firedog-arp-scan
else
    warn "Sudoers per arp-scan non valido, salto l'installazione (Discovery andrà configurata a mano)"
fi
rm -f "$SUDOERS_TMP"

# ── 3/9 PostgreSQL ────────────────────────────────────────────────────────────
log "3/9 Database PostgreSQL"
[ -n "$DB_PASSWORD" ] || DB_PASSWORD="$(generate_secret)"
DB_PASSWORD_SQL="$(sql_escape "$DB_PASSWORD")"
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
    [ "$FORCE" = true ] || die "Il ruolo Postgres '$DB_USER' esiste già — usa --force per procedere comunque"
    warn "Ruolo $DB_USER già esistente, sincronizzo la password per --force (così .env resta coerente col DB reale)"
    sudo -u postgres psql -q -c "ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD_SQL}';"
    sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
        sudo -u postgres psql -q -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
else
    sudo -u postgres psql -q <<SQL
CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD_SQL}';
CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
SQL
fi

# ── 4/9 backend ───────────────────────────────────────────────────────────────
log "4/9 Backend (venv + pip + migrazioni)"
cd "$INSTALL_DIR/backend"
sudo -u "$INSTALL_USER" python3 -m venv venv
sudo -u "$INSTALL_USER" venv/bin/pip install -q --upgrade pip
sudo -u "$INSTALL_USER" venv/bin/pip install -q -r requirements.txt

SECRET_KEY="$(generate_secret)"
[ "$SKIP_TLS" = true ] && TLS_ENABLED_VAL=False || TLS_ENABLED_VAL=True
write_env "$SECRET_KEY" "$DB_PASSWORD" "$TLS_ENABLED_VAL"

[ -n "$ADMIN_PASSWORD" ] || ADMIN_PASSWORD="$(generate_secret)"
sudo -u "$INSTALL_USER" venv/bin/python manage.py migrate --noinput
sudo -u "$INSTALL_USER" venv/bin/python manage.py collectstatic --noinput -v0
DJANGO_SUPERUSER_USERNAME="$ADMIN_USER" \
DJANGO_SUPERUSER_EMAIL="$ADMIN_EMAIL" \
DJANGO_SUPERUSER_PASSWORD="$ADMIN_PASSWORD" \
    sudo -E -u "$INSTALL_USER" venv/bin/python manage.py createsuperuser --noinput || \
    warn "createsuperuser fallito (magari l'utente esiste già da un --force)"

sudo -u "$INSTALL_USER" venv/bin/python manage.py check

# ── 5/9 frontend ──────────────────────────────────────────────────────────────
# packaging/build-release.sh spedisce solo frontend/build già compilato (niente
# toolchain Node richiesta sul target finale): se è già presente, salta la
# build e riusa quello. Un checkout git (nessun frontend/build) lo compila qui.
if [ -d "$INSTALL_DIR/frontend/build" ]; then
    log "5/9 Frontend — già compilato nel pacchetto, salto npm ci/build"
else
    log "5/9 Frontend (npm ci + build)"
    cd "$INSTALL_DIR/frontend"
    sudo -u "$INSTALL_USER" npm ci --silent
    sudo -u "$INSTALL_USER" npm run build --silent
fi

# ── 6/9 certificato TLS ───────────────────────────────────────────────────────
if [ "$SKIP_TLS" = false ]; then
    log "6/9 Certificato TLS self-signed"
    generate_tls_cert
else
    log "6/9 Certificato TLS — saltato (--skip-tls)"
fi

# ── 7/9 systemd ───────────────────────────────────────────────────────────────
log "7/9 Unit systemd"
for unit in firedog-backend firedog-celery firedog-celerybeat; do
    sed -e "s#__FIREDOG_USER__#${INSTALL_USER}#g" -e "s#__FIREDOG_DIR__#${INSTALL_DIR}#g" \
        "$REPO_ROOT/deploy/${unit}.service" > "/etc/systemd/system/${unit}.service"
done
systemctl daemon-reload
systemctl enable --now firedog-backend firedog-celery firedog-celerybeat

# ── 8/9 nginx ─────────────────────────────────────────────────────────────────
log "8/9 nginx"
if [ "$SKIP_TLS" = true ]; then
    SRC_CONF="$REPO_ROOT/deploy/nginx-firedog.conf"
else
    SRC_CONF="$REPO_ROOT/deploy/templates/nginx-firedog-https.conf"
fi
sed -e "s#__FIREDOG_SERVER_NAME__#${SERVER_NAME}#g" -e "s#__FIREDOG_DIR__#${INSTALL_DIR}#g" \
    "$SRC_CONF" > /etc/nginx/sites-available/firedog
ln -sf /etc/nginx/sites-available/firedog /etc/nginx/sites-enabled/firedog
rm -f /etc/nginx/sites-enabled/default

# Permessi: nginx (www-data) deve poter attraversare fino a frontend/build e
# staticfiles — gotcha documentato in INSTALL.md.
chmod o+x "$(dirname "$INSTALL_DIR")" "$INSTALL_DIR" 2>/dev/null || true
chmod -R o+rX "$INSTALL_DIR/frontend/build"
chmod -R o+rX "$INSTALL_DIR/backend/staticfiles"

nginx -t
systemctl reload nginx

# ── 9/9 verifica finale ───────────────────────────────────────────────────────
log "9/9 Verifica finale"
sleep 2
for svc in firedog-backend firedog-celery firedog-celerybeat nginx redis-server postgresql; do
    systemctl is-active --quiet "$svc" || warn "$svc non risulta attivo"
done
if [ "$SKIP_TLS" = true ]; then
    CODE="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost/")"
else
    CODE="$(curl -sk -o /dev/null -w '%{http_code}' "https://localhost/")"
fi
[ "$CODE" = "200" ] || warn "Homepage risponde $CODE (atteso 200) — controlla i log dei servizi"

echo -e "\n${GREEN}=== FireDog installato ===${NC}"
[ "$SKIP_TLS" = false ] && echo -e "${YELLOW}Certificato self-signed: il browser avviserà 'connessione non sicura' al primo accesso — è atteso, accetta l'eccezione.${NC}"
echo "URL:            $([ "$SKIP_TLS" = true ] && echo "http://${SERVER_NAME}/" || echo "https://${SERVER_NAME}/")"
echo "Admin:          $ADMIN_USER / $ADMIN_PASSWORD"
echo "DB password:    $DB_PASSWORD"
echo -e "${YELLOW}Annota queste credenziali ora — non verranno ristampate.${NC}"

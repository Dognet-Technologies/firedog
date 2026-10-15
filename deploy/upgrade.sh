#!/usr/bin/env bash
#
# FireDog — upgrade IN-PLACE di un master già installato (tarball o OVA/qcow2
# — stesso meccanismo, sono comunque un host Linux provisionato via
# install.sh/first-boot.sh). Risolve il caso che il bottone "Installa
# aggiornamento" del frontend non può gestire: un'installazione da tarball
# non è un git clone, quindi git pull non è disponibile — vedi
# /api/system/update/check/ in backend/api/views_system.py.
#
# NON copre il caso "sposta i dati su un'appliance NUOVA di zecca" (quella
# resta una procedura pg_dump/pg_restore manuale) — questo script aggiorna
# l'istanza ESISTENTE sul posto.
#
# Uso: sudo ./deploy/upgrade.sh
#      (eseguito dalla RADICE del NUOVO pacchetto estratto, stessa posizione
#      di deploy/install.sh — PKG_DIR risale di un livello dalla posizione
#      dello script, stessa convenzione di REPO_ROOT in deploy/install.sh)
#
# Sequenza: backup DB (pg_dump) → stop servizi → backup artefatti correnti
# (per rollback) → installa nuovo backend+frontend (preserva .env) → venv +
# requirements.txt → migrate col nuovo codice → se fallisce: ripristina gli
# artefatti vecchi e riavvia, NESSUNA modifica silenziosa → se riesce:
# riavvia e verifica.
#
# Non-obiettivo (deliberato, stesso principio di SentinelCore): rollback
# automatico dello SCHEMA. Se il backend non risponde dopo un upgrade
# riuscito, lo schema resta quello nuovo — il backup pg_dump è per un
# ripristino manuale.
set -euo pipefail

# Forza una locale sempre presente: pg_dump/psql su Debian sono wrapper Perl
# che stampano "perl: warning: Setting locale failed" per ogni invocazione
# se il client SSH inoltra LC_* non generate sull'host target — innocuo ma
# seppellisce l'output reale sotto righe di rumore identico.
export LC_ALL=C.UTF-8 LANGUAGE=C.UTF-8

[ "$(id -u)" -eq 0 ] || { echo "Esegui come root (sudo ./upgrade.sh)"; exit 1; }

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${FIREDOG_INSTALL_DIR:-/opt/firedog}"
SVC_USER="${FIREDOG_INSTALL_USER:-firedog}"
BACKUP_DIR="$BASE/backups"
TS="$(date +%Y%m%d-%H%M%S)"

log() { echo -e "\n\033[1;36m▶ $*\033[0m"; }

[ -f "$BASE/backend/manage.py" ] || {
  echo "ERRORE: nessuna installazione esistente trovata in $BASE."
  echo "        Per un primo avvio usa install.sh, non upgrade.sh."
  exit 1
}
[ -f "$PKG_DIR/backend/manage.py" ] || {
  echo "ERRORE: $PKG_DIR non sembra un pacchetto di release valido (manca backend/manage.py)."
  exit 1
}

CURRENT_VERSION="$(cat "$BASE/backend/VERSION" 2>/dev/null || echo sconosciuta)"
NEW_VERSION="$(cat "$PKG_DIR/backend/VERSION" 2>/dev/null || echo sconosciuta)"
echo "Versione installata: $CURRENT_VERSION   →   Nuova: $NEW_VERSION"

ENV_FILE="$BASE/backend/.env"
[ -f "$ENV_FILE" ] || { echo "ERRORE: $ENV_FILE non trovato."; exit 1; }
DB_NAME="$(grep -oP '^DB_NAME=\K.*' "$ENV_FILE")"
DB_USER="$(grep -oP '^DB_USER=\K.*' "$ENV_FILE")"
DB_PASSWORD="$(grep -oP '^DB_PASSWORD=\K.*' "$ENV_FILE")"
DB_HOST="$(grep -oP '^DB_HOST=\K.*' "$ENV_FILE" 2>/dev/null || true)"
DB_HOST="${DB_HOST:-localhost}"
[ -n "$DB_NAME" ] && [ -n "$DB_USER" ] || { echo "ERRORE: impossibile leggere DB_NAME/DB_USER da $ENV_FILE"; exit 1; }

# ── 1. Backup database — rete di sicurezza PRIMA di qualunque modifica ─────
log "1/6 Backup database (pg_dump)"
mkdir -p "$BACKUP_DIR"
DUMP_FILE="$BACKUP_DIR/pre-upgrade-$TS.dump"
PGPASSWORD="$DB_PASSWORD" pg_dump --format=custom -h "$DB_HOST" -U "$DB_USER" -f "$DUMP_FILE" "$DB_NAME" || {
  echo "ERRORE: backup DB fallito — upgrade interrotto, nessuna modifica applicata."
  exit 1
}
echo "Backup salvato in: $DUMP_FILE"

# ── 2. Ferma i servizi ───────────────────────────────────────────────────────
log "2/6 Stop dei servizi"
systemctl stop firedog-backend firedog-celery firedog-celerybeat

# ── 3. Backup artefatti correnti (per rollback se le migration falliscono) ─
log "3/6 Backup artefatti correnti"
ROLLBACK_DIR="$BASE/.upgrade-rollback-$TS"
mkdir -p "$ROLLBACK_DIR"
cp -a "$BASE/backend" "$ROLLBACK_DIR/backend"
cp -a "$BASE/frontend/build" "$ROLLBACK_DIR/frontend-build"

rollback() {
  echo ""
  echo "❌ Migration fallite — ripristino il backend precedente e riavvio i servizi."
  rm -rf "${BASE:?}/backend"
  cp -a "$ROLLBACK_DIR/backend" "$BASE/backend"
  rm -rf "${BASE:?}/frontend/build"
  cp -a "$ROLLBACK_DIR/frontend-build" "$BASE/frontend/build"
  chown -R "$SVC_USER:$SVC_USER" "$BASE/backend" "$BASE/frontend"
  systemctl start firedog-backend firedog-celery firedog-celerybeat
  rm -rf "$ROLLBACK_DIR"
  echo "Servizio precedente ($CURRENT_VERSION) ripristinato e riavviato."
  echo "Le migration girano in transazione: il DB non dovrebbe aver subito modifiche"
  echo "parziali, ma il backup pre-upgrade resta disponibile per sicurezza:"
  echo "  $DUMP_FILE"
  exit 1
}

# ── 4. Installa i nuovi artefatti (preserva .env: segreti, DB, TLS) ─────────
log "4/6 Installazione nuovi artefatti"
NEW_BACKEND_TMP="$BASE/.new-backend-$TS"
cp -a "$PKG_DIR/backend" "$NEW_BACKEND_TMP"
cp "$ENV_FILE" "$NEW_BACKEND_TMP/.env"
rm -rf "${BASE:?}/backend"
mv "$NEW_BACKEND_TMP" "$BASE/backend"

rm -rf "${BASE:?}/frontend/build"
cp -a "$PKG_DIR/frontend/build" "$BASE/frontend/build"
# nginx (www-data) deve poter attraversare fino a frontend/build e leggerne i file.
chmod -R o+rX "$BASE/frontend/build"

# Il tarball di release non porta un venv (gitignored, vedi build-release.sh):
# va creato da zero per il backend appena copiato, non "aggiornato" — quello
# vecchio è stato eliminato insieme al resto di backend/ sopra (sopravvive
# solo nel backup di rollback).
sudo -u "$SVC_USER" python3 -m venv "$BASE/backend/venv"
sudo -u "$SVC_USER" "$BASE/backend/venv/bin/pip" install -q --upgrade pip
sudo -u "$SVC_USER" "$BASE/backend/venv/bin/pip" install -q -r "$BASE/backend/requirements.txt"

# systemd unit possono cambiare fra versioni (timeout, nuove ExecStart) — NON
# toccano .env, segreti o certificati TLS. Stessi placeholder di install.sh.
for svc in firedog-backend firedog-celery firedog-celerybeat; do
  if [ -f "$PKG_DIR/deploy/$svc.service" ]; then
    sed -e "s#__FIREDOG_USER__#$SVC_USER#g" -e "s#__FIREDOG_DIR__#$BASE#g" \
      "$PKG_DIR/deploy/$svc.service" > "/etc/systemd/system/$svc.service"
  fi
done
systemctl daemon-reload

chown -R "$SVC_USER:$SVC_USER" "$BASE/backend" "$BASE/frontend"

# ── 5. Applica le migration pendenti col NUOVO codice ───────────────────────
log "5/6 Applicazione migration"
(cd "$BASE/backend" && sudo -u "$SVC_USER" venv/bin/python manage.py migrate --noinput) || rollback
(cd "$BASE/backend" && sudo -u "$SVC_USER" venv/bin/python manage.py collectstatic --noinput -v0) 2>/dev/null || true
rm -rf "$ROLLBACK_DIR"

# ── 6. Riavvia e verifica ────────────────────────────────────────────────────
log "6/6 Riavvio e verifica"
systemctl start firedog-backend firedog-celery firedog-celerybeat
set +e
for i in $(seq 1 60); do
  # /api/token/ accetta solo POST: 405 = Daphne+Django rispondono davvero
  # (stesso check già usato da packaging/appliance/first-boot.sh).
  CODE="$(curl -sk -o /dev/null -w '%{http_code}' https://127.0.0.1/api/token/ 2>/dev/null)"
  [ "$CODE" = "405" ] && break
  sleep 1
done
set -e

if [ "$CODE" = "405" ]; then
  cat <<EOF

────────────────────────────────────────────────────────────────────
 ✅ Aggiornamento completato: $CURRENT_VERSION → $NEW_VERSION
   Backup DB pre-upgrade: $DUMP_FILE
   Servizi: systemctl status firedog-backend firedog-celery firedog-celerybeat
────────────────────────────────────────────────────────────────────
EOF
else
  cat <<EOF

⚠️  Il backend non risponde correttamente dopo l'aggiornamento (http=$CODE).
    Lo schema è già stato aggiornato e NON viene ripristinato automaticamente
    (rollback dello schema fuori scope, stesso principio di SentinelCore —
    solo il backup manuale lo copre).
    Controlla i log:  journalctl -u firedog-backend -n 100 --no-pager
    Backup DB pre-upgrade per un ripristino manuale: $DUMP_FILE
EOF
  exit 1
fi

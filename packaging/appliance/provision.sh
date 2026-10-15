#!/usr/bin/env bash
#
# Eseguito DENTRO la VM di build da cloud-init.
# Scarica il tarball di release dal build host (via QEMU NAT 10.0.2.2),
# estrae DIRETTAMENTE nella posizione finale /opt/firedog (niente copia
# successiva: deploy/install.sh di FireDog lavora in-place sulla directory
# in cui si trova, a differenza del modello "stage in /tmp poi copia" di
# SentinelCore), esegue install.sh, poi installa il servizio di first-boot
# per i cloni futuri.
#
# Variabili richieste (passate dall'environment o da /tmp/build-env.sh):
#   TARBALL_NAME  — es. firedog-v1.1.0-linux-x86_64.tar.gz
#   HTTP_BASE     — es. http://10.0.2.2:18081
set -euo pipefail

LOG=/var/log/firedog-provision.log
exec > >(tee -a "$LOG") 2>&1
echo "[provision] $(date '+%Y-%m-%d %H:%M:%S') avvio"

: "${TARBALL_NAME:?TARBALL_NAME non impostato}"
: "${HTTP_BASE:?HTTP_BASE non impostato}"

INSTALL_DIR="/opt/firedog"

# ── 1. Scarica ed estrae direttamente in /opt/firedog ───────────────────────
echo "[provision] Download: $HTTP_BASE/dist/$TARBALL_NAME"
wget -q --tries=5 --timeout=120 \
    "$HTTP_BASE/dist/$TARBALL_NAME" -O "/tmp/$TARBALL_NAME"

echo "[provision] Estrazione in $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
tar xzf "/tmp/$TARBALL_NAME" -C "$INSTALL_DIR" --strip-components=1

# ── 2. Installa FireDog con credenziali appliance fisse ──────────────────────
echo "[provision] Esecuzione deploy/install.sh..."
chmod +x "$INSTALL_DIR/deploy/install.sh"
export FIREDOG_INSTALL_DIR="$INSTALL_DIR"
export FIREDOG_INSTALL_USER="firedog"
export FIREDOG_ADMIN_USER="admin"
export FIREDOG_ADMIN_EMAIL="admin@localhost"
export FIREDOG_ADMIN_PASSWORD="FireDog2026!!"
# server-name/DB-password lasciati vuoti: auto-rilevato/generato da
# install.sh. first-boot.sh li rigenera comunque ad ogni clone.
"$INSTALL_DIR/deploy/install.sh"

# ── 3. Installa il first-boot service ───────────────────────────────────────
echo "[provision] Installazione firedog-first-boot..."

wget -q "$HTTP_BASE/packaging/appliance/first-boot.sh" \
    -O "$INSTALL_DIR/deploy/first-boot.sh"
chmod 755 "$INSTALL_DIR/deploy/first-boot.sh"
chown firedog:firedog "$INSTALL_DIR/deploy/first-boot.sh"

wget -q "$HTTP_BASE/packaging/appliance/firedog-first-boot.service" \
    -O /etc/systemd/system/firedog-first-boot.service
systemctl daemon-reload
systemctl enable firedog-first-boot.service

# ── 4. Ferma i servizi prima di esportare (snapshot pulito) ──────────────────
echo "[provision] Stop servizi prima dell'export..."
systemctl stop firedog-backend firedog-celery firedog-celerybeat 2>/dev/null || true
systemctl stop postgresql 2>/dev/null || true

# ── 5. Configurazione persistente (sopravvive a cloud-init clean) ───────────
echo "[provision] Configurazione rete e accesso iniziale..."

mkdir -p /etc/systemd/network
cat > /etc/systemd/network/10-dhcp.network << 'NETCFG'
[Match]
Name=en*

[Network]
DHCP=yes
DNS=1.1.1.1
NETCFG
systemctl enable systemd-networkd
systemctl enable systemd-resolved 2>/dev/null || true

# Stesso gotcha già affrontato per SentinelCore: la cloud image Debian
# abilita serial-getty@ttyS0 di default, ma su hypervisor "headless"
# (VirtualBox/QEMU via OVA/qcow2 importati) spesso non c'è un backend UART
# reale — agetty fallisce in loop infinito intasando i log. Accesso comunque
# garantito via rete (SSH/HTTPS).
systemctl mask serial-getty@ttyS0.service

# Password root fissa e documentata — first-boot.sh NON la ruota (rigenera
# solo DB password/SECRET_KEY/certificato TLS), resta finché l'operatore
# non la cambia. La scadenza forzata (chage -d 0) va impostata da
# first-boot.sh stesso come ultimo passo, non qui — vedi il commento in
# quello script per il motivo (deadlock PAM/sudo).
echo 'root:FireDog1st!' | chpasswd
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# ── 6. Pulizia pre-export: generico per ogni clone ───────────────────────────
echo "[provision] Pulizia per export..."
truncate -s 0 /etc/machine-id
rm -f /etc/ssh/ssh_host_*_key /etc/ssh/ssh_host_*_key.pub
rm -f "/tmp/$TARBALL_NAME"
apt-get clean -qq 2>/dev/null || true
cloud-init clean --logs 2>/dev/null || true

echo "[provision] $(date '+%Y-%m-%d %H:%M:%S') completato — poweroff"

# $LOG (vedi riga 17, exec > >(tee -a "$LOG")) contiene la DB_PASSWORD di
# build, superata dalla rotazione di first-boot.sh ma comunque un segreto
# che non ha senso spedire dentro ogni immagine. rm sull'inode ancora aperto
# dal tee è sicuro: il contenuto resta scrivibile via il fd esistente ma
# senza più un percorso che lo referenzi — sparisce per davvero quando il
# processo (questo script, a poweroff) chiude il descriptor.
rm -f "$LOG"

sync
poweroff -f

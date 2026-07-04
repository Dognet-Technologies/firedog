#!/bin/bash
#
# FireDog target install script
#
# Base dir layout (all management/config lives under /opt/sentinelsuite/firedog):
#
#   /opt/sentinelsuite/firedog/
#     ├── bin/                 firewall-manager, traffic-analyzer, firewall-init.sh
#     ├── conf/                ulogd.conf, custom_rules.conf.example, firedog-cron,
#     │                        firewall-fm.service, firewall-pcap-logrotate,
#     │                        apparmor-firewall-manager
#     ├── data/                runtime data (traffic-analyzer / firewall-manager outputs)
#     ├── logs/                application logs
#     ├── rules/               iptables backups
#     └── export/              manual CLI exports (legacy, agent now pushes via WS)
#
# System-level files (required by OS daemons) are symlinked back to this tree:
#   /usr/local/bin/firewall-manager   -> /opt/sentinelsuite/firedog/bin/firewall-manager
#   /usr/local/bin/traffic-analyzer   -> /opt/sentinelsuite/firedog/bin/traffic-analyzer
#   /usr/local/sbin/firewall-init.sh  -> /opt/sentinelsuite/firedog/bin/firewall-init.sh
#   /etc/ulogd.conf                   -> /opt/sentinelsuite/firedog/conf/ulogd.conf
#   /etc/logrotate.d/firewall-pcap    -> /opt/sentinelsuite/firedog/conf/firewall-pcap-logrotate
#   /etc/systemd/system/firewall-fm.service
#                                     -> /opt/sentinelsuite/firedog/conf/firewall-fm.service
#   /etc/cron.d/firedog               -> /opt/sentinelsuite/firedog/conf/firedog-cron (if microcyber)
#   /etc/apparmor.d/usr.local.bin.firewall-manager
#                                     -> /opt/sentinelsuite/firedog/conf/apparmor-firewall-manager
#
# /etc/firewall/{iptables.rules,custom_rules.conf} stay where the firewall-fm.service
# unit expects them (kernel/iptables side).
#
# The new Rust dog-agent installs separately via its own .deb under /usr/bin/dog-agent
# and talks to the master over WebSocket — there is no SSH pull anymore.
#
# Usage:  sudo ./install.sh [--skip-init]
#

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

SKIP_INIT=false
for arg in "$@"; do
    case "$arg" in
        --skip-init) SKIP_INIT=true ;;
        -h|--help)   sed -n '1,40p' "$0"; exit 0 ;;
        *) echo "Unknown arg: $arg"; exit 2 ;;
    esac
done

[[ $EUID -eq 0 ]] || { echo -e "${RED}[ERROR]${NC} root required"; exit 1; }
grep -Eiq 'debian|ubuntu' /etc/os-release || { echo -e "${YELLOW}[WARN]${NC} non-Debian system, aborting"; exit 1; }

BASE_DIR="/opt/sentinelsuite/firedog"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${GREEN}== FireDog target install ==${NC} base=${BASE_DIR}"

# ── 1/7 packages ─────────────────────────────────────────────────────────────
echo -e "${GREEN}[1/7]${NC} apt deps"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq iptables iptables-persistent ulogd2 python3 tcpdump logrotate

# ── 2/7 directory tree ───────────────────────────────────────────────────────
echo -e "${GREEN}[2/7]${NC} tree ${BASE_DIR}"
install -d -m 0755 "${BASE_DIR}"/{bin,conf,data,logs,rules,export}
install -d -m 0700 /etc/firewall
install -d -m 0700 /var/lib/firewall
install -d -m 0755 /var/log/firedog
if id microcyber &>/dev/null; then
    chown -R microcyber:microcyber "${BASE_DIR}"/{data,logs,rules,export}
fi

# ── 3/7 binaries -> /opt + symlinks under /usr/local ─────────────────────────
echo -e "${GREEN}[3/7]${NC} binaries"
install -m 0755 "${SCRIPT_DIR}/firewall-manager.py" "${BASE_DIR}/bin/firewall-manager"
install -m 0755 "${SCRIPT_DIR}/traffic-analyzer.py" "${BASE_DIR}/bin/traffic-analyzer"
install -m 0755 "${SCRIPT_DIR}/firewall-init.sh"    "${BASE_DIR}/bin/firewall-init.sh"
ln -sfn "${BASE_DIR}/bin/firewall-manager" /usr/local/bin/firewall-manager
ln -sfn "${BASE_DIR}/bin/traffic-analyzer" /usr/local/bin/traffic-analyzer
ln -sfn "${BASE_DIR}/bin/firewall-init.sh" /usr/local/sbin/firewall-init.sh

# ── 4/7 configs -> /opt + symlinks where OS daemons read them ────────────────
echo -e "${GREEN}[4/7]${NC} configs"
install -m 0644 "${SCRIPT_DIR}/file_config/ulogd.conf"                "${BASE_DIR}/conf/ulogd.conf"
install -m 0644 "${SCRIPT_DIR}/file_config/firewall-pcap-logrotate"   "${BASE_DIR}/conf/firewall-pcap-logrotate"
install -m 0644 "${SCRIPT_DIR}/file_config/custom_rules.conf.example" "${BASE_DIR}/conf/custom_rules.conf.example"
install -m 0644 "${SCRIPT_DIR}/file_config/firedog-cron"              "${BASE_DIR}/conf/firedog-cron"
install -m 0644 "${SCRIPT_DIR}/firewall.service"                      "${BASE_DIR}/conf/firewall-fm.service"
install -m 0644 "${SCRIPT_DIR}/apparmor-firewall-manager"             "${BASE_DIR}/conf/apparmor-firewall-manager"

# Backup pre-existing /etc/ulogd.conf if not already a symlink to our tree
if [[ -f /etc/ulogd.conf && ! -L /etc/ulogd.conf ]]; then
    cp /etc/ulogd.conf "/etc/ulogd.conf.bak.$(date +%s)"
fi
ln -sfn "${BASE_DIR}/conf/ulogd.conf"              /etc/ulogd.conf
ln -sfn "${BASE_DIR}/conf/firewall-pcap-logrotate" /etc/logrotate.d/firewall-pcap
ln -sfn "${BASE_DIR}/conf/firewall-fm.service"     /etc/systemd/system/firewall-fm.service
install -d -m 0750 -o root -g adm /var/log/ulogd

# /etc/firewall/custom_rules.conf seed (only on first install)
[[ -f /etc/firewall/custom_rules.conf ]] || \
    install -m 0644 "${BASE_DIR}/conf/custom_rules.conf.example" /etc/firewall/custom_rules.conf

systemctl daemon-reload
systemctl enable --now ulogd2

# ── 5/7 cron (only if microcyber exists) ─────────────────────────────────────
echo -e "${GREEN}[5/7]${NC} cron"
if id microcyber &>/dev/null; then
    ln -sfn "${BASE_DIR}/conf/firedog-cron" /etc/cron.d/firedog
    chmod 0644 "${BASE_DIR}/conf/firedog-cron"
else
    echo -e "${YELLOW}  [skip]${NC} microcyber missing, firedog-cron not linked"
fi

# ── 6/7 AppArmor (best-effort) ──────────────────────────────────────────────
echo -e "${GREEN}[6/7]${NC} apparmor (best-effort)"
if command -v apparmor_parser &>/dev/null; then
    ln -sfn "${BASE_DIR}/conf/apparmor-firewall-manager" /etc/apparmor.d/usr.local.bin.firewall-manager
    apparmor_parser -r /etc/apparmor.d/usr.local.bin.firewall-manager 2>/dev/null || \
        echo -e "${YELLOW}  [warn]${NC} apparmor reload failed (non-fatal)"
else
    echo -e "${YELLOW}  [skip]${NC} apparmor not present"
fi

# ── 7/7 init firewall (interactive) ─────────────────────────────────────────
if $SKIP_INIT; then
    echo -e "${YELLOW}[7/7]${NC} --skip-init: firewall NOT activated"
    echo -e "${CYAN}      run: sudo firewall-init.sh && systemctl enable --now firewall-fm${NC}"
else
    echo -e "${GREEN}[7/7]${NC} firewall init"
    echo -e "${YELLOW}      policy DROP will be applied. ensure console/serial access.${NC}"
    read -rp "      proceed? (yes/no): " confirm
    if [[ "$confirm" == "yes" ]]; then
        /usr/local/sbin/firewall-init.sh
        systemctl enable --now firewall-fm
    else
        echo -e "${YELLOW}      skipped. activate later: systemctl enable --now firewall-fm${NC}"
    fi
fi

echo
echo -e "${GREEN}== done ==${NC}"
echo "  base dir:       ${BASE_DIR}"
echo "  CLI:            firewall-manager --help"
echo "  firewall svc:   systemctl status firewall-fm"
echo "  custom rules:   /etc/firewall/custom_rules.conf"
echo "  pcap logs:      /var/log/ulogd/"

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
# Supported distros: Debian/Ubuntu (apt) and openSUSE/SLES (zypper).
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

# ── distro detection (debian family / suse family) ──────────────────────────
[[ -r /etc/os-release ]] || { echo -e "${RED}[ERROR]${NC} /etc/os-release missing"; exit 1; }
. /etc/os-release
OS_FAMILY=""
for os_id in ${ID:-} ${ID_LIKE:-}; do
    case "$os_id" in
        debian|ubuntu)          OS_FAMILY="debian"; break ;;
        *suse*|sles)            OS_FAMILY="suse";   break ;;
    esac
done
[[ -n "$OS_FAMILY" ]] || {
    echo -e "${YELLOW}[WARN]${NC} unsupported distro '${ID:-?}' (supported: Debian/Ubuntu, openSUSE/SLES), aborting"
    exit 1
}

BASE_DIR="/opt/sentinelsuite/firedog"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${GREEN}== FireDog target install ==${NC} base=${BASE_DIR} distro=${ID:-?} (${OS_FAMILY})"

# ── 1/7 packages ─────────────────────────────────────────────────────────────
if [[ "$OS_FAMILY" == "debian" ]]; then
    echo -e "${GREEN}[1/7]${NC} apt deps"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq iptables iptables-persistent ipset ulogd2 python3 tcpdump logrotate cron
else
    echo -e "${GREEN}[1/7]${NC} zypper deps"
    zypper --non-interactive --quiet refresh
    # no iptables-persistent on SUSE: boot persistence is handled by firewall-fm.service
    # util-linux-systemd: provides `logger`, used by the firedog-cron jobs
    zypper --non-interactive install --no-recommends \
        iptables ipset python3 tcpdump logrotate cronie curl util-linux-systemd
    # ulogd lives in the security:netfilter OBS repo on Leap/SLES (not in the
    # main repos); there the pcap output plugin is a separate subpackage
    install_ulogd() {
        zypper --non-interactive install --no-recommends ulogd ulogd-pcap 2>/dev/null || \
        zypper --non-interactive install --no-recommends ulogd2 2>/dev/null
    }
    if ! install_ulogd; then
        for obs_target in "${VERSION_ID:-}" "openSUSE_Leap_${VERSION_ID:-}" "openSUSE_Tumbleweed"; do
            [[ -n "$obs_target" ]] || continue
            repo_url="https://download.opensuse.org/repositories/security:/netfilter/${obs_target}/security:netfilter.repo"
            if curl -fsI "$repo_url" &>/dev/null; then
                echo -e "${CYAN}  [info]${NC} adding OBS repo security:netfilter (${obs_target}) for ulogd"
                zypper --non-interactive addrepo -f "$repo_url" 2>/dev/null || true
                zypper --non-interactive --gpg-auto-import-keys refresh
                break
            fi
        done
        install_ulogd || {
            echo -e "${RED}[ERROR]${NC} ulogd package not found (security:netfilter repo unavailable for this release)"; exit 1;
        }
    fi
    # cron.d support needs the cron daemon running (not enabled by default on SUSE)
    systemctl enable --now cron
fi

# resolve ulogd unit name (ulogd2.service on Debian, ulogd.service on SUSE)
ULOGD_SVC="ulogd2"
systemctl cat ulogd2.service &>/dev/null || \
    { systemctl cat ulogd.service &>/dev/null && ULOGD_SVC="ulogd"; }

# firewalld conflicts with the raw-iptables setup (openSUSE enables it by default)
FIREWALLD_ACTIVE=false
if systemctl is-active --quiet firewalld 2>/dev/null; then
    FIREWALLD_ACTIVE=true
    echo -e "${YELLOW}  [warn]${NC} firewalld is active: it will be disabled when the FireDog firewall is activated"
fi

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
# ulogd.conf ships with Debian multiarch plugin paths: rewrite them to the
# plugin dir that actually exists on this system (SUSE uses /usr/lib64/ulogd)
for plugin_dir in /usr/lib/x86_64-linux-gnu/ulogd /usr/lib64/ulogd /usr/lib/ulogd; do
    if [[ -e "${plugin_dir}/ulogd_inppkt_NFLOG.so" ]]; then
        sed -i "s|/usr/lib/x86_64-linux-gnu/ulogd|${plugin_dir}|g" "${BASE_DIR}/conf/ulogd.conf"
        break
    fi
done
install -m 0644 "${SCRIPT_DIR}/file_config/firewall-pcap-logrotate"   "${BASE_DIR}/conf/firewall-pcap-logrotate"
install -m 0644 "${SCRIPT_DIR}/file_config/custom_rules.conf.example" "${BASE_DIR}/conf/custom_rules.conf.example"
install -m 0644 "${SCRIPT_DIR}/file_config/firedog.conf.example"      "${BASE_DIR}/conf/firedog.conf.example"
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
# adm group does not exist on every SUSE install: fall back to root
LOG_GRP="root"; getent group adm &>/dev/null && LOG_GRP="adm"
install -d -m 0750 -o root -g "$LOG_GRP" /var/log/ulogd

# /etc/firewall/custom_rules.conf seed (only on first install)
[[ -f /etc/firewall/custom_rules.conf ]] || \
    install -m 0644 "${BASE_DIR}/conf/custom_rules.conf.example" /etc/firewall/custom_rules.conf

# /etc/firewall/firedog.conf seed (only on first install): MONITORED_INTERFACES
# + ALWAYS_OPEN_PORTS. Va valorizzato PRIMA di firewall-init.sh se il target
# espone servizi che altrimenti resterebbero irraggiungibili sotto la policy
# DROP finale (oltre a SSH, già protetto a parte).
[[ -f /etc/firewall/firedog.conf ]] || \
    install -m 0644 "${BASE_DIR}/conf/firedog.conf.example" /etc/firewall/firedog.conf

systemctl daemon-reload
systemctl enable --now "$ULOGD_SVC"

# ── 5/7 cron ───────────────────────────────────────────────────────────────
# I job in firedog-cron girano come root (non serve più microcyber): senza
# questo, l'export status.json non viene mai generato e Target.firedog_version
# resta vuoto anche su target agent-based perfettamente funzionanti (Method B
# non crea l'utente microcyber, quindi prima di questo fix il link veniva
# sempre skippato su quel percorso di installazione).
echo -e "${GREEN}[5/7]${NC} cron"
ln -sfn "${BASE_DIR}/conf/firedog-cron" /etc/cron.d/firedog
chmod 0644 "${BASE_DIR}/conf/firedog-cron"

# ── 6/7 AppArmor (best-effort) ──────────────────────────────────────────────
# the parser alone is not enough: the kernel must have AppArmor active
# (e.g. openSUSE Leap 16 ships apparmor_parser but runs SELinux by default)
echo -e "${GREEN}[6/7]${NC} apparmor (best-effort)"
if command -v apparmor_parser &>/dev/null && [[ -d /sys/kernel/security/apparmor ]]; then
    ln -sfn "${BASE_DIR}/conf/apparmor-firewall-manager" /etc/apparmor.d/usr.local.bin.firewall-manager
    apparmor_parser -r /etc/apparmor.d/usr.local.bin.firewall-manager 2>/dev/null || \
        echo -e "${YELLOW}  [warn]${NC} apparmor reload failed (non-fatal)"
else
    echo -e "${YELLOW}  [skip]${NC} apparmor not present"
fi

# ── 7/7 init firewall (interactive) ─────────────────────────────────────────
if $SKIP_INIT; then
    echo -e "${YELLOW}[7/7]${NC} --skip-init: firewall NOT activated"
    if $FIREWALLD_ACTIVE; then
        echo -e "${CYAN}      run: sudo systemctl disable --now firewalld${NC}"
    fi
    echo -e "${CYAN}      run: sudo firewall-init.sh && systemctl enable --now firewall-fm${NC}"
else
    echo -e "${GREEN}[7/7]${NC} firewall init"
    echo -e "${YELLOW}      policy DROP will be applied. ensure console/serial access.${NC}"
    if $FIREWALLD_ACTIVE; then
        echo -e "${YELLOW}      firewalld will be disabled and replaced by firewall-fm.${NC}"
    fi
    read -rp "      proceed? (yes/no): " confirm
    if [[ "$confirm" == "yes" ]]; then
        if $FIREWALLD_ACTIVE; then
            systemctl disable --now firewalld
        fi
        # enable before init: if the session dies in the DROP window (remote
        # installs) the unit is already registered for the next boot
        systemctl enable firewall-fm
        /usr/local/sbin/firewall-init.sh
        systemctl start firewall-fm
    else
        echo -e "${YELLOW}      skipped. activate later: systemctl enable --now firewall-fm${NC}"
    fi
fi

echo
echo -e "${GREEN}== done ==${NC}"
echo "  base dir:       ${BASE_DIR}"
echo "  CLI:            firewall-manager --help"
echo "  firewall svc:   systemctl status firewall-fm"
echo "  ulogd svc:      systemctl status ${ULOGD_SVC}"
echo "  custom rules:   /etc/firewall/custom_rules.conf"
echo "  firedog conf:   /etc/firewall/firedog.conf (NIC monitorate, porte sempre aperte, ban SSH brute-force)"
echo "  pcap logs:      /var/log/ulogd/"

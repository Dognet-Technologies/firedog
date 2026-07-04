#!/bin/bash
#
# FireDog target bootstrap installer.
#
# Installa gli strumenti firewall del target (/opt/sentinelsuite/firedog)
# scaricando firedog-package dal repo GitHub:
#
#   curl -fsSL https://raw.githubusercontent.com/Dognet-Technologies/firedog/develop-v0.0.6/firedog-package/get-firedog.sh | sudo bash
#
# Opzioni di install.sh (dopo "-s --"):
#   curl -fsSL .../get-firedog.sh | sudo bash -s -- --skip-init
#
# Variabili d'ambiente:
#   FIREDOG_REF   branch o tag da installare (default: develop-v0.0.6)
#
# NOTA: questo script installa SOLO gli strumenti firewall del target.
# Il dog-agent (heartbeat/pairing col master) si installa separatamente
# con il suo pacchetto .deb — vedi INSTALL-TARGET.md.
#
set -euo pipefail

REPO="Dognet-Technologies/firedog"
REF="${FIREDOG_REF:-develop-v0.0.6}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[get-firedog]${NC} $*"; }
warn() { echo -e "${YELLOW}[get-firedog]${NC} $*"; }
die()  { echo -e "${RED}[get-firedog]${NC} $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "serve root: rilancia con sudo"
command -v curl >/dev/null || die "curl mancante (apt install curl)"
command -v tar  >/dev/null || die "tar mancante"

WORKDIR="$(mktemp -d /tmp/firedog-install.XXXXXX)"
trap 'rm -rf "${WORKDIR}"' EXIT
cd "${WORKDIR}"

# ── 1. scarica il tarball del ref (branch, poi tag) ──────────────────────────
info "scarico ${REPO}@${REF}"
curl -fsSL -o src.tar.gz "https://codeload.github.com/${REPO}/tar.gz/refs/heads/${REF}" \
    || curl -fsSL -o src.tar.gz "https://codeload.github.com/${REPO}/tar.gz/refs/tags/${REF}" \
    || die "download di ${REPO}@${REF} fallito"

tar xzf src.tar.gz --wildcards "*/firedog-package/*"
PKG_DIR="$(find "${WORKDIR}" -maxdepth 2 -type d -name firedog-package | head -1)"
[[ -n "${PKG_DIR}" && -f "${PKG_DIR}/install.sh" ]] || die "install.sh non trovato nel pacchetto"
chmod +x "${PKG_DIR}/install.sh"

# ── 2. esegui l'installer ────────────────────────────────────────────────────
# In pipe (curl | bash) stdin non è un tty: la conferma interattiva di
# attivazione firewall leggerebbe EOF. Riaggancia /dev/tty se disponibile,
# altrimenti forza --skip-init (mai policy DROP senza conferma esplicita).
args=("$@")
if [[ ! -t 0 ]]; then
    if [[ -r /dev/tty ]]; then
        info "eseguo install.sh ${args[*]:-} (input da /dev/tty)"
        bash "${PKG_DIR}/install.sh" "${args[@]}" < /dev/tty
        exit $?
    fi
    case " ${args[*]:-} " in
        *" --skip-init "*) : ;;
        *) warn "nessun tty: aggiungo --skip-init (attiva poi con: sudo firewall-init.sh)"
           args+=("--skip-init") ;;
    esac
fi
info "eseguo install.sh ${args[*]:-}"
bash "${PKG_DIR}/install.sh" "${args[@]}"

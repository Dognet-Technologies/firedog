#!/bin/bash
#
# FireDog target bootstrap installer.
#
# Installa gli strumenti firewall (/opt/sentinelsuite/firedog) e il dog-agent
# su un target Debian/Ubuntu scaricando il pacchetto da GitHub:
#
#   curl -fsSL https://raw.githubusercontent.com/Dognet-Technologies/firedog/develop-v0.0.6/firedog-package/get-firedog.sh | sudo bash
#
# Opzioni (passate a install.sh dopo "-s --"):
#   curl -fsSL .../get-firedog.sh | sudo bash -s -- --skip-init
#
# Variabili d'ambiente:
#   FIREDOG_RELEASE  tag della release da cui scaricare il pacchetto completo
#                    (default: ultima release con asset firedog-package.tar.gz)
#   FIREDOG_REF      branch/tag di fallback per il solo codice, senza binario
#                    dog-agent (default: develop-v0.0.6)
#
# Il pacchetto completo (strumenti + binario dog-agent) vive negli asset delle
# GitHub Release: il binario dell'agent non è versionato nel repo.
#
set -euo pipefail

REPO="Dognet-Technologies/firedog"
ASSET="firedog-package.tar.gz"
REF="${FIREDOG_REF:-develop-v0.0.6}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[get-firedog]${NC} $*"; }
warn()  { echo -e "${YELLOW}[get-firedog]${NC} $*"; }
die()   { echo -e "${RED}[get-firedog]${NC} $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "serve root: rilancia con sudo"
command -v curl >/dev/null || die "curl mancante (apt install curl)"
command -v tar  >/dev/null || die "tar mancante"

WORKDIR="$(mktemp -d /tmp/firedog-install.XXXXXX)"
trap 'rm -rf "${WORKDIR}"' EXIT
cd "${WORKDIR}"

# ── 1. individua l'URL del pacchetto ─────────────────────────────────────────
asset_url=""
if [[ -n "${FIREDOG_RELEASE:-}" ]]; then
    api="https://api.github.com/repos/${REPO}/releases/tags/${FIREDOG_RELEASE}"
else
    api="https://api.github.com/repos/${REPO}/releases"
fi

# Primo browser_download_url che termina con l'asset atteso
asset_url="$(curl -fsSL "${api}" 2>/dev/null \
    | grep -oE '"browser_download_url": *"[^"]+"' \
    | grep -oE 'https://[^"]+' \
    | grep "/${ASSET}$" | head -1 || true)"

# ── 2. scarica ed estrae ─────────────────────────────────────────────────────
if [[ -n "${asset_url}" ]]; then
    info "scarico pacchetto completo: ${asset_url}"
    curl -fSL -o "${ASSET}" "${asset_url}"
    tar xzf "${ASSET}"
    PKG_DIR="${WORKDIR}/firedog-package"
else
    warn "nessuna release con ${ASSET}: fallback sul ref '${REF}' (SENZA binario dog-agent)"
    warn "l'agent andrà installato dal master (push via UI) o da una release futura"
    curl -fSL -o src.tar.gz "https://codeload.github.com/${REPO}/tar.gz/refs/heads/${REF}" \
        || curl -fSL -o src.tar.gz "https://codeload.github.com/${REPO}/tar.gz/refs/tags/${REF}" \
        || die "download di ${REPO}@${REF} fallito"
    tar xzf src.tar.gz --wildcards "*/firedog-package/*"
    PKG_DIR="$(find "${WORKDIR}" -maxdepth 2 -type d -name firedog-package | head -1)"
fi

[[ -f "${PKG_DIR}/install.sh" ]] || die "install.sh non trovato nel pacchetto"
chmod +x "${PKG_DIR}/install.sh"

# ── 3. esegui l'installer vero e proprio ─────────────────────────────────────
# Se lo script è arrivato via pipe (curl | bash) stdin non è un tty: l'init
# interattivo del firewall leggerebbe EOF. In quel caso riaggancia /dev/tty
# se disponibile, altrimenti forza --skip-init.
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

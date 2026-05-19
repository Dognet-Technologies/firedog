#!/usr/bin/env bash
# update.sh — FireDog master-side update script.
#
# Pulls latest code from origin, rebuilds the React frontend, applies
# backend dependencies + migrations, restarts daphne + celery.
#
# Usage:
#   ./update.sh           # apply latest commits of the configured branch
#   ./update.sh --check   # only report installed vs available, no changes
#
# Sui target NON gira nulla: l'agent si aggiorna distribuendo il binario
# tramite firedog-package/ in un flusso separato.
#
# Prerequisites on master:
#   - the install directory MUST be a git clone of the repo
#   - microcyber must have NOPASSWD sudo for:
#       /bin/systemctl restart firedog-backend
#       /bin/systemctl restart firedog-celery
#     (see /etc/sudoers.d/microcyber-firedog-update)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRANCH="${UPDATE_BRANCH:-frontend-restyling}"
BACKEND_DIR="$REPO_DIR/backend"
FRONTEND_DIR="$REPO_DIR/frontend"
VENV="$BACKEND_DIR/venv"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}  $*"; }
warn() { echo -e "${YELLOW}[!!]${NC}  $*"; }
fail() { echo -e "${RED}[KO]${NC}  $*"; exit 1; }
step() { echo -e "\n${YELLOW}──────${NC} $* ${YELLOW}──────${NC}"; }

[[ -d "$REPO_DIR/.git" ]] || fail "$REPO_DIR non è un git clone (re-init con: git init && git remote add origin … && git fetch && git reset --hard origin/$BRANCH)"
command -v git >/dev/null  || fail "git non trovato"
command -v node >/dev/null || fail "node non trovato"
command -v npm >/dev/null  || fail "npm non trovato"

# ── --check mode ─────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--check" ]]; then
    step "Check updates ($BRANCH)"
    git -C "$REPO_DIR" fetch origin "$BRANCH" --quiet
    LOCAL=$(git -C "$REPO_DIR" rev-parse HEAD)
    REMOTE=$(git -C "$REPO_DIR" rev-parse "origin/$BRANCH")
    AHEAD=$(git -C "$REPO_DIR" rev-list --count "$LOCAL..$REMOTE")
    echo "  installed : $(git -C "$REPO_DIR" rev-parse --short HEAD)"
    echo "  available : $(git -C "$REPO_DIR" rev-parse --short "origin/$BRANCH")"
    echo "  behind    : $AHEAD commit(s)"
    if [[ "$AHEAD" == "0" ]]; then ok "Already up to date"; else warn "$AHEAD update(s) disponibili"; fi
    exit 0
fi

step "FireDog update ($BRANCH)"
cd "$REPO_DIR"

# ── step 1: git pull (saving conflict-prone local edits if any) ─────────────
step "Step 1/5 — git pull"
git fetch origin "$BRANCH" --quiet
LOCAL_DIRTY=$(git status --porcelain | grep -vE '^\?\?' | wc -l)
if [[ "$LOCAL_DIRTY" -gt 0 ]]; then
    warn "Working tree non pulito; faccio stash automatico"
    git stash push -m "auto-stash before update $(date +%s)" >/dev/null
fi
git checkout "$BRANCH" --quiet
git pull --ff-only origin "$BRANCH" && ok "Codice aggiornato" || fail "git pull (non fast-forward?) — risolvi a mano"

# ── step 2: frontend deps + build ───────────────────────────────────────────
step "Step 2/5 — frontend build"
cd "$FRONTEND_DIR"
# npm install solo se package-lock.json è cambiato (vs node_modules/.package-lock.json)
NEEDS_NPM_INSTALL=1
if [[ -f node_modules/.package-lock.json ]] && cmp -s package-lock.json node_modules/.package-lock.json; then
    NEEDS_NPM_INSTALL=0
fi
if [[ $NEEDS_NPM_INSTALL -eq 1 ]]; then
    npm ci --no-audit --no-fund && ok "npm deps OK" || fail "npm ci fallito"
else
    ok "npm deps invariate, skip"
fi
npm run build 2>&1 | tail -5
[[ -f build/static/js/main.*.js ]] || true
ok "Frontend rebuild OK"

# ── step 3: backend deps (se requirements.txt è cambiato) ───────────────────
step "Step 3/5 — backend deps"
cd "$BACKEND_DIR"
[[ -d "$VENV" ]] || fail "venv non trovato in $VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
if git diff --name-only "HEAD@{1}" HEAD -- requirements.txt 2>/dev/null | grep -q requirements.txt; then
    pip install -q -r requirements.txt && ok "pip OK" || fail "pip install fallito"
else
    ok "requirements.txt invariato, skip"
fi

# ── step 4: migrations ──────────────────────────────────────────────────────
step "Step 4/5 — migrate"
python manage.py migrate --noinput 2>&1 | tail -10
ok "Migrazioni applicate"

# ── step 5: restart services ────────────────────────────────────────────────
step "Step 5/5 — restart services"
sudo -n /bin/systemctl restart firedog-backend && ok "firedog-backend ✓" || fail "restart backend fallito"
sudo -n /bin/systemctl restart firedog-celery  && ok "firedog-celery ✓"  || warn "restart celery fallito (non bloccante)"

deactivate || true

step "Done"
echo "  commit: $(git -C "$REPO_DIR" rev-parse --short HEAD)  ($(git -C "$REPO_DIR" log -1 --format='%s' HEAD | head -c 80))"

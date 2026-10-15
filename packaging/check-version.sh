#!/usr/bin/env bash
#
# Gate della release: il tag git deve coincidere con la versione dichiarata
# nel codice del master (backend/VERSION, fonte unica — vedi settings.py
# FIREDOG_VERSION). Un tag che diverge produrrebbe un pacchetto che si
# presenta con un'altra versione nel footer/API (/api/system/version/).
#
# Non controlla firedog-package/VERSION: quella è la versione del pacchetto
# TARGET (firewall-manager/firewall-init.sh), aggiornata con un processo
# indipendente — la release qui è del master, non del pacchetto target.
#
# Uso:  packaging/check-version.sh vX.Y.Z[-suffisso]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAG="${1:?uso: check-version.sh <tag>}"

# SemVer con suffisso opzionale: v1.0.2, v1.1.0-beta, v1.1.0-rc.1
if [[ ! "$TAG" =~ ^v([0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?)$ ]]; then
  echo "ERRORE: tag '$TAG' non e' nel formato vX.Y.Z[-suffisso]" >&2
  exit 1
fi
EXPECTED="${BASH_REMATCH[1]}"

BACKEND_VERSION="$(cat "$REPO_ROOT/backend/VERSION" 2>/dev/null | tr -d '[:space:]')"
FRONTEND_VERSION="$(sed -n 's/^  "version": "\(.*\)",/\1/p' "$REPO_ROOT/frontend/package.json" | head -1)"

fail=0
check() {
  local label="$1" value="$2"
  if [ "$value" = "$EXPECTED" ]; then
    printf '  ok   %-28s %s\n' "$label" "$value"
  else
    printf '  FAIL %-28s %s (atteso %s)\n' "$label" "${value:-<vuoto>}" "$EXPECTED" >&2
    fail=1
  fi
}

echo "Tag: $TAG  ->  versione attesa: $EXPECTED"
check "backend/VERSION"       "$BACKEND_VERSION"
check "frontend/package.json" "$FRONTEND_VERSION"

if [ "$fail" -ne 0 ]; then
  echo "ERRORE: versioni nel codice non allineate al tag." >&2
  exit 1
fi
echo "Versioni coerenti."

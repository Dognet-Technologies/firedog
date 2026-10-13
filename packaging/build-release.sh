#!/usr/bin/env bash
#
# Costruisce il pacchetto di release: build del frontend, staging del
# sorgente backend (Django non compila) e assembla un tarball versionato
# auto-installante (backend + frontend/build + deploy/ + INSTALL.md).
#
# Uso:  packaging/build-release.sh [versione]
#       (versione default = git describe, es. v1.1.0-beta)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="${1:-$(git describe --tags --always 2>/dev/null || echo v0.0.0)}"
ARCH="linux-x86_64"
NAME="firedog-${VERSION}-${ARCH}"
OUT="$REPO_ROOT/dist"
STAGE="$OUT/$NAME"

echo "▶ Release: $NAME"
rm -rf "$STAGE"; mkdir -p "$STAGE"

# ── frontend ──────────────────────────────────────────────────────────────
echo "▶ Build frontend (npm run build)"
( cd frontend && npm ci --no-audit --no-fund --silent && CI=false GENERATE_SOURCEMAP=false npm run build --silent )
mkdir -p "$STAGE/frontend"
cp -a frontend/build "$STAGE/frontend/build"

# ── backend (sorgente, nessun compile step per Django) ───────────────────
echo "▶ Staging backend"
mkdir -p "$STAGE/backend"
# Lista file da `git ls-files` (tracciati + non tracciati ma non ignorati)
# invece di un elenco --exclude= mantenuto a mano: prende il contenuto reale
# del working tree (comprese modifiche non ancora committate — workflow
# normale di questo repo, si builda senza commit prima) ma si ferma da solo
# a qualunque cosa .gitignore già esclude (venv/.env/staticfiles/__pycache__/
# *.log/backend/logs/*), senza bisogno di tenere una seconda lista
# sincronizzata a mano che può disallinearsi da .gitignore nel tempo.
( cd backend && git ls-files --cached --others --exclude-standard -z ) \
    | tar -C backend --null -T - -c | tar -C "$STAGE/backend" -x

# ── deploy + install.sh + INSTALL.md ──────────────────────────────────────
echo "▶ Assemblaggio artefatti"
cp -a deploy "$STAGE/deploy"
[ -f INSTALL.md ] && cp INSTALL.md "$STAGE/INSTALL.md" || true
echo "$VERSION" > "$STAGE/VERSION"

# ── tarball + checksum + firma GPG ──────────────────────────────────────────
echo "▶ Tarball + checksum + firma"
mkdir -p "$OUT"
( cd "$OUT" && tar czf "$NAME.tar.gz" "$NAME" )
( cd "$OUT" && sha256sum "$NAME.tar.gz" > "$NAME.tar.gz.sha256" )
if gpg --list-secret-keys >/dev/null 2>&1; then
    ( cd "$OUT" && gpg --armor --detach-sign --output "$NAME.tar.gz.asc" "$NAME.tar.gz" ) \
        && echo "  firma: $NAME.tar.gz.asc"
else
    echo "  (nessuna chiave GPG sul build host: firma saltata)"
fi

rm -rf "$STAGE"
echo "▶ Fatto:"
ls -lh "$OUT/$NAME".tar.gz* | sed 's#.*/##'
echo "Artefatti in: $OUT/"

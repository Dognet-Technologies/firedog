"""System-level endpoints: update from GitHub."""

from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path

from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminUser

logger = logging.getLogger("firedog.system_update")

# Risale dal BASE_DIR (backend/) alla root del repo (dove vive update.sh + .git/)
REPO_ROOT = Path(getattr(settings, "BASE_DIR", Path(__file__).resolve().parents[2])).parent
UPDATE_SCRIPT = REPO_ROOT / "update.sh"


def _run(cmd: list[str], cwd: Path | str | None = None, timeout: int = 30) -> tuple[int, str, str]:
    """Thin wrapper su subprocess.run con default safe + truncate output."""
    try:
        p = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", f"timeout after {timeout}s"
    except FileNotFoundError as e:
        return 127, "", f"comando non trovato: {e}"


class SystemUpdateCheckView(APIView):
    """GET /api/system/update/check/ — versione corrente vs disponibile su GitHub."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (REPO_ROOT / ".git").exists():
            return Response(
                {
                    "ok": False,
                    "error": (
                        "Il path di installazione non è un git clone — l'update "
                        "automatico richiede che il repo sia gestito con git. "
                        f"Path: {REPO_ROOT}"
                    ),
                },
                status=200,
            )

        # `git fetch` per portare i ref di origin a livello locale, senza modificare working tree.
        rc, _, err = _run(["git", "fetch", "origin", "--quiet"], cwd=REPO_ROOT, timeout=30)
        if rc != 0:
            logger.warning("git fetch failed: %s", err)
            return Response({"ok": False, "error": f"git fetch fallito: {err.strip() or rc}"}, status=200)

        # branch corrente
        rc, branch, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT)
        branch = branch.strip() or "HEAD"

        rc, local_sha, _ = _run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT)
        rc, remote_sha, _ = _run(["git", "rev-parse", f"origin/{branch}"], cwd=REPO_ROOT)
        rc, ahead_str, _ = _run(
            ["git", "rev-list", "--count", f"{local_sha.strip()}..{remote_sha.strip()}"],
            cwd=REPO_ROOT,
        )
        try:
            ahead = int(ahead_str.strip() or 0)
        except ValueError:
            ahead = 0

        rc, local_summary, _ = _run(["git", "log", "-1", "--format=%h %s (%ar)"], cwd=REPO_ROOT)
        rc, remote_summary, _ = _run(
            ["git", "log", "-1", "--format=%h %s (%ar)", f"origin/{branch}"], cwd=REPO_ROOT
        )

        # Lista dei commit nuovi (max 20 righe)
        rc, log_diff, _ = _run(
            [
                "git",
                "log",
                "--no-merges",
                "--pretty=format:%h %s (%an, %ar)",
                "-n",
                "20",
                f"{local_sha.strip()}..{remote_sha.strip()}",
            ],
            cwd=REPO_ROOT,
        )

        return Response(
            {
                "ok": True,
                "branch": branch,
                "installed": local_summary.strip(),
                "available": remote_summary.strip(),
                "commits_behind": ahead,
                "changelog": [line for line in log_diff.splitlines() if line.strip()],
                "up_to_date": ahead == 0,
                "update_script": str(UPDATE_SCRIPT),
            }
        )


class SystemUpdateInstallView(APIView):
    """POST /api/system/update/install/ — esegue update.sh.

    Richiede privilegi admin. Esegue lo script sincrono e ritorna stdout/stderr
    (truncated). Per output streaming useremo Server-Sent Events in V2.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        if not UPDATE_SCRIPT.exists():
            return Response({"ok": False, "error": f"update.sh non trovato in {UPDATE_SCRIPT}"}, status=500)
        if not (REPO_ROOT / ".git").exists():
            return Response(
                {"ok": False, "error": "Repo non gestito con git: re-inizializzalo prima."},
                status=500,
            )

        logger.info("System update triggered by user=%s", getattr(request.user, "username", "?"))

        # Timeout generoso (5 min): npm ci può essere lento. Stiamo eseguendo sul master.
        rc, stdout, stderr = _run(["bash", str(UPDATE_SCRIPT)], cwd=REPO_ROOT, timeout=600)

        # Trim output a ultimi ~8 KB per non far esplodere la response.
        def tail(s: str, n: int = 8192) -> str:
            return s if len(s) <= n else "…\n" + s[-n:]

        ok = rc == 0
        # Estrai un messaggio operativo dallo stderr (o ultime righe stdout)
        # così la UI può mostrarlo subito invece di un generico "Errore di rete".
        if not ok:
            error_msg = (stderr.strip().splitlines() or [""])[-1]
            if not error_msg:
                # cerca pattern [KO] / [ERROR] / "fail" nelle ultime righe stdout
                tail_lines = [l for l in stdout.splitlines() if l.strip()][-5:]
                error_msg = next(
                    (l for l in tail_lines if any(t in l for t in ("[KO]", "[ERROR]", "fail", "error"))),
                    tail_lines[-1] if tail_lines else f"update.sh exit {rc}",
                )
        else:
            error_msg = None

        return Response(
            {
                "ok": ok,
                "exit_code": rc,
                "stdout": tail(stdout),
                "stderr": tail(stderr),
                "error": error_msg,
                "command": shlex.join(["bash", str(UPDATE_SCRIPT)]),
            },
            status=200 if ok else 500,
        )

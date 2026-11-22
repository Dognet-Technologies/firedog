#!/usr/bin/env bash
#
# Toglie le credenziali iniziali da motd e console appena microcyber cambia la
# password: da quel momento sarebbero false. Attivato da
# firedog-clear-credentials.path a ogni modifica di /etc/shadow.
set -euo pipefail

SSH_USER="microcyber"

# Campo lastchg a 0: cambio password ancora da fare (vedi first-boot.sh).
[ "$(getent shadow "$SSH_USER" | cut -d: -f3)" != "0" ] || exit 0

URL_LINE="$(grep -m1 'URL:' /etc/motd || true)"
rm -f /etc/issue.d/firedog.issue
cat > /etc/motd <<MOTD

  FireDog — SentinelSuite
$URL_LINE

MOTD

systemctl disable firedog-clear-credentials.path

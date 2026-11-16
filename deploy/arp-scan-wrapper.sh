#!/bin/bash
# Installato da deploy/install.sh / upgrade.sh come
# /usr/local/lib/firedog/arp-scan-wrapper (root:root 0755).
#
# Il worker Celery della Discovery (backend/discovery/tasks.py) lo lancia
# via sudo. Prima il sudoers autorizzava /usr/sbin/arp-scan con QUALUNQUE
# argomento: arp-scan ha opzioni che leggono e scrivono file arbitrari
# (es. --writepkttofile, --ouifile), quindi chi comprometteva l'utente di
# servizio poteva scrivere file come root. Qui si accetta solo una rete
# IPv4 in notazione CIDR.
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "uso: $0 <rete IPv4 CIDR>" >&2
    exit 2
fi

octet='(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])'
cidr_re="^${octet}\.${octet}\.${octet}\.${octet}/([0-9]|[12][0-9]|3[0-2])$"
if ! [[ "$1" =~ $cidr_re ]]; then
    echo "rete non valida: $1" >&2
    exit 2
fi

exec /usr/sbin/arp-scan "$1"

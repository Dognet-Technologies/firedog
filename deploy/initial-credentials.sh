#!/usr/bin/env bash
#
# Credenziali iniziali dell'admin web, fuori da qualsiasi log.
# Script condiviso della SentinelSuite: tenerlo identico in tutti i repo.
#
#   save  <dir> <database> <tabella> <colonna-hash> <utente>   (password su stdin)
#         Scrive <dir>/initial-credentials (root, 600) e l'impronta dell'hash
#         attuale della password, senza stampare nulla.
#   check <dir> <timer>
#         Se l'hash in database non e' piu' quello iniziale (password cambiata o
#         utente rimosso) cancella il file e spegne il timer che lo invoca.
#
# Tabella e colonna arrivano solo dagli installer; l'utente passa a psql come
# variabile (:'u'), mai concatenato nella query.
set -euo pipefail

STATE_NAME="initial-credentials.state"
CREDS_NAME="initial-credentials"

current_fingerprint() {
    local db="$1" table="$2" column="$3" user="$4" hash
    hash="$(printf "SELECT %s FROM %s WHERE username = :'u';\n" "$column" "$table" \
        | runuser -u postgres -- psql -X -q -tA -v ON_ERROR_STOP=1 -v u="$user" -d "$db")" \
        || return 1
    printf '%s' "$hash" | sha256sum | cut -d' ' -f1
}

cmd_save() {
    [ $# -eq 5 ] || { echo "uso: $0 save <dir> <db> <tabella> <colonna> <utente>" >&2; exit 2; }
    local dir="$1" db="$2" table="$3" column="$4" user="$5" password fp
    IFS= read -r password
    [ -n "$password" ] || { echo "password vuota su stdin" >&2; exit 2; }
    fp="$(current_fingerprint "$db" "$table" "$column" "$user")"

    install -d -m 0700 -o root -g root "$dir"
    (
        umask 077
        cat > "$dir/$CREDS_NAME" <<EOF
# Credenziali iniziali dell'amministratore web.
# Il file si cancella da solo appena la password viene cambiata.
Utente:   $user
Password: $password
EOF
        printf '%s %s %s %s %s\n' "$user" "$db" "$table" "$column" "$fp" > "$dir/$STATE_NAME"
    )
}

cmd_check() {
    [ $# -eq 2 ] || { echo "uso: $0 check <dir> <timer>" >&2; exit 2; }
    local dir="$1" timer="$2" user db table column initial current
    if [ -f "$dir/$STATE_NAME" ] && [ -f "$dir/$CREDS_NAME" ]; then
        read -r user db table column initial < "$dir/$STATE_NAME"
        if ! current="$(current_fingerprint "$db" "$table" "$column" "$user")"; then
            echo "database non raggiungibile, riprovo al prossimo giro" >&2
            exit 0
        fi
        [ "$current" != "$initial" ] || exit 0
        echo "password iniziale cambiata: rimuovo $dir/$CREDS_NAME"
    fi
    rm -f "$dir/$CREDS_NAME" "$dir/$STATE_NAME"
    systemctl disable --now "$timer" >/dev/null 2>&1 || true
}

case "${1:-}" in
    save)  shift; cmd_save "$@" ;;
    check) shift; cmd_check "$@" ;;
    *)     echo "uso: $0 save|check ..." >&2; exit 2 ;;
esac

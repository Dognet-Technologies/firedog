#!/bin/bash
#
# FireDog SSH Gateway - Forced Commands Wrapper
# Questo script viene eseguito quando un client SSH si connette con forced commands
# Implementa whitelist di comandi permessi per sicurezza
#
# Setup in authorized_keys:
# command="/usr/local/bin/firedog-ssh-gateway.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding ssh-rsa AAAA...
#

set -euo pipefail

# Logging
LOG_FILE="/var/log/firedog/ssh-gateway.log"
mkdir -p /var/log/firedog
touch "$LOG_FILE"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [USER:${USER:-unknown}] [IP:${SSH_CLIENT%% *}] $1" >> "$LOG_FILE"
}

# Funzione per sanitizzare input (previene injection)
sanitize() {
    local input="$1"
    # Rimuovi caratteri pericolosi: ; & | ` $ ( ) < > \ " '
    echo "$input" | sed 's/[;&|`$()<>\\"\x27]//g'
}

# Comando ricevuto via SSH (SSH_ORIGINAL_COMMAND è settato da sshd)
ORIGINAL_CMD="${SSH_ORIGINAL_COMMAND:-}"

# Se nessun comando, nega accesso
if [[ -z "$ORIGINAL_CMD" ]]; then
    log "DENIED: No command specified (interactive shell attempt)"
    echo "ERROR: Interactive shell not allowed. Use SSH command execution only."
    exit 1
fi

log "REQUEST: $ORIGINAL_CMD"

# ========== WHITELIST COMANDI PERMESSI ==========

# Pattern matching per comandi permessi
case "$ORIGINAL_CMD" in
    # ========== READ-ONLY COMMANDS (no password) ==========

    "sudo iptables -L"*)
        log "ALLOW: iptables list"
        exec sudo /usr/sbin/iptables -L -n -v
        ;;

    "sudo iptables -S"*)
        log "ALLOW: iptables specification"
        exec sudo /usr/sbin/iptables -S
        ;;

    "sudo iptables-save")
        log "ALLOW: iptables-save"
        exec sudo /usr/sbin/iptables-save
        ;;

    "sudo firewall-manager --list"*)
        log "ALLOW: firewall-manager --list"
        exec sudo /usr/local/bin/firewall-manager --list
        ;;

    "sudo firewall-manager --stats"*)
        log "ALLOW: firewall-manager --stats"
        exec sudo /usr/local/bin/firewall-manager --stats
        ;;

    "sudo firewall-manager --export-json"*)
        # Valida path (solo /opt/firedog/export/*.json)
        if [[ "$ORIGINAL_CMD" =~ ^sudo\ firewall-manager\ --export-json\ (/opt/firedog/export/[a-zA-Z0-9_-]+\.json)$ ]]; then
            OUTPUT_PATH="${BASH_REMATCH[1]}"
            log "ALLOW: firewall-manager --export-json $OUTPUT_PATH"
            exec sudo /usr/local/bin/firewall-manager --export-json "$OUTPUT_PATH"
        else
            log "DENIED: Invalid export path: $ORIGINAL_CMD"
            echo "ERROR: Export path must be /opt/firedog/export/*.json"
            exit 1
        fi
        ;;

    "sudo firewall-manager --threats"*)
        log "ALLOW: firewall-manager --threats"
        exec sudo /usr/local/bin/firewall-manager --threats
        ;;

    "sudo firewall-manager --analyze"*)
        # Valida parametro numerico (ore)
        if [[ "$ORIGINAL_CMD" =~ ^sudo\ firewall-manager\ --analyze\ ([0-9]+)$ ]]; then
            HOURS="${BASH_REMATCH[1]}"
            log "ALLOW: firewall-manager --analyze $HOURS"
            exec sudo /usr/local/bin/firewall-manager --analyze "$HOURS"
        else
            log "DENIED: Invalid analyze parameter: $ORIGINAL_CMD"
            echo "ERROR: --analyze requires numeric hours parameter"
            exit 1
        fi
        ;;

    "sudo traffic-analyzer"*)
        # Permetti traffic-analyzer con qualsiasi argomento (già validato dallo script stesso)
        log "ALLOW: traffic-analyzer"
        exec sudo /usr/local/bin/traffic-analyzer ${ORIGINAL_CMD#sudo traffic-analyzer }
        ;;

    "sudo systemctl status firedog"*)
        log "ALLOW: systemctl status firedog"
        exec sudo /bin/systemctl status firedog
        ;;

    "sudo systemctl restart firedog"*)
        log "ALLOW: systemctl restart firedog"
        exec sudo /bin/systemctl restart firedog
        ;;

    "sudo systemctl reload firedog"*)
        log "ALLOW: systemctl reload firedog"
        exec sudo /bin/systemctl reload firedog
        ;;

    # ========== WRITE COMMANDS (require password) ==========
    # Questi comandi richiedono password, validazione più stretta

    "sudo firewall-manager --add-input"*)
        # Parsing: --add-input PORT PROTOCOL [--source IP] [--comment "text"]
        if [[ "$ORIGINAL_CMD" =~ ^sudo\ firewall-manager\ --add-input\ ([0-9]+)\ (tcp|udp) ]]; then
            PORT="${BASH_REMATCH[1]}"
            PROTOCOL="${BASH_REMATCH[2]}"

            # Valida porta (1-65535)
            if [[ $PORT -lt 1 || $PORT -gt 65535 ]]; then
                log "DENIED: Invalid port: $PORT"
                echo "ERROR: Port must be between 1 and 65535"
                exit 1
            fi

            log "ALLOW (password required): firewall-manager --add-input $PORT $PROTOCOL"
            # Questo richiederà password perché sudoers non ha NOPASSWD per --add-input
            exec sudo /usr/local/bin/firewall-manager --add-input "$PORT" "$PROTOCOL"
        else
            log "DENIED: Invalid --add-input syntax: $ORIGINAL_CMD"
            echo "ERROR: Usage: sudo firewall-manager --add-input PORT PROTOCOL"
            exit 1
        fi
        ;;

    "sudo firewall-manager --add-output"*)
        # Stessa logica di add-input
        if [[ "$ORIGINAL_CMD" =~ ^sudo\ firewall-manager\ --add-output\ ([0-9]+)\ (tcp|udp) ]]; then
            PORT="${BASH_REMATCH[1]}"
            PROTOCOL="${BASH_REMATCH[2]}"

            if [[ $PORT -lt 1 || $PORT -gt 65535 ]]; then
                log "DENIED: Invalid port: $PORT"
                echo "ERROR: Port must be between 1 and 65535"
                exit 1
            fi

            log "ALLOW (password required): firewall-manager --add-output $PORT $PROTOCOL"
            exec sudo /usr/local/bin/firewall-manager --add-output "$PORT" "$PROTOCOL"
        else
            log "DENIED: Invalid --add-output syntax: $ORIGINAL_CMD"
            echo "ERROR: Usage: sudo firewall-manager --add-output PORT PROTOCOL"
            exit 1
        fi
        ;;

    "sudo firewall-manager --delete"*)
        # Parsing: --delete CHAIN RULE_NUMBER
        if [[ "$ORIGINAL_CMD" =~ ^sudo\ firewall-manager\ --delete\ (INPUT|OUTPUT|FORWARD)\ ([0-9]+)$ ]]; then
            CHAIN="${BASH_REMATCH[1]}"
            RULE_NUM="${BASH_REMATCH[2]}"

            log "ALLOW (password required): firewall-manager --delete $CHAIN $RULE_NUM"
            exec sudo /usr/local/bin/firewall-manager --delete "$CHAIN" "$RULE_NUM"
        else
            log "DENIED: Invalid --delete syntax: $ORIGINAL_CMD"
            echo "ERROR: Usage: sudo firewall-manager --delete CHAIN RULE_NUMBER"
            exit 1
        fi
        ;;

    # ========== FILE TRANSFER (SCP/SFTP) ==========
    # Permetti SCP pull di file JSON esportati

    "scp"*)
        # SCP è gestito internamente da sshd, non passa da qui
        log "INFO: SCP request (handled by sshd)"
        ;;

    # ========== DEFAULT: DENY ==========

    *)
        log "DENIED: Command not in whitelist: $ORIGINAL_CMD"
        echo "ERROR: Command not allowed: $ORIGINAL_CMD"
        echo ""
        echo "Allowed commands:"
        echo "  sudo iptables -L"
        echo "  sudo iptables -S"
        echo "  sudo iptables-save"
        echo "  sudo firewall-manager --list"
        echo "  sudo firewall-manager --stats"
        echo "  sudo firewall-manager --export-json /opt/firedog/export/FILE.json"
        echo "  sudo firewall-manager --threats"
        echo "  sudo firewall-manager --analyze HOURS"
        echo "  sudo traffic-analyzer [args]"
        echo "  sudo systemctl status|restart|reload firedog"
        echo ""
        echo "Write commands (require password):"
        echo "  sudo firewall-manager --add-input PORT PROTOCOL"
        echo "  sudo firewall-manager --add-output PORT PROTOCOL"
        echo "  sudo firewall-manager --delete CHAIN RULE_NUMBER"
        exit 1
        ;;
esac

# Non dovrebbe mai arrivare qui
log "ERROR: Unexpected exit point"
exit 1

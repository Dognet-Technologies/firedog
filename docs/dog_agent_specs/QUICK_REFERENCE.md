# QUICK REFERENCE

## Parametri Chiave

### Identity Hash
```python
# Formato: ip+hostname+mac (NO delimitatori)
identity_text = f"{ip_address}{hostname}{mac_address}"
# Esempio: "192.168.0.15webserverAA:BB:CC:DD:EE:FF"
identity_hash = hashlib.sha512(identity_text.encode()).hexdigest()
```

### API Key
- **Globale**: Una sola per tutti gli agent
- **Storage**: SHA512 hash nel database
- **Generazione**: `secrets.token_urlsafe(48)` (64 caratteri)

### Timeout & Intervals
- **Pairing timeout**: 3 minuti
- **Heartbeat interval**: 30 secondi (default)
- **Health check**: Ogni 2 minuti
- **Offline threshold**: 2 minuti senza heartbeat

### Threat Scoring
- **Threshold default**: 75
- **Classification**:
  - CRITICAL: score >= 80
  - HIGH: 60-79
  - MEDIUM: 40-59
  - LOW: 20-39

### File Paths (Agent)
- **Config**: `/etc/dog-agent/agent.conf`
- **Logs**: `/opt/sentinelsuite/firedog/log/`
- **Agent code**: `/opt/sentinelsuite/firedog/`
- **PCAP input**: `/var/log/ulogd/input_dropped.pcap`
- **PCAP output**: `/var/log/ulogd/output_dropped.pcap`

## WebSocket Messages

### Agent → Server
```json
// Pairing
{"type": "pair_request", "api_key": "...", "ip": "...", "hostname": "...", "mac": "..."}

// Heartbeat
{"type": "heartbeat", "timestamp": "...", "system_stats": {...}}

// Threat Log
{"type": "threat_log", "threats": [{...}]}

// Command Response
{"type": "command_response", "command_id": "...", "status": "success"}
```

### Server → Agent
```json
// Pairing Status
{"type": "pairing_status", "status": "success", "phase_1_verified": true}

// Command
{"type": "command", "command_id": "...", "action": "add_rule", "payload": {...}}

// Config
{"type": "config", "config": {...}}
```

## Command Actions
- `add_rule`: Aggiunge regola firewall
- `remove_rule`: Rimuove regola
- `sync_rules`: Sincronizza tutte le regole
- `block_ip`: Blocca IP
- `unblock_ip`: Sblocca IP
- `update_config`: Aggiorna configurazione
- `check_integrity`: Verifica integrità file

## Database Models

### AgentAPIKey
- `key_hash`: SHA512 dell'API key
- `is_active`: Solo una attiva alla volta
- `expires_at`: NULL = mai scade

### PairingSession
- `status`: waiting, verifying_api, verifying_hash, success, failed, expired
- `phase_1_verified`: API key OK
- `phase_2_verified`: Identity hash OK
- `expires_at`: created_at + 3 minuti

### AgentConnection
- `websocket_channel`: Django Channels channel name
- `is_online`: Aggiornato da heartbeat
- `last_heartbeat`: Timestamp ultimo heartbeat
- `system_info`: JSONB con statistiche sistema

### AgentCommand
- `status`: pending, sent, executing, success, failed, timeout
- `command_id`: UUID univoco
- `action`: Tipo comando
- `payload`: JSONB parametri
- `timeout_seconds`: Default 30

## Installation Commands

### Server
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Generate API key
python manage.py shell
>>> from agent_manager.views import AgentAPIKeyViewSet
>>> # Use /api/agent/api-keys/generate/ endpoint

# Start services
gunicorn firedog_backend.wsgi:application
daphne firedog_backend.asgi:application
celery -A firedog_backend worker
celery -A firedog_backend beat
```

### Agent
```bash
# Install package
sudo dpkg -i dog-agent_1.0.0_amd64.deb
sudo apt-get -f install

# Configure
sudo nano /etc/dog-agent/agent.conf

# Start service
sudo systemctl start dog-agent
sudo systemctl status dog-agent

# View logs
sudo journalctl -u dog-agent -f
```

## Security Checklist

- [ ] HTTPS con certificato valido
- [ ] API key in chmod 600
- [ ] JWT secret strong
- [ ] Rate limiting abilitato
- [ ] Audit logging attivo
- [ ] Firewall configurato
- [ ] SSL certificate verification abilitato
- [ ] Database backups schedulati

## Testing Quick Commands

```bash
# Backend tests
python manage.py test agent_manager

# Agent tests
cd /opt/sentinelsuite/firedog
python -m pytest tests/

# Integration test
# 1. Create target in UI
# 2. Start pairing
# 3. Start agent: sudo systemctl start dog-agent
# 4. Check pairing success in UI
# 5. Send test command
# 6. Verify in agent logs
```

## Troubleshooting

### Agent non si connette
```bash
# Check config
sudo cat /etc/dog-agent/agent.conf

# Check logs
sudo journalctl -u dog-agent -n 50

# Test connectivity
curl https://firedog-server.com/api/health

# Check firewall
sudo iptables -L -n | grep OUTPUT
```

### Pairing timeout
- Verifica API key corretta
- Controlla ip/hostname/mac sul server
- Verifica timeout non scaduto (3 minuti)
- Controlla logs agent per errori

### Heartbeat non arriva
- Verifica agent online: `systemctl status dog-agent`
- Controlla WebSocket connection nei logs
- Verifica network connectivity
- Check server Celery beat running

## File Structure Reference

```
firedog_backend/
├── agent_manager/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── consumers.py
│   ├── routing.py
│   ├── tasks.py
│   └── tests/

dog-agent/
├── dog_agent.py
├── config_manager.py
├── websocket_client.py
├── firewall_manager.py
├── threat_detector.py
├── system_monitor.py
├── integrity_monitor.py
└── requirements.txt
```

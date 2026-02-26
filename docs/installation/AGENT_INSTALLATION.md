# Installazione FireDog Agent

Guida completa per l'installazione del Dog Agent sui sistemi target (Debian/Ubuntu).

## Requisiti di Sistema

### Sistemi Supportati
- Debian 11 (Bullseye)
- Debian 12 (Bookworm)
- Ubuntu 20.04 LTS
- Ubuntu 22.04 LTS
- Ubuntu 24.04 LTS

### Requisiti Hardware
- **CPU**: 1 core
- **RAM**: 512 MB
- **Disk**: 100 MB spazio libero
- **Network**: Connessione al server FireDog

### Permessi
- Accesso **root** o **sudo** per l'installazione
- L'agent verrà eseguito come servizio systemd

---

## 1. Prerequisiti

### 1.1 Installazione Python 3.9+

```bash
# Verifica versione Python (deve essere >= 3.9)
python3 --version

# Se Python non è installato o versione < 3.9
apt update
apt install -y python3 python3-pip python3-venv
```

### 1.2 Installazione Dipendenze Sistema

```bash
apt update
apt install -y \
    python3-dev \
    build-essential \
    curl \
    iptables \
    systemd
```

---

## 2. Installazione Agent

### Metodo 1: Installazione da Package (Raccomandato)

```bash
# Scarica il package wheel dal server FireDog
# (sostituisci con l'URL del tuo server)
curl -O http://firedog-server/packages/dog-agent-latest-py3-none-any.whl

# Installa il package
pip3 install dog-agent-latest-py3-none-any.whl

# Verifica installazione
dog-agent --version
```

### Metodo 2: Installazione da Sorgenti

```bash
# Scarica il codice sorgente
cd /tmp
git clone https://github.com/Dognet-Technologies/firedog.git
cd firedog/firedog-package

# Build del package
python3 -m pip install build
python3 -m build

# Installa
pip3 install dist/dog_agent-*.whl

# Verifica installazione
dog-agent --version
```

### Metodo 3: Installazione Manuale (Sviluppo)

```bash
# Crea directory installazione
mkdir -p /opt/dog-agent
cd /opt/dog-agent

# Copia i file dell'agent
# dog-agent/
#   ├── dog_agent.py
#   ├── config_manager.py
#   ├── websocket_client.py
#   ├── system_monitor.py
#   ├── threat_detector.py
#   └── firewall_manager.py

# Installa dipendenze
pip3 install websockets psutil cryptography pyyaml
```

---

## 3. Configurazione Agent

### 3.1 Creazione Directory Configurazione

```bash
# Crea directory configurazione
mkdir -p /etc/dog-agent
mkdir -p /var/log/dog-agent
mkdir -p /var/lib/dog-agent
```

### 3.2 File di Configurazione

Crea il file `/etc/dog-agent/config.yaml`:

```bash
cat > /etc/dog-agent/config.yaml << 'EOF'
# Dog Agent Configuration

# Server Configuration
server:
  host: "firedog-server.domain.com"  # SOSTITUISCI con IP/hostname del server
  port: 8001
  protocol: "wss"  # ws per HTTP, wss per HTTPS
  api_key: "YOUR_API_KEY_HERE"  # SOSTITUISCI con API key dal server

# Agent Configuration
agent:
  name: ""  # Lascia vuoto per usare hostname
  group: "default"  # Gruppo di appartenenza (es: production, development, dmz)
  log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  log_file: "/var/log/dog-agent/agent.log"
  pid_file: "/var/run/dog-agent.pid"

# Monitoring Configuration
monitoring:
  interval: 30  # Secondi tra ogni heartbeat
  collect_metrics: true
  metrics_history: 100  # Numero di sample da mantenere in memoria

# Threat Detection Configuration
threat_detection:
  enabled: true
  threshold: 75  # Soglia di minaccia (0-100)
  check_interval: 60  # Secondi tra ogni controllo
  max_failed_login: 5  # Numero max tentativi login falliti
  scan_ports: true
  scan_processes: true

# Firewall Configuration
firewall:
  enabled: true
  backend: "iptables"  # iptables o nftables
  auto_apply: true  # Applica automaticamente le regole ricevute
  backup_rules: true  # Backup regole prima di modifiche

# Reconnection Configuration
reconnection:
  enabled: true
  initial_delay: 5  # Secondi prima del primo tentativo
  max_delay: 300  # Massimo delay tra tentativi (5 minuti)
  backoff_multiplier: 2  # Moltiplicatore per exponential backoff
EOF
```

### 3.3 Configurazione API Key

**IMPORTANTE**: Recupera l'API Key dal server FireDog:

1. Accedi al server FireDog web interface
2. Vai su **Settings** → **General** → **Agent API Keys**
3. Copia la chiave generata

Poi inseriscila nel config:

```bash
# Modifica config con la tua API key
vim /etc/dog-agent/config.yaml
# Sostituisci: api_key: "YOUR_API_KEY_HERE"
# Con:        api_key: "la-tua-chiave-generata-dal-server"
```

### 3.4 Configurazione Gruppo (Opzionale)

Per organizzare i target in gruppi:

```bash
# Modifica il gruppo nel config
vim /etc/dog-agent/config.yaml

# Esempi di gruppi:
# agent:
#   group: "production"      # Server di produzione
#   group: "development"     # Server di sviluppo
#   group: "dmz"            # Server in DMZ
#   group: "web-servers"    # Web server
#   group: "db-servers"     # Database server
```

I gruppi permettono di inviare comandi a tutti i target appartenenti allo stesso gruppo.

---

## 4. Creazione Servizio Systemd

### 4.1 Crea File di Servizio

```bash
cat > /etc/systemd/system/dog-agent.service << 'EOF'
[Unit]
Description=FireDog Agent - Security Monitoring and Management
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root

# Percorsi
ExecStart=/usr/local/bin/dog-agent start
ExecStop=/usr/local/bin/dog-agent stop
PIDFile=/var/run/dog-agent.pid

# Configurazione
Environment="DOG_AGENT_CONFIG=/etc/dog-agent/config.yaml"

# Restart policy
Restart=always
RestartSec=10

# Sicurezza
PrivateTmp=yes
NoNewPrivileges=false
ProtectSystem=full
ProtectHome=yes

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=dog-agent

[Install]
WantedBy=multi-user.target
EOF
```

### 4.2 Abilita e Avvia Servizio

```bash
# Ricarica systemd
systemctl daemon-reload

# Abilita avvio automatico
systemctl enable dog-agent

# Avvia agent
systemctl start dog-agent

# Verifica stato
systemctl status dog-agent
```

---

## 5. Verifica Installazione

### 5.1 Controllo Stato Servizio

```bash
# Stato servizio
systemctl status dog-agent

# Log in tempo reale
journalctl -u dog-agent -f

# Log completo
cat /var/log/dog-agent/agent.log
```

### 5.2 Verifica Connessione al Server

Nel log dovresti vedere:

```
[INFO] Connecting to server: wss://firedog-server:8001
[INFO] Connected to server successfully
[INFO] Pairing request sent
[INFO] Pairing successful - Target ID: 123
[INFO] Agent ready and monitoring
```

### 5.3 Verifica sul Server FireDog

1. Accedi alla web interface del server
2. Vai su **Discovery** o **Targets**
3. Dovresti vedere il nuovo target con:
   - Hostname
   - IP address
   - Stato: **Online** (pallino verde)
   - Gruppo assegnato
   - Ultimo heartbeat recente

---

## 6. Gestione Agent

### 6.1 Comandi Base

```bash
# Avvia agent
systemctl start dog-agent

# Ferma agent
systemctl stop dog-agent

# Riavvia agent
systemctl restart dog-agent

# Stato agent
systemctl status dog-agent

# Log agent
journalctl -u dog-agent -f
```

### 6.2 Modifica Configurazione

```bash
# Modifica config
vim /etc/dog-agent/config.yaml

# Riavvia per applicare modifiche
systemctl restart dog-agent
```

### 6.3 Test Manuale (Debug)

```bash
# Ferma il servizio
systemctl stop dog-agent

# Avvia in modalità debug
dog-agent start --debug --foreground

# Oppure con Python
python3 /usr/local/bin/dog-agent start --debug
```

---

## 7. Disinstallazione

### 7.1 Rimozione Completa

```bash
# Ferma servizio
systemctl stop dog-agent
systemctl disable dog-agent

# Rimuovi servizio
rm /etc/systemd/system/dog-agent.service
systemctl daemon-reload

# Rimuovi agent
pip3 uninstall dog-agent

# Rimuovi configurazione (opzionale)
rm -rf /etc/dog-agent
rm -rf /var/log/dog-agent
rm -rf /var/lib/dog-agent
```

---

## 8. Troubleshooting

### Agent non si connette al server

**Problema**: `Connection refused` o `Connection timeout`

**Soluzioni**:

```bash
# 1. Verifica configurazione
cat /etc/dog-agent/config.yaml | grep -A5 "server:"

# 2. Verifica connettività rete
ping firedog-server
telnet firedog-server 8001

# 3. Verifica firewall
iptables -L OUTPUT -v -n
ufw status

# 4. Verifica DNS
nslookup firedog-server
```

### Errore API Key non valida

**Problema**: `Invalid API key` o `Authentication failed`

**Soluzioni**:

```bash
# 1. Verifica API key nel config
cat /etc/dog-agent/config.yaml | grep api_key

# 2. Rigenera API key sul server
# - Vai su Settings → Agent API Keys
# - Genera nuova chiave
# - Aggiorna config dell'agent

# 3. Riavvia agent
systemctl restart dog-agent
```

### Agent si disconnette continuamente

**Problema**: Agent si connette ma si disconnette dopo pochi secondi

**Soluzioni**:

```bash
# 1. Controlla log dettagliati
journalctl -u dog-agent -f

# 2. Verifica risorse sistema
free -m
df -h
top

# 3. Aumenta log level
# In /etc/dog-agent/config.yaml:
#   log_level: "DEBUG"

# 4. Riavvia
systemctl restart dog-agent
```

### Permessi insufficienti per iptables

**Problema**: `Permission denied` quando esegue comandi iptables

**Soluzioni**:

```bash
# Verifica che il servizio giri come root
systemctl status dog-agent | grep "Main PID"
ps aux | grep dog-agent

# Se necessario, modifica il servizio per girare come root
# In /etc/systemd/system/dog-agent.service:
#   User=root
#   Group=root

systemctl daemon-reload
systemctl restart dog-agent
```

---

## 9. Installazione Multipla (Script Automatico)

Per installare l'agent su molti target, crea uno script:

```bash
cat > install-agent.sh << 'EOF'
#!/bin/bash

# Configurazione
SERVER_HOST="firedog-server.domain.com"
API_KEY="your-api-key-here"
AGENT_GROUP="production"

# Installazione
apt update
apt install -y python3 python3-pip
pip3 install dog-agent

# Configurazione
mkdir -p /etc/dog-agent
cat > /etc/dog-agent/config.yaml << CONF
server:
  host: "$SERVER_HOST"
  port: 8001
  protocol: "wss"
  api_key: "$API_KEY"

agent:
  group: "$AGENT_GROUP"
  log_level: "INFO"

monitoring:
  interval: 30

threat_detection:
  enabled: true
  threshold: 75

firewall:
  enabled: true
  backend: "iptables"
CONF

# Servizio
cat > /etc/systemd/system/dog-agent.service << SERVICE
[Unit]
Description=FireDog Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/dog-agent start
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE

# Avvio
systemctl daemon-reload
systemctl enable dog-agent
systemctl start dog-agent

echo "Agent installato con successo!"
systemctl status dog-agent
EOF

chmod +x install-agent.sh
```

Poi puoi eseguire lo script su ogni target:

```bash
# Locale
./install-agent.sh

# Remoto via SSH
scp install-agent.sh root@target:/tmp/
ssh root@target "bash /tmp/install-agent.sh"

# Multipli target
for host in server1 server2 server3; do
  scp install-agent.sh root@$host:/tmp/
  ssh root@$host "bash /tmp/install-agent.sh"
done
```

---

## 10. Best Practices

1. **Sicurezza API Key**:
   - Non condividere l'API key
   - Usa permessi file appropriati: `chmod 600 /etc/dog-agent/config.yaml`

2. **Gruppi Logici**:
   - Organizza target in gruppi significativi
   - Usa nomi gruppo descrittivi (production, development, dmz, web, db)

3. **Monitoraggio**:
   - Controlla regolarmente i log: `journalctl -u dog-agent`
   - Verifica connessione sul server FireDog

4. **Aggiornamenti**:
   - Mantieni l'agent aggiornato
   - Testa aggiornamenti in dev prima di production

5. **Backup Configurazione**:
   ```bash
   cp /etc/dog-agent/config.yaml /etc/dog-agent/config.yaml.backup
   ```

---

## Support

Per problemi o domande:
- Issues: https://github.com/Dognet-Technologies/firedog/issues
- Documentazione: `/opt/firedog/docs/`
- Log agent: `/var/log/dog-agent/agent.log`
- Log systemd: `journalctl -u dog-agent -f`

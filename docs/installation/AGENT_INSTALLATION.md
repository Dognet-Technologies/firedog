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

### 2.4 Conversione UTF-8 dei File Python (IMPORTANTE!)

**NOTA**: Alcuni file Python dell'agent potrebbero avere encoding ISO-8859-1 che causa errori con Python 3.9+. Convertili in UTF-8:

```bash
# Installa iconv se non presente
apt install -y libc-bin

# Converti i file problematici
cd /opt/dog-agent

# Lista file da convertire (se presenti)
for file in integrity_monitor.py websocket_client.py; do
  if [ -f "$file" ]; then
    echo "Converting $file to UTF-8..."
    iconv -f ISO-8859-1 -t UTF-8 "$file" -o "${file}.utf8"
    mv "${file}.utf8" "$file"
  fi
done

# Verifica encoding
file *.py
```

Se vedi errori tipo:
```
SyntaxError: (unicode error) 'utf-8' codec can't decode byte 0xe0
```

Significa che il file ha encoding sbagliato e va convertito con iconv.

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

**IMPORTANTE: L'agent usa formato JSON, NON YAML!**

Crea il file `/etc/dog-agent/agent.conf` (NON config.yaml):

```bash
cat > /etc/dog-agent/agent.conf << 'EOF'
{
  "server": {
    "url": "ws://firedog-server-ip:8001",
    "api_key": "YOUR_API_KEY_HERE",
    "verify_ssl": false
  },
  "agent": {
    "name": "",
    "group": "default",
    "log_level": "INFO",
    "log_path": "/var/log/dog-agent/agent.log",
    "notification_interval": 30
  },
  "monitoring": {
    "check_integrity": false,
    "integrity_files": [],
    "pcap_path_input": "/var/log/ulog/syslogemu.log",
    "pcap_path_output": "/tmp/firedog-analysis.json"
  },
  "intervention": {
    "mode": "manual",
    "threat_threshold": 75
  }
}
EOF

# Imposta permessi corretti
chmod 600 /etc/dog-agent/agent.conf
```

**Note importanti:**
- Il file DEVE chiamarsi `agent.conf` (non `config.yaml`)
- Il formato è **JSON** (non YAML)
- `server.url` deve essere il WebSocket completo: `ws://IP:8001` (o `wss://` per HTTPS)
- Per HTTP usa `ws://`, per HTTPS usa `wss://`
- Sostituisci `firedog-server-ip` con l'IP reale del server (es: `10.99.201.6`)

### 3.3 Configurazione API Key

**IMPORTANTE**: Recupera l'API Key dal server FireDog:

1. Accedi al server FireDog web interface
2. Vai su **Settings** → **General** → **Agent API Keys**
3. Copia la chiave generata

Poi inseriscila nel config:

```bash
# Modifica config con la tua API key
vim /etc/dog-agent/agent.conf
# Sostituisci: "api_key": "YOUR_API_KEY_HERE"
# Con:        "api_key": "la-tua-chiave-generata-dal-server"
```

### 3.4 Configurazione Gruppo (Opzionale)

Per organizzare i target in gruppi:

```bash
# Modifica il gruppo nel config
vim /etc/dog-agent/agent.conf

# Esempi di gruppi in formato JSON:
# "agent": {
#   "group": "production"      # Server di produzione
#   "group": "development"     # Server di sviluppo
#   "group": "dmz"            # Server in DMZ
#   "group": "web-servers"    # Web server
#   "group": "db-servers"     # Database server
# }
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
Environment="DOG_AGENT_CONFIG=/etc/dog-agent/agent.conf"

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
vim /etc/dog-agent/agent.conf

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
cat /etc/dog-agent/agent.conf | grep -A3 "server"

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
cat /etc/dog-agent/agent.conf | grep api_key

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
# In /etc/dog-agent/agent.conf:
#   "log_level": "DEBUG"

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

### Errore "Identity hash verification failed"

**Problema**: Agent si connette ma pairing fallisce con `Identity hash verification failed`

**Soluzioni**:

```bash
# 1. Verifica log agent per trovare l'identity hash
journalctl -u dog-agent -n 100 | grep "identity_hash"

# Dovresti vedere qualcosa come:
# "identity_hash": "abc123def456..."

# 2. Accedi al database del server FireDog
# Sul server (10.99.201.6):
sudo -u postgres psql -d firedog

# 3. Trova il target
SELECT id, hostname, ip_address, status, identity_hash FROM targets_target;

# 4. Aggiorna identity_hash e status
UPDATE targets_target
SET identity_hash = 'HASH_DAI_LOG_AGENT',
    status = 'active'
WHERE hostname = 'HOSTNAME_AGENT';

# 5. Esci dal database
\q

# 6. Riavvia agent
systemctl restart dog-agent

# 7. Verifica connessione
journalctl -u dog-agent -f
```

**Nota**: Dopo l'aggiornamento, il target dovrebbe apparire online nella web interface con pallino verde.

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
cat > /etc/dog-agent/agent.conf << CONF
{
  "server": {
    "url": "wss://$SERVER_HOST:8001",
    "api_key": "$API_KEY",
    "verify_ssl": true
  },
  "agent": {
    "name": "",
    "group": "$AGENT_GROUP",
    "log_level": "INFO",
    "log_path": "/var/log/dog-agent/agent.log",
    "notification_interval": 30
  },
  "monitoring": {
    "check_integrity": false,
    "integrity_files": [],
    "pcap_path_input": "/var/log/ulog/syslogemu.log",
    "pcap_path_output": "/tmp/firedog-analysis.json"
  },
  "intervention": {
    "mode": "manual",
    "threat_threshold": 75
  }
}
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
   - Usa permessi file appropriati: `chmod 600 /etc/dog-agent/agent.conf`

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
   cp /etc/dog-agent/agent.conf /etc/dog-agent/agent.conf.backup
   ```

---

## Support

Per problemi o domande:
- Issues: https://github.com/Dognet-Technologies/firedog/issues
- Documentazione: `/opt/firedog/docs/`
- Log agent: `/var/log/dog-agent/agent.log`
- Log systemd: `journalctl -u dog-agent -f`

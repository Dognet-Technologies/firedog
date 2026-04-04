# FireDog - Quick Start Guide

Guida rapida per installare e configurare FireDog in pochi minuti.

---

## Panoramica

FireDog è una piattaforma di gestione e monitoraggio della sicurezza per infrastrutture Linux. Include:

- **Server**: Dashboard web per gestione centralizzata
- **Agent**: Software installato sui target per monitoraggio e controllo remoto

**Architettura**:
```
┌──────────────────┐
│  FireDog Server  │  ← Dashboard Web (porta 3000)
│  - PostgreSQL    │  ← Backend API (porta 8000)
│  - Redis         │  ← WebSocket (porta 8001)
│  - Celery        │
└──────────────────┘
         ↕ WebSocket (wss://)
┌──────────────────┐
│  Target Machine  │
│  + Dog Agent     │
└──────────────────┘
```

---

## Parte 1: Installazione Server (Debian 12)

> **Nota**: Questa guida usa Docker per semplicità. Per installazione nativa senza Docker, vedi [SERVER_NATIVE_INSTALLATION.md](./SERVER_NATIVE_INSTALLATION.md)

### Step 1: Preparazione Sistema

```bash
# Login come root
su -

# Aggiorna sistema
apt update && apt upgrade -y

# Installa requisiti base
apt install -y curl wget git vim
```

### Step 2: Installa Docker

```bash
# Installa Docker
curl -fsSL https://get.docker.com | sh

# Installa Docker Compose
apt install -y docker-compose-plugin

# Verifica
docker --version
docker compose version
```

### Step 3: Installa FireDog

```bash
# Clone repository
mkdir -p /opt/firedog
cd /opt/firedog
git clone https://github.com/Dognet-Technologies/firedog.git .

# Configura ambiente
cp .env.example .env
vim .env  # Modifica almeno: POSTGRES_PASSWORD, DJANGO_SECRET_KEY, REDIS_PASSWORD

# Build e avvia
docker compose build
docker compose up -d

# Verifica
docker compose ps
```

### Step 4: Inizializza Database

```bash
# Esegui migrazioni
docker exec -it firedog-backend python manage.py migrate

# Crea admin user
docker exec -it firedog-backend python manage.py createsuperuser
# Username: admin
# Email: admin@firedog.local
# Password: [scegli password sicura]
```

### Step 5: Accedi Web Interface

Apri browser: `http://your-server-ip:3000`

Login con credenziali create al passo precedente.

### Step 6: Genera API Key per Agent

1. Nel menu: **Settings** → **General**
2. Sezione **Agent API Keys** → **Generate New API Key**
3. **COPIA LA CHIAVE** (es: `aBcDeFgH123456789...`)
4. Salva in un file: `echo "aBcDeFgH123456789..." > /root/agent-api-key.txt`

✅ **Server installato e pronto!**

---

## Parte 2: Installazione Agent su Target

### Step 1: Prerequisiti Target

```bash
# Sul target machine (Debian/Ubuntu)
apt update
apt install -y python3 python3-pip iptables
```

### Step 2: Installa Agent

**Opzione A - Da Package** (raccomandato):

```bash
# Scarica package dal server o repository
curl -O http://firedog-server/packages/dog-agent-latest.whl
pip3 install dog-agent-latest.whl
```

**Opzione B - Da Sorgenti**:

```bash
cd /tmp
git clone https://github.com/Dognet-Technologies/firedog.git
cd firedog/firedog-package
pip3 install .
```

### Step 3: Configura Agent

**IMPORTANTE: L'agent usa formato JSON, NON YAML!**

```bash
# Crea directory
mkdir -p /etc/dog-agent

# Crea configurazione (formato JSON)
cat > /etc/dog-agent/agent.conf << 'EOF'
{
  "server": {
    "url": "wss://FIREDOG_SERVER_IP:8001",
    "api_key": "TUA_API_KEY_QUI",
    "verify_ssl": true
  },
  "agent": {
    "name": "",
    "group": "production",
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

# Imposta permessi
chmod 600 /etc/dog-agent/agent.conf
```

**Note importanti:**
- Il file DEVE chiamarsi `agent.conf` (non `config.yaml`)
- Il formato è **JSON** (non YAML)
- `server.url` deve essere WebSocket completo: `wss://IP:8001` (o `ws://` per HTTP)

### Step 4: Crea Servizio Systemd

```bash
cat > /etc/systemd/system/dog-agent.service << 'EOF'
[Unit]
Description=FireDog Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/dog-agent start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### Step 5: Avvia Agent

```bash
# Abilita e avvia
systemctl daemon-reload
systemctl enable dog-agent
systemctl start dog-agent

# Verifica
systemctl status dog-agent
journalctl -u dog-agent -f
```

### Step 6: Verifica Connessione

**Sul target** - Controlla log:

```bash
journalctl -u dog-agent -n 50

# Dovresti vedere:
# [INFO] Connected to server successfully
# [INFO] Pairing successful - Target ID: 123
```

**Sul server** - Verifica web interface:

1. Vai su **Discovery** o **Targets**
2. Il nuovo target dovrebbe apparire come **Online** (🟢)

✅ **Agent installato e connesso!**

---

## Parte 3: Primi Passi

### 1. Organizza Target in Gruppi

I gruppi permettono di gestire multiple macchine contemporaneamente.

**Esempi di gruppi**:
- `production` - Server di produzione
- `development` - Server di sviluppo
- `web-servers` - Web server Apache/Nginx
- `db-servers` - Database server
- `dmz` - Server in zona DMZ

**Per assegnare gruppo**, modifica config agent:

```bash
# Sul target
vim /etc/dog-agent/agent.conf

# Modifica (JSON format):
{
  "agent": {
    "group": "web-servers"
  }
}

# Riavvia
systemctl restart dog-agent
```

### 2. Gestione Firewall

**Regola singolo target**:
1. Vai su **Firewall** → **Rules**
2. Seleziona **Target Singolo**
3. Scegli target dal menu
4. Aggiungi regola (modalità Standard o Expert)

**Regola intero gruppo**:
1. Vai su **Firewall** → **Rules**
2. Seleziona **Gruppo**
3. Scegli gruppo dal menu
4. Aggiungi regola (verrà applicata a tutti i target del gruppo)

### 3. Monitoraggio

**Dashboard**:
- Overview di tutti i target
- Stato online/offline
- Metriche sistema (CPU, RAM, Disk)
- Alert e threat detection

**Threat Logs**:
- Attacchi rilevati
- Tentativi di login falliti
- Port scan detection
- Anomalie di sistema

### 4. Discovery

**Scansione automatica rete**:
1. Vai su **Discovery**
2. Configura range IP da scansionare
3. Avvia scansione
4. Importa host trovati come target

---

## Comandi Utili

### Server (Docker)

```bash
cd /opt/firedog

# Stato containers
docker compose ps

# Log in tempo reale
docker compose logs -f backend

# Riavvia server
docker compose restart

# Ferma server
docker compose down

# Avvia server
docker compose up -d

# Backup database
docker exec firedog-db pg_dump -U firedog firedog > backup.sql

# Ripristina database
docker exec -i firedog-db psql -U firedog firedog < backup.sql
```

### Agent (Target)

```bash
# Stato agent
systemctl status dog-agent

# Log agent
journalctl -u dog-agent -f

# Riavvia agent
systemctl restart dog-agent

# Test connessione manuale
dog-agent start --debug --foreground

# Verifica config
cat /etc/dog-agent/agent.conf

# Verifica connettività verso server
telnet firedog-server 8001
```

---

## Troubleshooting Rapido

### Server non risponde

```bash
# Verifica container
docker compose ps

# Riavvia tutto
docker compose restart

# Verifica log
docker compose logs backend
docker compose logs db
```

### Agent non si connette

```bash
# Verifica config
cat /etc/dog-agent/agent.conf | grep -E "(url|api_key)"

# Test connessione
ping firedog-server-ip
telnet firedog-server-ip 8001

# Verifica firewall target
iptables -L OUTPUT -v

# Log dettagliati
journalctl -u dog-agent -f
```

### Target appare offline su server

```bash
# Sul target - verifica servizio
systemctl status dog-agent

# Riavvia
systemctl restart dog-agent

# Sul server - verifica websocket
docker compose logs backend | grep -i websocket
```

---

## Script Installazione Automatica

### Server (One-liner)

```bash
curl -fsSL https://raw.githubusercontent.com/Dognet-Technologies/firedog/main/scripts/install-server.sh | bash
```

### Agent (One-liner)

```bash
curl -fsSL https://raw.githubusercontent.com/Dognet-Technologies/firedog/main/scripts/install-agent.sh | bash -s -- \
  --server "firedog-server-ip" \
  --api-key "your-api-key" \
  --group "production"
```

---

## Architettura Consigliata

### Piccola Infrastruttura (< 10 target)

```
1x Server FireDog: 2 CPU, 4GB RAM, 20GB disk
Nx Target con agent: 1 CPU, 512MB RAM
```

### Media Infrastruttura (10-50 target)

```
1x Server FireDog: 4 CPU, 8GB RAM, 50GB SSD
Nx Target con agent: 1 CPU, 512MB RAM
Optional: Nginx reverse proxy con SSL
```

### Grande Infrastruttura (50+ target)

```
1x Server FireDog: 8+ CPU, 16+ GB RAM, 100GB SSD
Nx Target con agent: 1 CPU, 512MB RAM
Nginx reverse proxy + SSL
PostgreSQL tuning per performance
Redis clustering (optional)
Backup automatico giornaliero
```

---

## Sicurezza Best Practices

1. **Server**:
   - Usa password forti per database e admin
   - Cambia `DJANGO_SECRET_KEY` in produzione
   - Abilita SSL/TLS (nginx + certbot)
   - Firewall: apri solo porte necessarie (80, 443, 8001)

2. **Agent**:
   - Proteggi API key: `chmod 600 /etc/dog-agent/agent.conf`
   - Non condividere API key tra ambienti
   - Usa gruppi per separare production/development
   - Monitora log regolarmente

3. **Network**:
   - Usa VPN per connessioni server-agent (opzionale)
   - Segmenta rete (DMZ, internal, management)
   - Firewall rules tra zone

---

## Prossimi Passi

1. **Documentazione Completa**:
   - [SERVER_INSTALLATION.md](./SERVER_INSTALLATION.md) - Installazione server dettagliata
   - [AGENT_INSTALLATION.md](./AGENT_INSTALLATION.md) - Installazione agent dettagliata

2. **Configurazione Avanzata**:
   - Nginx reverse proxy con SSL
   - Backup automatico database
   - Alta disponibilità (HA setup)
   - Monitoraggio con Prometheus/Grafana

3. **Integrazione**:
   - Notifiche (Email, Slack, Discord)
   - SIEM integration
   - CI/CD pipeline per deploy automatico

---

## Support & Community

- **Issues**: https://github.com/Dognet-Technologies/firedog/issues
- **Documentazione**: `/opt/firedog/docs/`
- **Wiki**: https://github.com/Dognet-Technologies/firedog/wiki

---

**Hai completato la configurazione di FireDog!** 🎉

Il tuo sistema è ora pronto per monitorare e gestire la sicurezza della tua infrastruttura.

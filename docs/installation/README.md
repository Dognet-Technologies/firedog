# FireDog - Documentazione Installazione

Documentazione completa per l'installazione e configurazione di FireDog.

---

## 📚 Indice Documentazione

### ⚙️ Scelta Metodo di Installazione

**Docker vs Nativo - Quale scegliere?**

| Caratteristica | Docker | Nativo |
|---------------|--------|--------|
| **Facilità installazione** | ⭐⭐⭐⭐⭐ Molto semplice | ⭐⭐⭐ Media |
| **Performance** | ⭐⭐⭐⭐ Ottima | ⭐⭐⭐⭐⭐ Massima |
| **Isolamento** | ⭐⭐⭐⭐⭐ Completo | ⭐⭐ Limitato |
| **Aggiornamenti** | ⭐⭐⭐⭐⭐ Molto facili | ⭐⭐⭐ Manuali |
| **Controllo sistema** | ⭐⭐⭐ Limitato | ⭐⭐⭐⭐⭐ Completo |
| **Uso risorse** | ⭐⭐⭐⭐ Efficiente | ⭐⭐⭐⭐⭐ Massimo |
| **Troubleshooting** | ⭐⭐⭐ Medio | ⭐⭐⭐⭐ Diretto |
| **Portabilità** | ⭐⭐⭐⭐⭐ Massima | ⭐⭐ Bassa |

**Usa Docker se:**
- Prima installazione o test
- Vuoi semplicità di gestione
- Preferisci isolamento applicativo
- Hai poca esperienza con gestione server

**Usa Nativo se:**
- Ambiente production enterprise
- Vuoi massime performance
- Hai requisiti specifici di sistema
- Preferisci controllo completo
- Hai esperienza con gestione server Linux

---

### 🚀 [Quick Start Guide](./QUICK_START.md)
**Guida rapida** per installare server e agent in pochi minuti.

**Ideale per**: Prima installazione, test, proof of concept

**Tempo stimato**: 15-30 minuti

---

### 🖥️ [Server Installation (Docker)](./SERVER_INSTALLATION.md)
**Guida completa** per l'installazione del server FireDog su Debian 12 con Docker.

**Include**:
- Requisiti sistema
- Installazione Docker
- Configurazione database PostgreSQL
- Setup Redis e Celery
- Nginx reverse proxy (opzionale)
- SSL/TLS con Let's Encrypt
- Backup automatico
- Troubleshooting

**Tempo stimato**: 30-60 minuti

---

### 💻 [Server Installation (Native - No Docker)](./SERVER_NATIVE_INSTALLATION.md)
**Guida completa** per l'installazione nativa del server FireDog su Debian 12 senza Docker.

**Include**:
- Installazione PostgreSQL nativo
- Installazione Redis nativo
- Setup Python virtualenv
- Configurazione Django con Gunicorn e Daphne
- Servizi systemd per tutti i componenti
- Setup Celery worker e beat
- Installazione Node.js e build React
- Nginx come reverse proxy
- SSL/TLS con Let's Encrypt
- Script backup e manutenzione
- Troubleshooting

**Tempo stimato**: 45-90 minuti

**Ideale per**: Production server, installazioni enterprise, controllo completo

---

### 📡 [Agent Installation](./AGENT_INSTALLATION.md)
**Guida completa** per l'installazione del Dog Agent sui target.

**Include**:
- Sistemi supportati (Debian/Ubuntu)
- Installazione da package o sorgenti
- Configurazione dettagliata
- Setup servizio systemd
- Gestione gruppi
- Script installazione automatica
- Troubleshooting

**Tempo stimato**: 10-20 minuti per target

---

## 🎯 Percorsi di Installazione

### Scenario 1: Prima Installazione

1. **Leggi** [QUICK_START.md](./QUICK_START.md) per panoramica
2. **Installa Server** seguendo [SERVER_INSTALLATION.md](./SERVER_INSTALLATION.md)
3. **Installa Agent** su 1-2 target di test seguendo [AGENT_INSTALLATION.md](./AGENT_INSTALLATION.md)
4. **Testa** funzionalità base dalla web interface
5. **Scala** installando agent su altri target

### Scenario 2: Ambiente Production

**Scegli metodo di installazione:**
- **Docker** ([SERVER_INSTALLATION.md](./SERVER_INSTALLATION.md)) - Più semplice, isolato, aggiornamenti facili
- **Nativo** ([SERVER_NATIVE_INSTALLATION.md](./SERVER_NATIVE_INSTALLATION.md)) - Controllo completo, performance ottimali

**Passi:**
1. **Pianifica** architettura (server sizing, network, gruppi)
2. **Installa Server** con configurazione production (Docker o Nativo)
3. **Configura SSL** con nginx e Let's Encrypt
4. **Setup Backup** automatico database
5. **Installa Agent** su target di development per test
6. **Valida** setup con test completo
7. **Deploy Agent** su production usando script automatico

### Scenario 3: Ambiente di Sviluppo

1. **Quick install server** con [QUICK_START.md](./QUICK_START.md)
2. **Installa Agent** su VM locale
3. **Sviluppo** e testing features

---

## 📋 Checklist Pre-Installazione

### Server

- [ ] Debian 12 installato e aggiornato
- [ ] IP statico configurato
- [ ] Accesso root o sudo
- [ ] Almeno 4GB RAM disponibili
- [ ] Almeno 20GB disk disponibili
- [ ] Porta 8000 (API) accessibile
- [ ] Porta 8001 (WebSocket) accessibile
- [ ] Porta 3000 (Frontend) accessibile
- [ ] Connessione internet attiva

### Target (Agent)

- [ ] Debian/Ubuntu supportato (11, 12, 20.04, 22.04, 24.04)
- [ ] Python 3.9+ installato
- [ ] Accesso root o sudo
- [ ] Connettività verso server FireDog (porta 8001)
- [ ] iptables installato
- [ ] systemd disponibile

---

## 🔧 Requisiti di Sistema

### Server Minimo

| Componente | Minimo | Raccomandato |
|------------|--------|--------------|
| CPU | 2 core | 4+ core |
| RAM | 4 GB | 8+ GB |
| Disk | 20 GB | 50+ GB SSD |
| Network | 1 Gbps | 1+ Gbps |
| OS | Debian 12 | Debian 12 |

### Target (Agent) Minimo

| Componente | Minimo |
|------------|--------|
| CPU | 1 core |
| RAM | 512 MB |
| Disk | 100 MB |
| Network | 100 Mbps |
| OS | Debian 11+ / Ubuntu 20.04+ |

---

## 🌐 Porte di Rete

### Server FireDog

| Porta | Protocollo | Servizio | Descrizione |
|-------|-----------|----------|-------------|
| 3000 | TCP | Frontend | React Web Interface |
| 8000 | TCP | Backend | Django REST API |
| 8001 | TCP | WebSocket | Agent Communication (wss://) |
| 5432 | TCP | PostgreSQL | Database (interno Docker) |
| 6379 | TCP | Redis | Cache (interno Docker) |

**Note**:
- PostgreSQL e Redis sono interni a Docker (non esposti esternamente)
- In production, usa nginx reverse proxy su porta 80/443

### Target (Agent)

| Porta | Protocollo | Direzione | Descrizione |
|-------|-----------|-----------|-------------|
| 8001 | TCP | Outbound | Connessione a server FireDog |

**Note**:
- L'agent apre solo connessioni outbound (nessuna porta in ascolto)
- Connessione WebSocket persistente verso server

---

## 📦 Componenti Software

### Server

```
┌─────────────────────────────────────┐
│         Docker Containers           │
├─────────────────────────────────────┤
│ • firedog-frontend    (React)       │
│ • firedog-backend     (Django)      │
│ • firedog-db          (PostgreSQL)  │
│ • firedog-redis       (Redis)       │
│ • firedog-celery      (Worker)      │
│ • firedog-celery-beat (Scheduler)   │
└─────────────────────────────────────┘
```

**Dipendenze principali**:
- Docker Engine 24+
- Docker Compose 2.0+
- Debian 12 (Bookworm)

### Agent

```
┌──────────────────────────┐
│     Dog Agent Service    │
├──────────────────────────┤
│ • websocket_client.py    │
│ • system_monitor.py      │
│ • threat_detector.py     │
│ • firewall_manager.py    │
│ • config_manager.py      │
└──────────────────────────┘
```

**Dipendenze principali**:
- Python 3.9+
- websockets
- psutil
- cryptography
- pyyaml
- systemd

---

## 🔐 Sicurezza

### Credenziali da Configurare

**Server**:
1. `POSTGRES_PASSWORD` - Password database
2. `DJANGO_SECRET_KEY` - Secret key Django
3. `REDIS_PASSWORD` - Password Redis
4. Superuser Django (username/password)
5. API Key per agent

**Agent**:
1. API Key (ottenuta dal server)

### File Sensibili

**Proteggi questi file**:

```bash
# Server
/opt/firedog/.env                    # Variabili ambiente (chmod 600)

# Agent
/etc/dog-agent/agent.conf           # Contiene API key (chmod 600)
```

### Best Practices

1. **Password Forti**: Usa password >= 16 caratteri casuali
2. **API Key**: Non condividere, non committare in git
3. **SSL/TLS**: Usa HTTPS in production (nginx + certbot)
4. **Firewall**: Limita accesso solo a IP necessari
5. **Backup**: Cifra backup database
6. **Updates**: Mantieni sistema e Docker aggiornati

---

## 📊 Architettura Consigliata

### Piccola Infrastruttura (1-10 target)

```
                    Internet
                       │
                 ┌─────▼─────┐
                 │  Firewall │
                 └─────┬─────┘
                       │
            ┌──────────▼──────────┐
            │   FireDog Server    │
            │  2 CPU, 4GB RAM     │
            │  20GB Disk          │
            └──────────┬──────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
    │ Target1 │   │ Target2 │   │ Target3 │
    │ +Agent  │   │ +Agent  │   │ +Agent  │
    └─────────┘   └─────────┘   └─────────┘
```

### Media Infrastruttura (10-50 target)

```
                    Internet
                       │
                 ┌─────▼─────┐
                 │   Nginx   │
                 │ SSL Proxy │
                 └─────┬─────┘
                       │
            ┌──────────▼──────────┐
            │   FireDog Server    │
            │  4 CPU, 8GB RAM     │
            │  50GB SSD           │
            └──────────┬──────────┘
                       │
         ┌─────────────┼─────────────┬─────────────┐
         │             │             │             │
    [Production]  [Development]  [DMZ Zone]   [Database]
      10 targets    5 targets      3 targets   2 targets
```

### Grande Infrastruttura (50+ target)

```
                    Internet
                       │
                  ┌────▼────┐
                  │   CDN   │
                  └────┬────┘
                       │
                  ┌────▼────┐
                  │ Nginx   │
                  │ HA +SSL │
                  └────┬────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
  ┌─────▼──────┐              ┌───────▼──────┐
  │  FireDog   │◄────SYNC────►│   FireDog    │
  │  Primary   │              │   Standby    │
  │ 8CPU, 16GB │              │  8CPU, 16GB  │
  └─────┬──────┘              └───────┬──────┘
        │                             │
    ┌───▼────────────────────────┬────▼───┐
    │                            │        │
  [Prod]                      [Dev]    [DMZ]
  50+ targets                10 targets 5 targets
```

---

## 🛠️ Tools & Utility

### Script Utili

Nella cartella `scripts/` trovi:

- `install-server.sh` - Installazione automatica server
- `install-agent.sh` - Installazione automatica agent
- `backup-db.sh` - Backup database
- `restore-db.sh` - Ripristino database
- `health-check.sh` - Verifica stato sistema

### Monitoring

**Log Files**:

```bash
# Server
docker compose logs -f backend
docker compose logs -f celery
journalctl -u docker

# Agent
journalctl -u dog-agent -f
cat /var/log/dog-agent/agent.log
```

**Health Checks**:

```bash
# Server
curl http://localhost:8000/api/health/
curl http://localhost:3000/

# Agent
systemctl status dog-agent
dog-agent --version
```

---

## 📞 Support

### Documentazione

- **Installazione**: `/docs/installation/`
- **Dog Agent Specs**: `/docs/dog_agent_specs/`
- **API Reference**: `/docs/api/`

### Community

- **Issues**: https://github.com/Dognet-Technologies/firedog/issues
- **Discussions**: https://github.com/Dognet-Technologies/firedog/discussions
- **Wiki**: https://github.com/Dognet-Technologies/firedog/wiki

### Troubleshooting

Se incontri problemi:

1. Controlla la sezione **Troubleshooting** nella guida specifica
2. Verifica i log (server e agent)
3. Consulta le **Issues** su GitHub
4. Crea una nuova issue con:
   - Versione sistema operativo
   - Versione Docker (server)
   - Versione Python (agent)
   - Log completi dell'errore
   - Passi per riprodurre

---

## 🚀 Inizio Rapido

**Server (5 minuti)**:

```bash
cd /opt/firedog
git clone https://github.com/Dognet-Technologies/firedog.git .
cp .env.example .env
vim .env  # Configura password
docker compose up -d
docker exec -it firedog-backend python manage.py migrate
docker exec -it firedog-backend python manage.py createsuperuser
```

**Agent (2 minuti)**:

```bash
pip3 install dog-agent
mkdir -p /etc/dog-agent
cat > /etc/dog-agent/agent.conf << 'EOF'
{
  "server": {
    "url": "wss://firedog-ip:8001",
    "api_key": "your-key",
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
    "integrity_files": []
  },
  "intervention": {
    "mode": "manual",
    "threat_threshold": 75
  }
}
EOF
systemctl enable --now dog-agent
```

**✅ Sistema pronto!** Accedi a `http://firedog-ip:3000`

---

## 📅 Roadmap

- [ ] Supporto Ubuntu Server
- [ ] Supporto Rocky Linux / AlmaLinux
- [ ] Agent installer package (.deb, .rpm)
- [ ] Web installer wizard
- [ ] Docker compose HA setup
- [ ] Kubernetes deployment
- [ ] Ansible playbooks
- [ ] Terraform modules

---

**Buona installazione! 🎉**

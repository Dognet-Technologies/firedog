# FireDog - Sistema di Gestione Centralizzata Firewall

Sistema web centralizzato per gestire firewall iptables su molteplici sistemi target remoti.

## 🎯 Caratteristiche

- ✅ Gestione N target remoti via SSH
- ✅ Installazione automatica pacchetto firewall sui target
- ✅ Recupero periodico dati da traffic-analyzer via SCP
- ✅ Visualizzazione minacce, statistiche, regole iptables
- ✅ Aggiunta/rimozione regole da web UI
- ✅ Monitoring integrità file locale (SHA512)
- ✅ Dashboard personalizzabili

## 🏗️ Architettura

```
firedog/
├── backend/          # Django REST API
├── frontend/         # React + TypeScript UI
├── firedog-package/  # Pacchetto da installare sui target
├── scripts/          # Script di deployment e utility
├── docs/            # Documentazione
└── tests/           # Test suite
```

## 📋 Stack Tecnologico

- **Backend**: Django 4.2.11 LTS + Django REST Framework
- **Database**: PostgreSQL 13+
- **Task Queue**: Celery + Redis
- **Frontend**: React 18.2+ + TypeScript
- **SSH**: Paramiko 3.4.0
- **Charts**: Recharts 2.12.0

## 🚀 Quick Start

### Prerequisiti

- Python 3.9+
- PostgreSQL 13+
- Redis
- Node.js 18+

### Installazione Sviluppo

```bash
# 1. Setup backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configura database
sudo -u postgres createdb firedog
sudo -u postgres createuser -P microcyber

# 3. Migrazioni
python manage.py migrate

# 4. Crea superuser
python manage.py createsuperuser

# 5. Avvia server sviluppo
python manage.py runserver

# 6. Setup frontend (nuovo terminale)
cd frontend
npm install
npm start
```

### Installazione Produzione

```bash
sudo ./scripts/install.sh
```

## 📖 Documentazione

- [Specifiche Tecniche](docs/FIREDOG_TECHNICAL_SPECIFICATION_v1_0.md)
- [Guida Quick Start](docs/QUICK_START.md)
- [Esempi Avanzati](docs/ADVANCED_EXAMPLES.md)
- [Deployment](docs/DEPLOYMENT.md)

## 🔐 Sicurezza

- Autenticazione JWT
- Comunicazione SSH con chiavi Ed25519
- Permessi sudo limitati sui target
- File integrity monitoring (SHA512)
- OWASP/NIST compliance

## 🎮 Utilizzo

### Dashboard Web
```
http://localhost:3000
```

### API Endpoints
```
http://localhost:8000/api/
```

## 🧪 Testing

```bash
# Backend tests
cd backend
python manage.py test

# Frontend tests
cd frontend
npm test
```

## 📝 Licenza

Copyright © 2025 MicroCyber

## 👥 Autori

- Sistema Firewall: MicroCyber Team
- Web Wrapper: FireDog Project

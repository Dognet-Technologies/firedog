# FireDog - Guida Setup Completo

## 📦 Contenuto Archivio

L'archivio `firedog-backend-complete.tar.gz` contiene:

```
firedog/
├── backend/                   # Backend Django completo
│   ├── firedog/              # Configurazione Django
│   │   ├── settings.py       # Settings con PostgreSQL, Celery, JWT
│   │   ├── celery.py         # Configurazione Celery
│   │   └── urls.py           # URL routing API
│   ├── targets/              # App gestione target
│   │   ├── models.py         # Modello Target
│   │   ├── serializers.py    # API serializers
│   │   ├── views.py          # ViewSet API
│   │   ├── tasks.py          # Celery tasks
│   │   └── migrations/       # Database migrations
│   ├── rules/                # App gestione regole firewall
│   ├── threats/              # App gestione minacce
│   ├── dashboards/           # App dashboard personalizzabili
│   ├── integrity/            # App file integrity monitoring
│   ├── discovery/            # App network discovery
│   ├── audit/                # App audit logging
│   ├── core/                 # Utility condivise
│   │   └── ssh_manager.py    # Gestione SSH/SCP
│   ├── venv/                 # Virtual environment Python
│   ├── requirements.txt      # Dipendenze Python
│   ├── .env                  # Variabili ambiente (DA CONFIGURARE!)
│   └── manage.py             # Django management
├── scripts/                   # Script utility
│   └── setup-database.sh     # Setup PostgreSQL
├── firedog-package/          # Pacchetto da installare sui target
│   ├── firewall-manager.py
│   ├── traffic-analyzer.py
│   ├── install.sh
│   └── firewall-init.sh
├── README.md
└── .gitignore
```

## 🚀 Installazione Step-by-Step

### 1. Estrai l'archivio

```bash
cd /home/simone/Repos/Progetti
tar -xzf firedog-backend-complete.tar.gz
cd firedog
```

### 2. Installa PostgreSQL e Redis

```bash
# PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Redis
sudo apt install redis-server

# Avvia servizi
sudo systemctl start postgresql
sudo systemctl start redis-server
sudo systemctl enable postgresql
sudo systemctl enable redis-server
```

### 3. Configura Database

```bash
# Esegui script di setup
sudo bash scripts/setup-database.sh

# Oppure manualmente:
sudo -u postgres psql << EOF
CREATE USER microcyber WITH PASSWORD 'changeme123';
CREATE DATABASE firedog OWNER microcyber;
GRANT ALL PRIVILEGES ON DATABASE firedog TO microcyber;
\c firedog
GRANT ALL ON SCHEMA public TO microcyber;
EOF
```

### 4. Configura Backend

```bash
cd backend

# Il virtual environment è già creato con le dipendenze installate
# Se necessario reinstallare:
# python3 -m venv venv
# ./venv/bin/pip install -r requirements.txt

# IMPORTANTE: Modifica il file .env
nano .env

# Cambia almeno:
# - SECRET_KEY (genera una nuova chiave)
# - DB_PASSWORD (deve corrispondere a quella di PostgreSQL)
```

### 5. Applica Migrations

```bash
cd backend

# Applica migrations al database
./venv/bin/python manage.py migrate

# Output atteso:
# Running migrations:
#   Applying contenttypes.0001_initial... OK
#   Applying auth.0001_initial... OK
#   Applying targets.0001_initial... OK
#   Applying rules.0001_initial... OK
#   ...
```

### 6. Crea Superuser

```bash
./venv/bin/python manage.py createsuperuser

# Inserisci:
# Username: admin
# Email: admin@firedog.local
# Password: (scegli password sicura)
```

### 7. Genera Chiavi SSH

```bash
# Crea directory per chiavi
sudo mkdir -p /etc/firedog/ssh-keys

# Genera chiave Ed25519
sudo ssh-keygen -t ed25519 -f /etc/firedog/ssh-keys/id_ed25519 -N ""

# Permessi corretti
sudo chmod 600 /etc/firedog/ssh-keys/id_ed25519
sudo chmod 644 /etc/firedog/ssh-keys/id_ed25519.pub

# Mostra chiave pubblica (da copiare sui target)
cat /etc/firedog/ssh-keys/id_ed25519.pub
```

### 8. Test Backend

```bash
cd backend

# Avvia server sviluppo
./venv/bin/python manage.py runserver

# Output atteso:
# Django version 4.2.11, using settings 'firedog.settings'
# Starting development server at http://127.0.0.1:8000/
# Quit the server with CONTROL-C.
```

**Apri browser**: http://localhost:8000/admin
- Login con credenziali superuser
- Verifica che tutte le app siano visibili

### 9. Test API

```bash
# Ottieni token JWT
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_password"}'

# Risposta attesa:
# {"access":"eyJ0eXAiOiJ...","refresh":"eyJ0eXAiOiJ..."}

# Test API targets
curl http://localhost:8000/api/targets/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Risposta attesa:
# {"count":0,"next":null,"previous":null,"results":[]}
```

### 10. Avvia Celery

```bash
cd backend

# Worker (terminale 1)
./venv/bin/celery -A firedog worker --loglevel=info

# Beat scheduler (terminale 2)
./venv/bin/celery -A firedog beat --loglevel=info

# Verifica tasks schedulati:
# - fetch_all_targets_data ogni 10 minuti
# - check_all_integrity ogni 30 minuti
```

## 🎯 Preparazione Target

Sui sistemi target dove installare il firewall:

```bash
# 1. Crea utente microcyber
sudo adduser microcyber

# 2. Configura sudo (permessi limitati)
sudo visudo -f /etc/sudoers.d/microcyber

# Aggiungi:
microcyber ALL=(ALL) NOPASSWD: /usr/sbin/iptables, /usr/bin/python3 /opt/firedog/*

# 3. Copia chiave SSH pubblica
sudo mkdir -p /home/microcyber/.ssh
sudo bash -c 'echo "INCOLLA_CHIAVE_PUBBLICA_QUI" >> /home/microcyber/.ssh/authorized_keys'
sudo chown -R microcyber:microcyber /home/microcyber/.ssh
sudo chmod 700 /home/microcyber/.ssh
sudo chmod 600 /home/microcyber/.ssh/authorized_keys

# 4. Test connessione SSH
# (Dal server FireDog)
ssh -i /etc/firedog/ssh-keys/id_ed25519 microcyber@TARGET_IP
```

## 📝 Utilizzo Base

### Aggiungere un Target

```bash
# Via API
curl -X POST http://localhost:8000/api/targets/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ip_address": "192.168.1.100",
    "hostname": "server01",
    "description": "Server produzione"
  }'

# Via Admin Django
# 1. Vai su http://localhost:8000/admin/targets/target/
# 2. Click "Add Target"
# 3. Compila form
# 4. Save
```

### Test Connessione Target

```bash
curl -X POST http://localhost:8000/api/targets/1/test_connection/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Risposta attesa:
# {"success":true,"message":"Connessione SSH riuscita","user_exists":true,"whoami":"microcyber"}
```

### Installare Firedog su Target

```bash
curl -X POST http://localhost:8000/api/targets/1/install/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Risposta:
# {"success":true,"message":"Installazione avviata in background","status":"installing"}

# Monitora logs Celery per vedere progresso
```

## 🐛 Troubleshooting

### Database Connection Error

```bash
# Verifica PostgreSQL in esecuzione
sudo systemctl status postgresql

# Test connessione
psql -h localhost -U microcyber -d firedog

# Verifica credenziali in .env
cat backend/.env | grep DB_
```

### Celery Non Si Connette a Redis

```bash
# Verifica Redis
redis-cli ping  # deve rispondere PONG

# Verifica CELERY_BROKER_URL in .env
cat backend/.env | grep CELERY
```

### SSH Connection Refused

```bash
# Sul target, verifica SSH attivo
sudo systemctl status sshd

# Verifica chiave pubblica sul target
cat /home/microcyber/.ssh/authorized_keys

# Test connessione manuale
ssh -i /etc/firedog/ssh-keys/id_ed25519 microcyber@TARGET_IP -v
```

### Migrations Error

```bash
# Reset migrations (ATTENZIONE: perde dati!)
cd backend
./venv/bin/python manage.py migrate --fake-initial

# O ricrea database
sudo -u postgres dropdb firedog
sudo -u postgres createdb firedog -O microcyber
./venv/bin/python manage.py migrate
```

## 📚 Prossimi Passi

1. ✅ Backend completato
2. ⏳ Frontend React (prossimo step)
3. ⏳ Script deployment produzione
4. ⏳ Nginx reverse proxy
5. ⏳ Systemd services
6. ⏳ Testing completo

## 🔒 Sicurezza

**IMPORTANTE per produzione:**

1. Cambia `SECRET_KEY` in `.env`
2. Cambia password database
3. Imposta `DEBUG=False`
4. Configura HTTPS con certificato SSL
5. Limita `ALLOWED_HOSTS`
6. Configura firewall per porta 8000
7. Usa strong passwords per superuser

## 📞 Supporto

Per problemi o domande durante il setup, controlla:
- Logs Django: `backend/logs/django.log`
- Logs Celery: output terminale worker/beat
- Logs PostgreSQL: `/var/log/postgresql/`

## ✅ Checklist Setup

- [ ] PostgreSQL installato e configurato
- [ ] Redis installato e avviato
- [ ] Database `firedog` creato
- [ ] Backend .env configurato
- [ ] Migrations applicate
- [ ] Superuser creato
- [ ] Chiavi SSH generate
- [ ] Server sviluppo avviato (localhost:8000)
- [ ] Login admin funzionante
- [ ] Token JWT ottenuto
- [ ] Celery worker avviato
- [ ] Celery beat avviato
- [ ] Target preparati con utente microcyber
- [ ] Test connessione SSH riuscito

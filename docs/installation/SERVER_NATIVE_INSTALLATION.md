# Installazione FireDog Server (Nativa - Senza Docker)

Guida completa per l'installazione nativa di FireDog su Debian 12, senza Docker.

## Requisiti di Sistema

### Hardware Minimo
- **CPU**: 2 core
- **RAM**: 4 GB
- **Disk**: 20 GB
- **Network**: 1 interfaccia di rete

### Hardware Raccomandato
- **CPU**: 4+ core
- **RAM**: 8+ GB
- **Disk**: 50+ GB SSD
- **Network**: IP statico configurato

### Software
- **OS**: Debian 12 (Bookworm) - installazione minimal
- **Network**: Indirizzo IP statico
- **Internet**: Connessione per scaricare pacchetti

---

## 1. Preparazione Sistema Base

### 1.1 Installazione Debian 12

Durante l'installazione:
- Configura hostname: `firedog-server`
- Configura rete con IP statico
- Non installare ambiente desktop
- Installa solo: **SSH server** e **standard system utilities**

### 1.2 Aggiornamento Sistema

```bash
# Login come root
su -

# Aggiorna sistema
apt update
apt upgrade -y

# Installa strumenti base
apt install -y \
    curl \
    wget \
    vim \
    git \
    net-tools \
    htop \
    build-essential \
    software-properties-common \
    ca-certificates \
    gnupg \
    lsb-release
```

### 1.3 Configurazione Firewall

```bash
# Installa ufw
apt install -y ufw

# Configura regole
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp     # SSH
ufw allow 80/tcp     # HTTP
ufw allow 443/tcp    # HTTPS
ufw allow 8000/tcp   # Django API
ufw allow 8001/tcp   # WebSocket
ufw allow 3000/tcp   # React (opzionale, solo per dev)

# Abilita firewall
ufw enable
ufw status
```

---

## 2. Installazione PostgreSQL

### 2.1 Installa PostgreSQL 15

```bash
# Installa PostgreSQL
apt install -y postgresql postgresql-contrib

# Verifica installazione
systemctl status postgresql
psql --version
```

### 2.2 Configura Database

```bash
# Switch a utente postgres
su - postgres

# Accedi a PostgreSQL
psql

# Crea database e utente
CREATE DATABASE firedog;
CREATE USER firedog WITH PASSWORD 'ChangeMe_SecurePassword';
ALTER ROLE firedog SET client_encoding TO 'utf8';
ALTER ROLE firedog SET default_transaction_isolation TO 'read committed';
ALTER ROLE firedog SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE firedog TO firedog;

# Esci
\q
exit
```

### 2.3 Configura Accesso Remoto (opzionale)

```bash
# Modifica postgresql.conf
vim /etc/postgresql/15/main/postgresql.conf

# Trova e modifica:
listen_addresses = 'localhost'  # O '*' per accesso remoto

# Modifica pg_hba.conf
vim /etc/postgresql/15/main/pg_hba.conf

# Aggiungi:
# host    firedog         firedog         127.0.0.1/32            md5

# Riavvia PostgreSQL
systemctl restart postgresql
```

### 2.4 Test Connessione

```bash
# Test connessione
psql -h localhost -U firedog -d firedog
# Password: ChangeMe_SecurePassword

# Se connesso con successo:
\dt
\q
```

---

## 3. Installazione Redis

### 3.1 Installa Redis

```bash
# Installa Redis
apt install -y redis-server

# Verifica installazione
systemctl status redis-server
redis-cli --version
```

### 3.2 Configura Redis

```bash
# Modifica configurazione
vim /etc/redis/redis.conf

# Trova e modifica/aggiungi:
bind 127.0.0.1
protected-mode yes
port 6379
requirepass ChangeMe_RedisPassword

# Riavvia Redis
systemctl restart redis-server
systemctl enable redis-server
```

### 3.3 Test Redis

```bash
# Test connessione
redis-cli

# Autentica (se hai impostato password)
AUTH ChangeMe_RedisPassword

# Test
PING
# Risposta: PONG

# Esci
exit
```

---

## 4. Installazione Python e Backend Django

### 4.1 Installa Python 3.11+

```bash
# Installa Python e dipendenze
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libpq-dev \
    pkg-config

# Verifica versione (deve essere >= 3.11)
python3 --version
```

### 4.2 Crea Utente Sistema per FireDog

```bash
# Crea utente dedicato
useradd -r -m -s /bin/bash firedog

# Crea directory applicazione
mkdir -p /opt/firedog
chown firedog:firedog /opt/firedog
```

### 4.3 Clone Repository

```bash
# Switch a utente firedog
su - firedog

# Clone repository
cd /opt/firedog
git clone https://github.com/Dognet-Technologies/firedog.git .

# Oppure se hai già il codice:
# rsync -av /path/to/firedog/ /opt/firedog/
```

### 4.4 Crea Virtual Environment

```bash
# Come utente firedog
cd /opt/firedog/backend

# Crea virtualenv
python3 -m venv venv

# Attiva virtualenv
source venv/bin/activate

# Aggiorna pip
pip install --upgrade pip setuptools wheel
```

### 4.5 Installa Dipendenze Python

```bash
# Assicurati che venv sia attivo
source /opt/firedog/backend/venv/bin/activate

# IMPORTANTE: Con Python 3.13, psycopg2-binary non è compatibile
# Usa psycopg (psycopg3) invece
cd /opt/firedog/backend

# Installa dipendenze base
pip install \
    django \
    djangorestframework \
    django-cors-headers \
    'psycopg[binary]' \
    channels \
    channels-redis \
    daphne \
    'celery[redis]' \
    redis \
    cryptography \
    python-dotenv \
    gunicorn \
    django-filter \
    djangorestframework-simplejwt \
    django-celery-beat \
    django-celery-results \
    paramiko \
    websockets \
    psutil \
    requests \
    python-decouple \
    pyyaml \
    pillow \
    pyjwt

# Se requirements.txt esiste ma contiene psycopg2-binary,
# installa le dipendenze manualmente come sopra
```

### 4.6 Configura Django Settings

```bash
# Torna come root
exit

# Crea file di configurazione ambiente
cat > /opt/firedog/backend/.env << 'EOF'
# Django Configuration
DJANGO_SECRET_KEY=changeme_generate_random_secret_key_here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-server-ip,localhost,127.0.0.1,firedog-server

# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=firedog
DB_USER=firedog
DB_PASSWORD=ChangeMe_SecurePassword
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=ChangeMe_RedisPassword

# Celery
CELERY_BROKER_URL=redis://:ChangeMe_RedisPassword@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:ChangeMe_RedisPassword@localhost:6379/0

# WebSocket
CHANNEL_LAYERS_HOST=redis://:ChangeMe_RedisPassword@localhost:6379/1
EOF

# Imposta permessi
chown firedog:firedog /opt/firedog/backend/.env
chmod 600 /opt/firedog/backend/.env
```

**Genera DJANGO_SECRET_KEY**:

```bash
# Genera chiave sicura
python3 << EOF
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
EOF

# Copia l'output e sostituisci in .env
vim /opt/firedog/backend/.env
```

### 4.6.1 Correggi Encoding File Python (IMPORTANTE)

```bash
# IMPORTANTE: Alcuni file Python potrebbero avere encoding ISO-8859-1
# invece di UTF-8, causando errori di sintassi con Python 3.13

# Come root, verifica e converti file con encoding errato
cd /opt/firedog/backend

# Converti file agent_manager/tasks.py se necessario
if file -i agent_manager/tasks.py | grep -q 'iso-8859'; then
    iconv -f ISO-8859-1 -t UTF-8 agent_manager/tasks.py -o agent_manager/tasks.py.utf8
    mv agent_manager/tasks.py.utf8 agent_manager/tasks.py
    chown firedog:firedog agent_manager/tasks.py
fi

# Verifica altri file Python se necessario
find . -name "*.py" -type f -exec file -i {} \; | grep iso-8859 | cut -d: -f1 | while read f; do
    echo "Converting $f to UTF-8..."
    iconv -f ISO-8859-1 -t UTF-8 "$f" -o "${f}.utf8"
    mv "${f}.utf8" "$f"
    chown firedog:firedog "$f"
done
```

### 4.6.2 Configura Django Settings per HTTP (senza HTTPS)

```bash
# IMPORTANTE: Per installazioni senza SSL/HTTPS, devi disabilitare
# i redirect HTTPS e configurare CORS correttamente

cd /opt/firedog/backend

# Disabilita SECURE_SSL_REDIRECT
sed -i 's/SECURE_SSL_REDIRECT = True/SECURE_SSL_REDIRECT = False/' firedog/settings.py
sed -i 's/CSRF_COOKIE_SECURE = True/CSRF_COOKIE_SECURE = False/' firedog/settings.py
sed -i 's/SESSION_COOKIE_SECURE = True/SESSION_COOKIE_SECURE = False/' firedog/settings.py

# Aggiungi IP del server a CORS_ALLOWED_ORIGINS
# Trova la riga CORS_ALLOWED_ORIGINS = [ e aggiungi il tuo IP
# Esempio per IP 10.99.201.6:
sed -i '/CORS_ALLOWED_ORIGINS = \[/a\    "http://10.99.201.6",' firedog/settings.py

# Nota: Sostituisci 10.99.201.6 con il tuo IP server reale
```

### 4.6.3 Configura Redis per WebSocket (CHANNEL_LAYERS)

```bash
# IMPORTANTE: CHANNEL_LAYERS deve includere la password Redis

cd /opt/firedog/backend

# Aggiorna CHANNEL_LAYERS con autenticazione Redis
# Modifica firedog/settings.py manualmente o usa sed:
python3 << 'PYFIX'
import re

with open('firedog/settings.py', 'r') as f:
    content = f.read()

# Trova e sostituisci CHANNEL_LAYERS
old_pattern = r'CHANNEL_LAYERS = \{[^}]+\{[^}]+\"hosts\": \[[^\]]+\]'
new_config = '''CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": ["redis://:FireDog2024!RedisPass@127.0.0.1:6379/1"]'''

content = re.sub(old_pattern, new_config, content)

with open('firedog/settings.py', 'w') as f:
    f.write(content)

print("CHANNEL_LAYERS updated with Redis authentication")
PYFIX

# NOTA: Assicurati che la password Redis corrisponda a quella in .env
```

### 4.6.4 Correggi WSGI Configuration

```bash
# IMPORTANTE: Il file wsgi.py potrebbe contenere configurazione ASGI
# invece di WSGI, causando errori con Gunicorn

cd /opt/firedog/backend

# Backup originale
cp firedog/wsgi.py firedog/wsgi.py.bak

# Crea WSGI corretto
cat > firedog/wsgi.py << 'WSGI'
"""
WSGI config for firedog project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'firedog.settings')

application = get_wsgi_application()
WSGI

chown firedog:firedog firedog/wsgi.py
```

### 4.7 Esegui Migrazioni Database

```bash
# Come utente firedog
su - firedog
cd /opt/firedog/backend
source venv/bin/activate

# NOTA: Se ci sono conflitti di migrazione (agent_manager),
# rimuovi la migrazione conflittuale:
if [ -f agent_manager/migrations/0001_add_encrypted_key_field.py ]; then
    rm agent_manager/migrations/0001_add_encrypted_key_field.py
fi

# Esegui migrazioni
python manage.py migrate

# Crea superuser
python manage.py createsuperuser
# Username: admin
# Email: admin@firedog.local
# Password: [password sicura]

# Raccogli file statici
python manage.py collectstatic --noinput

# Esci
exit
```

---

## 5. Configurazione Servizi Systemd

### 5.1 Servizio Django (Daphne per WebSocket)

```bash
# Come root
cat > /etc/systemd/system/firedog-daphne.service << 'EOF'
[Unit]
Description=FireDog Daphne (Django Channels WebSocket)
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=firedog
Group=firedog
WorkingDirectory=/opt/firedog/backend
Environment="PATH=/opt/firedog/backend/venv/bin"
EnvironmentFile=/opt/firedog/backend/.env
ExecStart=/opt/firedog/backend/venv/bin/daphne -b 0.0.0.0 -p 8001 firedog.asgi:application

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### 5.2 Servizio Django (Gunicorn per API REST)

```bash
cat > /etc/systemd/system/firedog-gunicorn.service << 'EOF'
[Unit]
Description=FireDog Gunicorn (Django REST API)
After=network.target postgresql.service redis-server.service

[Service]
Type=notify
User=firedog
Group=firedog
WorkingDirectory=/opt/firedog/backend
Environment="PATH=/opt/firedog/backend/venv/bin"
EnvironmentFile=/opt/firedog/backend/.env
ExecStart=/opt/firedog/backend/venv/bin/gunicorn \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    --timeout 60 \
    --access-logfile /var/log/firedog/gunicorn-access.log \
    --error-logfile /var/log/firedog/gunicorn-error.log \
    firedog.wsgi:application

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### 5.3 Servizio Celery Worker

```bash
cat > /etc/systemd/system/firedog-celery.service << 'EOF'
[Unit]
Description=FireDog Celery Worker
After=network.target postgresql.service redis-server.service

[Service]
Type=forking
User=firedog
Group=firedog
WorkingDirectory=/opt/firedog/backend
Environment="PATH=/opt/firedog/backend/venv/bin"
EnvironmentFile=/opt/firedog/backend/.env
ExecStart=/opt/firedog/backend/venv/bin/celery -A firedog worker \
    --loglevel=info \
    --logfile=/var/log/firedog/celery-worker.log \
    --pidfile=/var/run/firedog/celery-worker.pid

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### 5.4 Servizio Celery Beat (Scheduler)

```bash
cat > /etc/systemd/system/firedog-celery-beat.service << 'EOF'
[Unit]
Description=FireDog Celery Beat (Scheduler)
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=firedog
Group=firedog
WorkingDirectory=/opt/firedog/backend
Environment="PATH=/opt/firedog/backend/venv/bin"
EnvironmentFile=/opt/firedog/backend/.env
ExecStart=/opt/firedog/backend/venv/bin/celery -A firedog beat \
    --loglevel=info \
    --logfile=/var/log/firedog/celery-beat.log \
    --pidfile=/var/run/firedog/celery-beat.pid

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### 5.5 Crea Directory Log e PID

```bash
# Crea directory
mkdir -p /var/log/firedog
mkdir -p /var/run/firedog

# Imposta permessi
chown -R firedog:firedog /var/log/firedog
chown -R firedog:firedog /var/run/firedog
```

### 5.6 Abilita e Avvia Servizi Backend

```bash
# Ricarica systemd
systemctl daemon-reload

# Abilita servizi
systemctl enable firedog-gunicorn
systemctl enable firedog-daphne
systemctl enable firedog-celery
systemctl enable firedog-celery-beat

# Avvia servizi
systemctl start firedog-gunicorn
systemctl start firedog-daphne
systemctl start firedog-celery
systemctl start firedog-celery-beat

# Verifica stato
systemctl status firedog-gunicorn
systemctl status firedog-daphne
systemctl status firedog-celery
systemctl status firedog-celery-beat
```

---

## 6. Installazione Node.js e Frontend React

### 6.1 Installa Node.js 20 LTS

```bash
# Installa Node.js 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# Verifica installazione
node --version
npm --version
```

### 6.2 Build Frontend

```bash
# Come utente firedog
su - firedog
cd /opt/firedog/frontend

# Installa dipendenze
npm install

# Crea file .env per frontend
cat > .env << 'EOF'
REACT_APP_API_URL=http://your-server-ip:8000/api
REACT_APP_WS_URL=ws://your-server-ip:8001
EOF

# Build production
npm run build

# Esci
exit
```

### 6.3 Servizio Frontend (Serve statico con Nginx - vedi sezione 7)

Oppure per development:

```bash
cat > /etc/systemd/system/firedog-frontend.service << 'EOF'
[Unit]
Description=FireDog React Frontend (Development)
After=network.target

[Service]
Type=simple
User=firedog
Group=firedog
WorkingDirectory=/opt/firedog/frontend
Environment="PATH=/usr/bin"
ExecStart=/usr/bin/npm start

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Abilita e avvia (solo per dev)
systemctl enable firedog-frontend
systemctl start firedog-frontend
```

**Nota**: In produzione, usa Nginx per servire il frontend (vedi sezione 7).

---

## 7. Configurazione Nginx (Produzione)

### 7.1 Installa Nginx

```bash
apt install -y nginx
```

### 7.2 Configura Nginx

```bash
cat > /etc/nginx/sites-available/firedog << 'EOF'
# Frontend (React build)
server {
    listen 80;
    server_name your-domain.com your-server-ip;

    # Frontend statico
    location / {
        root /opt/firedog/frontend/build;
        try_files $uri $uri/ /index.html;

        # Cache statico
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeout
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # WebSocket per agent
    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Timeout lunghi per WebSocket persistente
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
    }

    # Django static files
    location /static/ {
        alias /opt/firedog/backend/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Django media files
    location /media/ {
        alias /opt/firedog/backend/media/;
    }
}
EOF

# Abilita sito
ln -s /etc/nginx/sites-available/firedog /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Test configurazione
nginx -t

# Riavvia Nginx
systemctl restart nginx
systemctl enable nginx
```

### 7.3 Correggi Path Static Files per React Frontend (IMPORTANTE)

**NOTA**: Il file Nginx sopra punta `/static/` a `/opt/firedog/backend/staticfiles/`, ma i file JS/CSS di React sono in `/opt/firedog/frontend/build/static/`. Devi correggere:

```bash
# Modifica configurazione Nginx
vim /etc/nginx/sites-available/firedog

# Trova la sezione:
#   location /static/ {
#       alias /opt/firedog/backend/staticfiles/;
#
# Cambia in:
#   location /static/ {
#       alias /opt/firedog/frontend/build/static/;

# Oppure usa sed per modificare automaticamente:
sed -i 's|alias /opt/firedog/backend/staticfiles/|alias /opt/firedog/frontend/build/static/|' /etc/nginx/sites-available/firedog

# Verifica configurazione
nginx -t

# Riavvia Nginx
systemctl restart nginx
```

**Spiegazione**: Il frontend React viene buildato in `/opt/firedog/frontend/build/` e i suoi static files (JS, CSS, immagini) sono in `build/static/`. Django staticfiles sono separati e servono solo per l'admin panel.

### 7.4 Configurazione SSL con Let's Encrypt (Opzionale)

```bash
# Installa Certbot
apt install -y certbot python3-certbot-nginx

# Ottieni certificato SSL
certbot --nginx -d your-domain.com

# Rinnovo automatico (già configurato)
systemctl status certbot.timer
```

---

## 8. Verifica Installazione

### 8.1 Verifica Servizi

```bash
# Stato tutti i servizi
systemctl status postgresql
systemctl status redis-server
systemctl status firedog-gunicorn
systemctl status firedog-daphne
systemctl status firedog-celery
systemctl status firedog-celery-beat
systemctl status nginx
```

### 8.2 Verifica Log

```bash
# Backend API
tail -f /var/log/firedog/gunicorn-error.log

# WebSocket
journalctl -u firedog-daphne -f

# Celery
tail -f /var/log/firedog/celery-worker.log

# Nginx
tail -f /var/log/nginx/error.log
```

### 8.3 Test Connettività

```bash
# Test API
curl http://localhost:8000/api/

# Test Frontend
curl http://localhost/

# Test database
su - firedog -c "cd /opt/firedog/backend && source venv/bin/activate && python manage.py dbshell"
```

### 8.4 Accesso Web Interface

Apri browser: `http://your-server-ip/`

Login con credenziali superuser.

---

## 9. Generazione API Key per Agent

1. Accedi alla web interface
2. Vai su **Settings** → **General**
3. Sezione **Agent API Keys** → **Generate New API Key**
4. **COPIA LA CHIAVE** e salvala

---

## 10. Backup e Manutenzione

### 10.1 Backup Database

```bash
cat > /opt/firedog/scripts/backup-db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/firedog/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
sudo -u postgres pg_dump firedog | gzip > $BACKUP_DIR/firedog_$DATE.sql.gz

# Mantieni ultimi 30 backup
find $BACKUP_DIR -name "firedog_*.sql.gz" -mtime +30 -delete

echo "Backup completato: firedog_$DATE.sql.gz"
EOF

chmod +x /opt/firedog/scripts/backup-db.sh

# Crontab per backup giornaliero
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/firedog/scripts/backup-db.sh") | crontab -
```

### 10.2 Monitoraggio

```bash
# Script di health check
cat > /opt/firedog/scripts/health-check.sh << 'EOF'
#!/bin/bash

echo "=== FireDog Health Check ==="
echo ""

# PostgreSQL
echo -n "PostgreSQL: "
systemctl is-active postgresql && echo "OK" || echo "FAIL"

# Redis
echo -n "Redis: "
systemctl is-active redis-server && echo "OK" || echo "FAIL"

# Gunicorn
echo -n "Gunicorn (API): "
systemctl is-active firedog-gunicorn && echo "OK" || echo "FAIL"

# Daphne
echo -n "Daphne (WebSocket): "
systemctl is-active firedog-daphne && echo "OK" || echo "FAIL"

# Celery
echo -n "Celery Worker: "
systemctl is-active firedog-celery && echo "OK" || echo "FAIL"

# Celery Beat
echo -n "Celery Beat: "
systemctl is-active firedog-celery-beat && echo "OK" || echo "FAIL"

# Nginx
echo -n "Nginx: "
systemctl is-active nginx && echo "OK" || echo "FAIL"

echo ""
echo "=== Disk Usage ==="
df -h | grep -E '(Filesystem|/dev/)'

echo ""
echo "=== Memory Usage ==="
free -h
EOF

chmod +x /opt/firedog/scripts/health-check.sh
```

### 10.3 Aggiornamento FireDog

```bash
# Script aggiornamento
cat > /opt/firedog/scripts/update.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Aggiornamento FireDog ==="

# Backup
/opt/firedog/scripts/backup-db.sh

# Ferma servizi
systemctl stop firedog-gunicorn
systemctl stop firedog-daphne
systemctl stop firedog-celery
systemctl stop firedog-celery-beat

# Aggiorna codice
cd /opt/firedog
su - firedog -c "cd /opt/firedog && git pull"

# Aggiorna dipendenze backend
su - firedog -c "cd /opt/firedog/backend && source venv/bin/activate && pip install -r requirements.txt --upgrade"

# Migrazioni
su - firedog -c "cd /opt/firedog/backend && source venv/bin/activate && python manage.py migrate"

# Collectstatic
su - firedog -c "cd /opt/firedog/backend && source venv/bin/activate && python manage.py collectstatic --noinput"

# Aggiorna frontend
su - firedog -c "cd /opt/firedog/frontend && npm install && npm run build"

# Riavvia servizi
systemctl start firedog-gunicorn
systemctl start firedog-daphne
systemctl start firedog-celery
systemctl start firedog-celery-beat

echo "=== Aggiornamento completato ==="
EOF

chmod +x /opt/firedog/scripts/update.sh
```

---

## 11. Troubleshooting

### Servizio non si avvia

```bash
# Controlla log systemd
journalctl -u firedog-gunicorn -n 50
journalctl -u firedog-daphne -n 50

# Controlla log applicazione
tail -f /var/log/firedog/gunicorn-error.log

# Testa manualmente
su - firedog
cd /opt/firedog/backend
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

### Errore connessione database

```bash
# Verifica PostgreSQL
systemctl status postgresql
sudo -u postgres psql -c "\l" | grep firedog

# Test connessione
psql -h localhost -U firedog -d firedog
```

### WebSocket non funziona

```bash
# Verifica Daphne
systemctl status firedog-daphne
journalctl -u firedog-daphne -f

# Verifica Redis
redis-cli
AUTH your_password
PING
```

### Errori permessi

```bash
# Verifica ownership
chown -R firedog:firedog /opt/firedog
chown -R firedog:firedog /var/log/firedog
chown -R firedog:firedog /var/run/firedog

# Verifica permessi .env
chmod 600 /opt/firedog/backend/.env
```

### Errore "ProtocolTypeRouter.__call__() missing 1 required positional argument: 'send'"

**Problema**: Gunicorn fallisce con errore TypeError su ProtocolTypeRouter

**Causa**: Il file `wsgi.py` contiene configurazione ASGI invece di WSGI

**Soluzione**: Vedi sezione **4.6.4** - Correggi WSGI Configuration

### Frontend mostra schermata bianca

**Problema**: Accedendo a `http://server-ip/` si vede solo una pagina bianca

**Possibili cause e soluzioni**:

```bash
# 1. Verifica che il frontend sia stato buildato
ls -la /opt/firedog/frontend/build/
# Dovresti vedere: index.html, static/, asset-manifest.json

# 2. Se build/ è vuoto, rebuilda il frontend
cd /opt/firedog/frontend
sudo -u firedog npm install
sudo -u firedog npm run build

# 3. Verifica che Nginx punti al path corretto
cat /etc/nginx/sites-available/firedog | grep "root"
# Dovrebbe essere: root /opt/firedog/frontend/build;

# 4. Verifica che static files siano accessibili
curl http://localhost/static/js/main.*.js
# Non dovrebbe dare 404

# 5. Se hai 301 redirect verso HTTPS, disabilita SSL redirect
# Vedi sezione 4.6.2
```

### Login failed / CORS errors

**Problema**: Login fallisce o console browser mostra errori CORS

**Soluzione**:

```bash
# 1. Verifica CORS_ALLOWED_ORIGINS in settings.py
grep -A5 "CORS_ALLOWED_ORIGINS" /opt/firedog/backend/firedog/settings.py

# Deve includere l'IP del server:
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:3000",
#     "http://127.0.0.1:3000",
#     "http://10.99.201.6",  # <-- Il tuo IP
# ]

# 2. Se manca, vedi sezione 4.6.2 per aggiungerlo

# 3. Riavvia Gunicorn
systemctl restart firedog-gunicorn
```

### Redis authentication error nel WebSocket

**Problema**: Daphne log mostra `redis.exceptions.AuthenticationError`

**Soluzione**: Vedi sezione **4.6.3** - Configura Redis per WebSocket (CHANNEL_LAYERS)

### Migration conflicts

**Problema**: `python manage.py migrate` fallisce con "Conflicting migrations detected"

**Soluzione**:

```bash
cd /opt/firedog/backend

# Trova il file conflicting indicato nell'errore
# Esempio: 0001_add_encrypted_key_field.py in agent_manager

# Rimuovi il file conflicting più vecchio
rm agent_manager/migrations/0001_add_encrypted_key_field.py

# Esegui nuovamente migrate
sudo -u firedog venv/bin/python manage.py migrate
```

---

## 12. Comandi Utili

```bash
# Avvia tutti i servizi
systemctl start firedog-gunicorn firedog-daphne firedog-celery firedog-celery-beat

# Ferma tutti i servizi
systemctl stop firedog-gunicorn firedog-daphne firedog-celery firedog-celery-beat

# Riavvia tutti i servizi
systemctl restart firedog-gunicorn firedog-daphne firedog-celery firedog-celery-beat

# Stato servizi
systemctl status firedog-*

# Log in tempo reale
tail -f /var/log/firedog/*.log

# Health check
/opt/firedog/scripts/health-check.sh

# Backup manuale
/opt/firedog/scripts/backup-db.sh

# Aggiornamento
/opt/firedog/scripts/update.sh
```

---

## 13. Sicurezza

### 13.1 Firewall

```bash
ufw status
ufw allow from trusted-ip to any port 8000  # Limita accesso API
ufw allow from trusted-ip to any port 8001  # Limita accesso WebSocket
```

### 13.2 Fail2Ban (Opzionale)

```bash
apt install -y fail2ban

cat > /etc/fail2ban/jail.d/firedog.conf << 'EOF'
[firedog]
enabled = true
port = 80,443
logpath = /var/log/firedog/gunicorn-access.log
maxretry = 5
bantime = 3600
EOF

systemctl restart fail2ban
```

---

## Installazione Completata! 🎉

Ora puoi procedere con l'installazione degli agent sui target seguendo [AGENT_INSTALLATION.md](./AGENT_INSTALLATION.md).

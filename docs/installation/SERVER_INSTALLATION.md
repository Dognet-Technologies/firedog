# Installazione FireDog Server

Guida completa per l'installazione del server FireDog su Debian 12 (Bookworm).

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
- **Network**: 1+ interfacce di rete

### Software
- **OS**: Debian 12 (Bookworm) - installazione minimal
- **Network**: Indirizzo IP statico configurato
- **Internet**: Connessione per scaricare pacchetti

---

## 1. Preparazione Sistema Base

### 1.1 Installazione Debian 12

Scarica l'ISO di Debian 12 da: https://www.debian.org/download

Durante l'installazione:
- Scegli **"Debian GNU/Linux 12 (Bookworm)"**
- Configura hostname: `firedog-server` (o nome a scelta)
- Configura rete con IP statico
- Non installare ambiente desktop
- Installa solo: **SSH server** e **standard system utilities**

### 1.2 Aggiornamento Sistema

```bash
# Login come root o usa sudo
su -

# Aggiorna il sistema
apt update
apt upgrade -y
apt install -y curl wget vim git net-tools
```

### 1.3 Configurazione Firewall di Base (opzionale)

```bash
# Installa ufw
apt install -y ufw

# Configura regole base
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 8000/tcp  # Django dev server (se necessario)
ufw allow 3000/tcp  # React dev server (se necessario)

# Abilita firewall
ufw enable
```

---

## 2. Installazione Docker e Docker Compose

FireDog utilizza Docker per semplificare il deployment.

### 2.1 Rimozione Vecchie Versioni (se presenti)

```bash
apt remove -y docker docker-engine docker.io containerd runc
```

### 2.2 Installazione Docker

```bash
# Installa dipendenze
apt update
apt install -y ca-certificates curl gnupg lsb-release

# Aggiungi chiave GPG ufficiale Docker
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Aggiungi repository Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Installa Docker Engine
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verifica installazione
docker --version
docker compose version
```

### 2.3 Configurazione Docker

```bash
# Avvia Docker all'avvio del sistema
systemctl enable docker
systemctl start docker

# Aggiungi utente corrente al gruppo docker (opzionale)
usermod -aG docker $USER
# Riloggare per applicare le modifiche
```

---

## 3. Installazione FireDog

### 3.1 Clone Repository

```bash
# Crea directory per il progetto
mkdir -p /opt/firedog
cd /opt/firedog

# Clona repository (sostituisci con il tuo URL)
git clone https://github.com/Dognet-Technologies/firedog.git .

# Oppure se hai già scaricato il codice
# rsync -av /path/to/firedog/ /opt/firedog/
```

### 3.2 Configurazione Variabili d'Ambiente

```bash
# Crea file .env dalla template
cp .env.example .env

# Modifica il file .env con i tuoi valori
vim .env
```

Configura almeno questi parametri:

```bash
# Database
POSTGRES_DB=firedog
POSTGRES_USER=firedog
POSTGRES_PASSWORD=ChangeMe_SecurePassword_Here

# Django
DJANGO_SECRET_KEY=ChangeMe_GenerateRandomKey_Here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-server-ip,localhost,127.0.0.1

# Redis
REDIS_PASSWORD=ChangeMe_RedisPassword_Here

# WebSocket (se necessario)
WEBSOCKET_PORT=8001
```

Per generare una `DJANGO_SECRET_KEY` sicura:

```bash
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### 3.3 Build e Avvio Containers

```bash
cd /opt/firedog

# Build delle immagini
docker compose build

# Avvio containers in background
docker compose up -d

# Verifica che i container siano attivi
docker compose ps
```

Dovresti vedere i seguenti container attivi:
- `firedog-backend` (Django + Channels)
- `firedog-frontend` (React)
- `firedog-db` (PostgreSQL)
- `firedog-redis` (Redis)
- `firedog-celery` (Celery worker)
- `firedog-celery-beat` (Celery scheduler)

### 3.4 Inizializzazione Database

```bash
# Esegui le migrazioni
docker exec -it firedog-backend python manage.py migrate

# Crea superuser
docker exec -it firedog-backend python manage.py createsuperuser
# Inserisci username, email e password
```

### 3.5 Verifica Installazione

```bash
# Controlla i log
docker compose logs -f backend

# Verifica connessione database
docker exec -it firedog-db psql -U firedog -d firedog -c "SELECT version();"

# Testa accesso web
curl http://localhost:8000/api/
curl http://localhost:3000/
```

---

## 4. Configurazione Iniziale FireDog

### 4.1 Accesso Web Interface

Apri browser e vai a: `http://your-server-ip:3000`

Login con le credenziali superuser create precedentemente.

### 4.2 Generazione API Key per Agent

1. Vai su **Settings** → **General**
2. Nella sezione **Agent API Keys**, clicca su **Generate New API Key**
3. **IMPORTANTE**: Copia la chiave generata e salvala in un posto sicuro
4. Questa chiave sarà necessaria per configurare gli agent sui target

**Nota**: La chiave può essere recuperata successivamente inserendo la password admin.

---

## 5. Configurazione Avanzata (Opzionale)

### 5.1 Nginx Reverse Proxy

Per esporre FireDog su porta 80/443 con SSL:

```bash
apt install -y nginx certbot python3-certbot-nginx

# Crea configurazione Nginx
cat > /etc/nginx/sites-available/firedog << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

# Abilita sito
ln -s /etc/nginx/sites-available/firedog /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# Ottieni certificato SSL (opzionale)
certbot --nginx -d your-domain.com
```

### 5.2 Avvio Automatico

Docker Compose è già configurato per riavviare i container automaticamente.

Per verificare:

```bash
docker compose ps
# La colonna "RESTART" dovrebbe mostrare "always" o "unless-stopped"
```

### 5.3 Backup Automatico Database

Crea script di backup:

```bash
cat > /opt/firedog/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/firedog/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

docker exec firedog-db pg_dump -U firedog firedog | gzip > $BACKUP_DIR/firedog_$DATE.sql.gz

# Mantieni solo ultimi 30 backup
find $BACKUP_DIR -name "firedog_*.sql.gz" -mtime +30 -delete

echo "Backup completato: firedog_$DATE.sql.gz"
EOF

chmod +x /opt/firedog/backup.sh

# Aggiungi a crontab (backup giornaliero alle 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/firedog/backup.sh") | crontab -
```

---

## 6. Troubleshooting

### Container non si avvia

```bash
# Verifica log
docker compose logs backend
docker compose logs db

# Verifica risorse
df -h
free -m
```

### Problemi di connessione database

```bash
# Accedi al container database
docker exec -it firedog-db psql -U firedog -d firedog

# Verifica connettività
docker exec firedog-backend python manage.py dbshell
```

### Reset completo (ATTENZIONE: cancella tutti i dati)

```bash
cd /opt/firedog

# Ferma tutti i container
docker compose down

# Rimuovi volumi (DATI CANCELLATI!)
docker compose down -v

# Riavvia tutto
docker compose up -d
docker exec -it firedog-backend python manage.py migrate
docker exec -it firedog-backend python manage.py createsuperuser
```

---

## 7. Comandi Utili

```bash
# Avvia FireDog
cd /opt/firedog && docker compose up -d

# Ferma FireDog
cd /opt/firedog && docker compose down

# Riavvia FireDog
cd /opt/firedog && docker compose restart

# Vedi log in tempo reale
cd /opt/firedog && docker compose logs -f

# Vedi log di un singolo servizio
docker compose logs -f backend
docker compose logs -f celery

# Accedi alla shell Django
docker exec -it firedog-backend python manage.py shell

# Accedi al database
docker exec -it firedog-db psql -U firedog -d firedog

# Aggiorna FireDog (dopo git pull)
cd /opt/firedog
git pull
docker compose build
docker compose up -d
docker exec -it firedog-backend python manage.py migrate
```

---

## 8. Prossimi Passi

Dopo aver installato il server:

1. **Installa agent sui target**: Vedi [AGENT_INSTALLATION.md](./AGENT_INSTALLATION.md)
2. **Configura discovery**: Scansiona la rete per trovare target
3. **Configura gruppi**: Organizza i target in gruppi logici
4. **Configura regole firewall**: Definisci policy di sicurezza

---

## Support

Per problemi o domande:
- Issues: https://github.com/Dognet-Technologies/firedog/issues
- Documentazione completa: `/opt/firedog/docs/`

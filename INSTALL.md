# FireDog — Installazione del master

Guida all'installazione completa del server FireDog (backend Django + frontend
React + Celery + nginx). Procedura verificata da zero il 2026-07-02 su Linux
con Python 3.13 e Node 20.

> Per l'installazione **sui target** (firewall gestiti) vedi invece
> [README.md](README.md) e `firedog-package/install.sh`.

## Prerequisiti

| Componente | Versione testata | Note |
|---|---|---|
| Python | 3.11 – 3.13 | con `python3-venv` e toolchain C (`build-essential`, `libpq-dev`) |
| Node.js | 20.x | per build del frontend CRA |
| PostgreSQL | 15+ | database `firedog` |
| Redis | 7+ | broker Celery + channel layer |
| nginx | qualsiasi recente | serve il frontend e fa da proxy API/WS |

```bash
sudo apt install -y python3-venv build-essential libpq-dev postgresql redis-server nginx
```

## 1. Clone e database

```bash
git clone https://github.com/Dognet-Technologies/firedog.git
cd firedog

# Crea utente e database PostgreSQL
sudo -u postgres psql <<'SQL'
CREATE USER firedog WITH PASSWORD 'CAMBIAMI';
CREATE DATABASE firedog OWNER firedog;
SQL
```

## 2. Backend

```bash
cd backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# Configurazione: SENZA .env qualsiasi manage.py fallisce
# (decouple.UndefinedValueError su SECRET_KEY)
cp .env.example .env
#   → valorizza SECRET_KEY, DB_NAME, DB_USER, DB_PASSWORD

venv/bin/python manage.py migrate
venv/bin/python manage.py collectstatic --noinput
venv/bin/python manage.py createsuperuser
```

Verifica rapida: `venv/bin/python manage.py check` deve chiudere con
`System check identified no issues`.

> **Nota Python 3.13**: `psycopg2-binary` deve essere ≥ 2.9.10 (pin già
> aggiornato in requirements.txt). Versioni precedenti non compilano
> (`_PyInterpreterState_Get` rimossa dalla C-API).

## 3. Frontend

```bash
cd ../frontend
npm ci        # legacy-peer-deps=true è già impostato in .npmrc
npm run build # produce frontend/build servito da nginx
```

> **Nota peer-deps**: il progetto usa React 19 mentre
> `@testing-library/react@13` dichiara peer React 18: senza
> `legacy-peer-deps` npm ci fallisce con ERESOLVE. Il file `.npmrc`
> versionato risolve il problema per tutti.

## 4. Servizi systemd

Template pronti in [`deploy/`](deploy/) (percorsi basati su
`/home/microcyber/firedog`: adattali al tuo utente/percorso):

```bash
sudo cp deploy/firedog-backend.service   /etc/systemd/system/
sudo cp deploy/firedog-celery.service    /etc/systemd/system/
sudo cp deploy/firedog-celerybeat.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now firedog-backend firedog-celery firedog-celerybeat
```

| Servizio | Ruolo |
|---|---|
| `firedog-backend` | Daphne ASGI su `:8000` (API REST, MCP, WebSocket) |
| `firedog-celery` | worker Celery (task asincroni: install, fetch, analisi) |
| `firedog-celerybeat` | scheduler periodico (DatabaseScheduler) |

## 5. nginx

```bash
sudo cp deploy/nginx-firedog.conf /etc/nginx/sites-available/firedog
sudo ln -s /etc/nginx/sites-available/firedog /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

nginx serve `frontend/build` come SPA e fa da proxy verso Daphne per
`/api/`, `/admin/` e `/ws/` (WebSocket).

> **Nota permessi home directory**: nginx gira come `www-data` (o utente
> equivalente) e deve poter attraversare l'intero percorso fino a
> `frontend/build/index.html` e `backend/staticfiles/`. Se il clone è sotto
> `/home/<utente>` (come nei template `deploy/`) la home ha di norma
> permessi `750`: `www-data` non riesce ad attraversarla e nginx risponde
> `500 Internal Server Error` (log: `stat() ... failed (13: Permission
> denied)`, poi `rewrite or internal redirection cycle`). Prima della
> verifica finale:
> ```bash
> chmod o+x /home/<utente>
> chmod -R o+rX /home/<utente>/firedog/frontend/build
> chmod -R o+rX /home/<utente>/firedog/backend/staticfiles
> ```

## 6. Verifica finale

```bash
systemctl is-active firedog-backend firedog-celery firedog-celerybeat nginx redis-server postgresql
curl -s -o /dev/null -w '%{http_code}\n' http://localhost/            # 200
curl -s -o /dev/null -w '%{http_code}\n' http://localhost/api/token/  # 405 (solo POST)
```

Login UI: `http://<host>/` con l'utente creato al passo 2.

## Aggiornamenti

Usa [`update.sh`](update.sh): fa pull della branch configurata, rebuild del
frontend, `pip install` + `migrate` e riavvia i servizi. Richiede NOPASSWD
sudo per i soli restart (vedi commento in testa allo script).

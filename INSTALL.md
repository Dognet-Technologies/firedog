# FireDog — Installazione del master

Guida all'installazione completa del server FireDog (backend Django + frontend
React + Celery + nginx). Procedura verificata da zero il 2026-07-02 su Linux
con Python 3.13 e Node 20.

> Per l'installazione **sui target** (firewall gestiti) vedi invece
> [README.md](README.md) e `firedog-package/install.sh`.

## Install automatico: `deploy/install.sh`

```bash
git clone https://github.com/Dognet-Technologies/firedog.git
cd firedog
sudo ./deploy/install.sh
```

Esegue tutti i passi manuali descritti sotto, più la CA locale
dell'installazione, il certificato server firmato da lei e la configurazione
HTTPS di nginx (default — il browser avvisa "connessione non sicura" finché
non importi la CA, vedi [Certificato HTTPS e agent](#certificato-https-e-agent)).
Genera automaticamente `SECRET_KEY`, password del database e password
dell'utente admin se non passate esplicitamente. Nessuna password viene
stampata, perché con il `.deb` l'output finisce in `/var/log/apt/term.log`.
La password admin è in `/etc/sentinelsuite/firedog/initial-credentials`,
leggibile solo da root (`sudo cat …`). Il file si cancella da solo entro
pochi minuti dal cambio password, che va fatto al primo accesso. La password
del database resta solo in `backend/.env`.

Opzioni principali: `--server-name <ip-o-host>`, `--install-user <utente>`
(default: crea un utente di sistema dedicato `firedog`), `--skip-tls`
(nginx solo HTTP), `--tls-profile testing` (solo sviluppo e test interni:
certificati marcati TESTING, CA 12 mesi, server 6 mesi), `--force` (procede
anche se DB/utente esistono già).
`./deploy/install.sh --help` per l'elenco completo.

I passi manuali sotto restano come riferimento — utile per capire cosa fa
lo script, o per un'installazione passo-passo/debug di un run automatico
fallito.

## Installazione manuale

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

**Installazione da git clone**: usa [`update.sh`](update.sh) — fa pull della
branch configurata, rebuild del frontend, `pip install` + `migrate` e riavvia
i servizi. Richiede NOPASSWD sudo per i soli restart (vedi commento in testa
allo script).

> `update.sh` gira senza root e non tocca il certificato HTTPS. Su
> un'installazione da clone con il vecchio certificato self-signed
> (`/etc/ssl/firedog`, rifiutato da dog_agent 1.3+), dopo l'aggiornamento
> installa una volta lo strumento e il timer di rinnovo e migra il
> certificato (aggiungi `--name <ip-o-nome>` se il master ha cambiato
> indirizzo). Vedi [Certificato HTTPS e agent](#certificato-https-e-agent).
>
> ```bash
> sudo install -m 0755 deploy/firedog-tls /usr/local/sbin/firedog-tls
> sudo install -m 0644 deploy/firedog-tls-renew.service deploy/firedog-tls-renew.timer /etc/systemd/system/
> sudo systemctl daemon-reload && sudo systemctl enable --now firedog-tls-renew.timer
> sudo firedog-tls ensure
> ```

**Installazione da tarball di release o appliance OVA/qcow2** (nessuna
directory `.git` — `update.sh` non è applicabile, e il bottone "Verifica/
Installa aggiornamenti" del frontend risponde con un errore esplicito per lo
stesso motivo): scarica l'ultima release da GitHub e usa
[`deploy/upgrade.sh`](deploy/upgrade.sh) dalla directory estratta —
backup del DB, installazione dei nuovi artefatti (preserva `.env`), migration
con rollback automatico se falliscono, verifica finale.

```bash
tar xzf firedog-<tag>-linux-x86_64.tar.gz
cd firedog-<tag>-linux-x86_64
sudo ./deploy/upgrade.sh
```

## Certificato HTTPS e agent

Ogni installazione ha la propria CA, creata da `deploy/firedog-tls`
(installato in `/usr/local/sbin/firedog-tls`). La chiave della CA resta solo
sul master; la CA firma il certificato server (il solo IP o nome del master,
mai wildcard), che un timer giornaliero rinnova prima della scadenza senza
toccare agent e browser.

- Configurazione: `/etc/sentinelsuite/firedog/tls.conf` (`PROFILE`,
  `SERVER_NAME`, `MANAGED=no` per un certificato della propria PKI aziendale).
- Certificati: `/etc/sentinelsuite/firedog/tls/`, chiavi in `tls/private/`.
- Impronta e scadenze: Impostazioni > API Keys Agent > "Certificato del
  master", oppure `sudo firedog-tls info`.
- **dog_agent 1.3 e successivi** verificano il certificato del master:
  scarica la CA (`https://<master>/api/tls/ca.pem`), confronta l'impronta e
  impostala in `ca_cert` nella sezione `[agent]` di `agent.conf`. Se l'agent
  parla anche con altri prodotti della suite, metti le loro CA nello stesso
  file.
- **Browser**: importa la stessa CA come autorità per i siti web, oppure
  accetta l'avviso.
- **Il master ha cambiato IP**: `sudo firedog-tls ensure --name <nuovo-ip>`
  (stessa CA, nuovo certificato server; `SERVER_NAME` in `tls.conf` viene
  aggiornato da solo, così il rinnovo resta sul nuovo indirizzo). Negli agent va
  aggiornato solo `url`; aggiungi il nuovo IP a `ALLOWED_HOSTS` in
  `backend/.env`.
- **Nuova CA** (es. chiave compromessa): `sudo firedog-tls renew --force-ca`;
  la vecchia resta in `tls/private/legacy-*`, gli agent vanno riconfigurati.

**Aggiornando da una versione precedente** (certificato self-signed in
`/etc/ssl/firedog`), `upgrade.sh` crea la CA e il nuovo certificato e ripunta
nginx. Dopo l'aggiornamento il certificato è diverso: il browser chiede di
nuovo di accettarlo (una pagina già aperta va ricaricata, altrimenti i
salvataggi falliscono con un errore di connessione) e gli agent 1.3 vanno
configurati con la nuova CA.

## Domande frequenti

**Il browser dice "connessione non sicura".**
Il certificato è firmato dalla CA locale di questa installazione, che il
browser non conosce. Importa la CA (Impostazioni > API Keys Agent >
"Certificato del master", dopo aver confrontato l'impronta) oppure accetta
l'avviso.

**Dopo l'aggiornamento il salvataggio delle impostazioni fallisce con
"Connessione al master non riuscita".**
Il certificato è cambiato mentre la pagina era aperta e il browser rifiuta
le richieste senza mostrare l'avviso. Ricarica la pagina e accetta il nuovo
certificato.

**L'agent non si collega e nel log c'è `invalid peer certificate`.**
- `UnknownIssuer`: in `ca_cert` dell'agent manca la CA di questo master (o
  il master ha creato una CA nuova). Riscaricala da `/api/tls/ca.pem`.
- `Other(OtherError(CaUsedAsEndEntity))`: il master usa ancora il vecchio
  certificato self-signed; aggiorna FireDog (o, da clone git, migra a mano,
  vedi [Aggiornamenti](#aggiornamenti)).
- `NotValidForName`: `url` dell'agent usa un indirizzo diverso da quello del
  certificato; usa lo stesso, o rifai il certificato con `--name`.

Il manuale di dog_agent (`docs/MANUALE.md` nel suo repository) spiega
`ca_cert` e i messaggi dell'agent nel dettaglio.

**Il master ha cambiato IP e né browser né agent si collegano.**
`sudo firedog-tls ensure --name <nuovo-ip>`, nuovo IP in `ALLOWED_HOSTS` di
`backend/.env` (`sudo systemctl restart firedog-backend`), poi `url` negli
agent. La CA non cambia: gli agent non vanno riconfigurati.

**Voglio usare un certificato della mia PKI aziendale.**
In `/etc/sentinelsuite/firedog/tls.conf` metti `MANAGED=no` e punta nginx ai
tuoi file (`/etc/nginx/sites-available/firedog`). `firedog-tls` non toccherà
più nulla; negli agent `ca_cert` è la CA che ha firmato il tuo certificato.

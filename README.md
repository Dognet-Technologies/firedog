# 🛡️ FireDog

Piattaforma di gestione centralizzata del firewall per flotte di host Linux — policy DROP di default, regole distribuite in tempo reale, analisi del traffico con threat scoring, e un **server MCP** che espone tutto ad agenti AI autorizzati.

[![Release](https://img.shields.io/github/v/release/Dognet-Technologies/firedog)](https://github.com/Dognet-Technologies/firedog/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](#-licenza)

> **Guide di installazione:**
> - Master (backend Django + frontend React + Celery + nginx): [INSTALL.md](INSTALL.md)
> - Target (strumenti firewall + dog-agent + pairing col master): [INSTALL-TARGET.md](INSTALL-TARGET.md)
> - Ruoli, permessi e API: [ROLES_AND_PERMISSIONS.md](backend/ROLES_AND_PERMISSIONS.md)
>
> Installazione rapida di un target:
> ```bash
> curl -fsSL https://raw.githubusercontent.com/Dognet-Technologies/firedog/stabile/firedog-package/get-firedog.sh | sudo bash
> ```

## 🆕 Novità in v1.0.0

- **Server MCP ampliato** — tool di lettura *e scrittura* per regole, minacce, IP bloccati, traffico, network flow ([dettagli sotto](#-server-mcp)).
- **Supporto host multi-NIC** — un target può avere più interfacce di rete; le regole possono essere scoped su un'interfaccia specifica (`-i`/`-o`), con contatori rx/tx e selettore NIC nella UI.
- **Protezione SSH brute-force configurabile** — soglia/finestra personalizzabili, ban temporaneo o permanente via ipset persistente, gestibile con `firewall-manager --list-bans`/`--unban`.
- **`/etc/firewall/firedog.conf`** — nuovo file di configurazione target-side per interfacce monitorate e porte sempre aperte.
- **Supporto openSUSE/SLES** oltre a Debian/Ubuntu per l'installazione degli strumenti target.
- **Pulizia**: rimosso il vecchio meccanismo di gestione regole/installazione via SSH diretto (push dal master, terminale SSH nella UI) — il provisioning di un target è sempre self-service via `get-firedog.sh`, il dispatch delle regole avviene via WebSocket tramite [dog-agent](https://github.com/Dognet-Technologies/dog_agent).

Changelog completo: [release v1.0.0](https://github.com/Dognet-Technologies/firedog/releases/tag/v1.0.0).

## 🏗️ Architettura

FireDog è un sistema a **tre componenti**, ciascuno con un ruolo preciso:

| Componente | Dove gira | Cosa fa |
|---|---|---|
| **Master** | un host/VM dedicato | Backend Django + frontend React: policy editor, dashboard di traffico in tempo reale, API REST, **server MCP** |
| **Strumenti firewall** | ogni target, in `/opt/sentinelsuite/firedog` | `firewall-manager` (CLI regole), `traffic-analyzer` (threat scoring su PCAP), `firewall-init.sh` (policy DROP + protezioni) |
| **dog-agent** | ogni target, `/usr/bin/dog-agent` | Binario Rust statico condiviso con CyberSheppard/SentinelCore: pairing a 2 fasi col master, poi push di heartbeat/statistiche/minacce via WebSocket ed esecuzione dei comandi regola |

Le regole create sul master vengono **dispatchate all'agent via WebSocket** in tempo reale; se l'agent non è connesso restano persistite (`is_synced=false`) e si riconciliano alla riconnessione — nessun accesso SSH è mai coinvolto in questo percorso.

## 🤖 Server MCP

FireDog espone un server **[MCP](https://modelcontextprotocol.io) (Model Context Protocol)** che permette ad agenti AI autorizzati di consultare — e, con una chiave posseduta da un utente Admin, agire su — target, regole, minacce e traffico in modo programmatico.

- **Endpoint**: `POST /api/mcp` — JSON-RPC 2.0
- **Autenticazione**: header `Authorization: Bearer fd_<chiave>`, chiave generata da **Settings → API Keys MCP**. La chiave **eredita ruolo e permessi dell'utente che l'ha creata**: i tool marcati `[Admin]` nella tabella sotto funzionano solo con una chiave posseduta da un utente Admin, gli altri sono disponibili a qualunque chiave attiva.
- **Audit**: ogni azione di scrittura via MCP viene registrata in `AuditLog` con prefisso `"MCP <tool>: ..."`, distinguibile dalle modifiche fatte da UI.

<details>
<summary><strong>Esempio di chiamata</strong></summary>

```bash
curl -sk -X POST https://<master>/api/mcp \
  -H "Authorization: Bearer fd_xxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_threats",
      "arguments": {"severities": "critical,high", "min_score": 70}
    }
  }'
```
</details>

### Tool disponibili

| Tool | Cosa fa |
|---|---|
| `list_targets` | Elenca i target gestiti (stato, connectivity, versione firedog installata). Filtri: status, connection_type, hostname, ip_address |
| `get_target` | Dettaglio di un singolo target, incluso stato di connettività |
| `list_interfaces` | Elenca le interfacce di rete (NIC) dei target — supporto multi-homed |
| `list_rules` | Elenca le regole firewall iptables sui target |
| `get_rule` | Dettaglio di una singola regola per id |
| `create_rule` `[Admin]` | Crea una regola custom e la invia all'agent via WebSocket (se connesso) |
| `delete_rule` `[Admin]` | Elimina una regola per id e chiede all'agent di rimuoverla dal target |
| `list_threats` | Elenca le minacce rilevate, ordinate per data discendente. Filtri: severity, target_id, source_ip, is_blocked, is_resolved, min_score |
| `get_threat` | Dettaglio di una minaccia, inclusi i motivi dello score |
| `resolve_threat` `[Admin]` | Marca una minaccia come risolta (idempotente) |
| `list_blocked_ips` | Elenca gli IP bloccati sui target |
| `block_ip` `[Admin]` | Registra il blocco di un IP su un target |
| `unblock_ip` `[Admin]` | Sblocca un IP per id |
| `list_traffic_stats` | Snapshot periodici di traffico/volumi per target |
| `list_network_flows` | Peer remoti pubblici osservati nel traffico di un target |
| `get_policy_summary` | Rollup aggregato della postura firewall (target per stato, regole per tipo, ecc.) |

## 📋 Caratteristiche

- ✅ Policy DROP di default su INPUT/OUTPUT
- ✅ Protezioni avanzate: SYN flood, port scan, brute force SSH (soglia/ban configurabili)
- ✅ Logging separato INPUT/OUTPUT in formato PCAP con ulogd2
- ✅ Retention automatica con logrotate
- ✅ CLI Python per gestione regole (`firewall-manager`) e API REST dal master
- ✅ Analisi intelligente traffico con threat scoring
- ✅ Supporto host multi-NIC, regole scoped per interfaccia
- ✅ Server MCP per agenti AI (lettura e scrittura)
- ✅ Avvio automatico con systemd, Debian/Ubuntu e openSUSE/SLES
- ✅ Conforme OWASP/NIST security best practices

## 🚀 Installazione rapida

**Master (server web):**
```bash
git clone --branch v1.0.0 https://github.com/Dognet-Technologies/firedog.git
cd firedog && cat INSTALL.md
```

**Target (strumenti firewall — Debian/Ubuntu o openSUSE/SLES):**
```bash
curl -fsSL https://github.com/Dognet-Technologies/firedog/releases/latest/download/get-firedog.sh -o get-firedog.sh
less get-firedog.sh              # ispeziona prima di eseguire
sudo bash get-firedog.sh         # oppure: sudo bash get-firedog.sh --skip-init
```
> **Attenzione**: l'attivazione del firewall applica policy **DROP** su INPUT/OUTPUT. Assicurati di avere accesso console/seriale prima di confermare, o usa `--skip-init` e attiva dopo con `sudo firewall-init.sh && sudo systemctl enable --now firewall-fm`.

**dog-agent** (pairing target ↔ master): pacchetto `.deb`/`.rpm` dal repo [dog_agent](https://github.com/Dognet-Technologies/dog_agent/releases/latest).
```bash
sudo dpkg -i dog-agent_<versione>-1_amd64.deb      # Debian/Ubuntu
sudo zypper install ./dog-agent-<versione>-1.x86_64.rpm  # openSUSE/SLES
sudo nano /etc/dog-agent/agent.conf                # url master, api_key, ip/hostname/mac
sudo systemctl enable --now dog-agent
```

Guide complete, incluso il pairing a 2 fasi: [INSTALL.md](INSTALL.md) · [INSTALL-TARGET.md](INSTALL-TARGET.md).

## ⚙️ Configurazione target: `/etc/firewall/firedog.conf`

Seedato al primo install (mai sovrascritto agli aggiornamenti), formato `KEY="value"`:

```bash
# Interfacce da monitorare/riportare al master (separate da virgola).
# Vuoto = tutte le interfacce rilevate (default).
MONITORED_INTERFACES="eth0,eth1"

# Porte da tenere sempre aperte in INPUT, prima della policy DROP finale.
ALWAYS_OPEN_PORTS="80/tcp,443/tcp"

# Protezione SSH brute-force: soglia/finestra e cosa succede al superamento.
# BAN_DURATION: "0" nessun ban | "<N>m"/"<N>h"/"<N>d" temporaneo | "permanent"
SSH_PROTECT_MAX_ATTEMPTS="4"
SSH_PROTECT_WINDOW_SECONDS="60"
SSH_PROTECT_BAN_DURATION="0"
```

> **Importante**: `ALWAYS_OPEN_PORTS` va valorizzato **prima** di lanciare `firewall-init.sh` la prima volta — senza, qualunque servizio su quelle porte diventa irraggiungibile appena la policy DROP entra in vigore. Dopo una modifica, riapplica con `sudo firewall-init.sh`.

Gestione ban SSH attivi:
```bash
firewall-manager --list-bans          # IP bannati e tempo alla scadenza (o "permanente")
firewall-manager --unban 203.0.113.5  # rimuove un ban, incluso uno permanente
```

## 🔧 `firewall-manager` — CLI di gestione

```bash
# Lista regole
firewall-manager --list
firewall-manager --list INPUT

# Statistiche e minacce
firewall-manager --stats
firewall-manager --threats 50            # score >= 50
firewall-manager --analyze 24            # traffico bloccato ultime 24h

# Regole INPUT/OUTPUT
sudo firewall-manager --add-input 8080 --comment "Node.js app"
sudo firewall-manager --add-input 22 --source 192.168.1.10 --comment "SSH da admin"
sudo firewall-manager --add-output 3306 --dest 10.0.1.50 --comment "MySQL prod"
sudo firewall-manager --remove INPUT 5

# Ban SSH
firewall-manager --list-bans
sudo firewall-manager --unban 203.0.113.5
```

Sul master, le stesse operazioni si fanno da UI o via API REST (`/api/rules/`, `/api/settings/...`) — vedi [ROLES_AND_PERMISSIONS.md](backend/ROLES_AND_PERMISSIONS.md).

## 🔍 Interpretazione Threat Score

Il traffic-analyzer assegna uno score 0-100 a ogni IP basandosi su volume pacchetti, scanning multiplo porte, targeting di porte comunemente attaccate, pattern SYN flood e protocolli multipli:

| Score | Livello | Significato |
|-------|---------|-------------|
| 80-100 | 🔴 CRITICO | Attacco attivo confermato |
| 60-79 | 🟠 ALTO | Comportamento molto sospetto |
| 40-59 | 🟡 MEDIO | Attività anomala |
| 20-39 | 🟢 BASSO | Leggera anomalia |
| 0-19 | ⚪ MINIMO | Traffico normale |

## 👥 Ruoli e permessi

| Ruolo | Permessi |
|---|---|
| **Admin** | Completi: creare/modificare/eliminare target e regole, bloccare/sbloccare IP, configurazione, Django Admin, tool MCP di scrittura |
| **Reporter** | Sola lettura: target, regole, minacce, statistiche, audit log |

Dettagli e esempi API: [ROLES_AND_PERMISSIONS.md](backend/ROLES_AND_PERMISSIONS.md).

## 🔐 Sicurezza

**Principi implementati (OWASP/NIST):**
1. Defense in Depth — protezioni a più livelli
2. Fail Secure — policy DROP di default
3. Least Privilege — solo traffico necessario consentito
4. Audit & Logging — traffico bloccato loggato, ogni scrittura API/MCP in `AuditLog`
5. Rate Limiting — protezione da flood attack e brute-force SSH configurabile
6. Input Validation — validazione rigorosa di IP/porte/protocolli

**Protezioni attive lato target:** SYN Flood, Port Scan Detection, SSH Brute Force (con ban persistente opzionale), ICMP Flood, NULL/XMAS packet filtering, anti-spoofing (martian packets), fragment attack protection.

## 📁 Struttura del repository

```
firedog/
├── backend/                # Django REST Framework (master)
│   ├── targets/             # Target, NetworkInterface (multi-NIC)
│   ├── rules/                # Regole firewall + dispatch WebSocket
│   ├── agent_manager/       # Pairing dog-agent, API key
│   ├── mcp/                  # Server MCP (POST /api/mcp)
│   ├── threats/ discovery/ integrity/ audit/ dashboards/ accounts/ settings/
│   └── requirements.txt
├── frontend/                # React + TypeScript SPA
├── firedog-package/         # Strumenti target (bash + Python)
│   ├── install.sh            # apt (Debian/Ubuntu) o zypper (openSUSE/SLES)
│   ├── get-firedog.sh        # bootstrap curl | bash
│   ├── firewall-init.sh      # policy DROP + protezioni
│   ├── firewall-manager.py   # CLI regole/ban
│   └── file_config/          # firedog.conf.example, unit systemd, cron
├── INSTALL.md                # guida master
├── INSTALL-TARGET.md         # guida target + pairing agent
└── backend/ROLES_AND_PERMISSIONS.md
```

## 🛠️ Troubleshooting

**Non riesco più a connettermi via SSH dopo l'attivazione del firewall**
```bash
# da console fisica/IPMI/seriale
sudo iptables -I INPUT 1 -p tcp --dport 22 -j ACCEPT
sudo firewall-manager --save
```
Se hai configurato un ban SSH (capitolo Configurazione), controlla anche `firewall-manager --list-bans` — potresti aver bannato te stesso durante un test.

**Un servizio non è raggiungibile dopo l'attivazione della policy DROP**
```bash
sudo netstat -tulpn | grep <servizio>
sudo firewall-manager --add-input <PORTA> --comment "Nome servizio"
# oppure aggiungi la porta a ALWAYS_OPEN_PORTS in firedog.conf e rilancia firewall-init.sh
```

**Il target non risulta online sul master**
```bash
systemctl status dog-agent
journalctl -u dog-agent -f    # cerca "pairing" ed eventuali errori di autenticazione
```

**Accesso di emergenza** (il firewall blocca tutto e perdi accesso, da console fisica/IPMI):
```bash
sudo iptables -F
sudo iptables -P INPUT ACCEPT
sudo iptables -P OUTPUT ACCEPT
sudo iptables -P FORWARD ACCEPT
```

## 📚 Documentazione

- [INSTALL.md](INSTALL.md) — installazione del master
- [INSTALL-TARGET.md](INSTALL-TARGET.md) — installazione target e pairing dog-agent
- [backend/ROLES_AND_PERMISSIONS.md](backend/ROLES_AND_PERMISSIONS.md) — ruoli, permessi, esempi API
- [dog_agent](https://github.com/Dognet-Technologies/dog_agent) — repo dell'agent condiviso dalla suite Dognet

## 🐛 Bug Report e Contributi

Apri una [issue](https://github.com/Dognet-Technologies/firedog/issues) con: descrizione del problema, output di `firewall-manager --list -v`, `systemctl status firewall-fm dog-agent`, versione target (`lsb_release -a` o `cat /etc/os-release`).

## 📄 Licenza

Questo progetto è rilasciato sotto licenza MIT.

## ⚠️ Disclaimer

Fornito "as is" senza garanzie. Testa sempre in ambienti non-produzione prima del deploy, e assicurati di avere accesso fisico o out-of-band a un target prima di attivare la policy DROP.

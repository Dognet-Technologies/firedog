# FireDog — Installazione sui target

Guida all'installazione dei componenti **lato target** (le macchine Linux il
cui firewall è gestito da FireDog) e al processo di
connessione/autenticazione tra target e master.

> Per l'installazione del **master** (backend Django + frontend + Celery +
> nginx) vedi [INSTALL.md](INSTALL.md).

## I tre componenti di FireDog

| Componente | Dove gira | Cosa fa |
|---|---|---|
| **1. Server FireDog (master)** | una VM/host dedicato | Backend Django + frontend React: UI, API REST, server MCP, riceve heartbeat/statistiche dagli agent via WebSocket |
| **2. Strumenti firewall** | ogni target, in `/opt/sentinelsuite/firedog` | `firewall-manager` (CLI iptables), `traffic-analyzer` (analisi PCAP con threat scoring), `firewall-init.sh` (policy DROP + protezioni), ulogd2/logrotate/cron a supporto |
| **3. dog-agent** | ogni target, `/usr/bin/dog-agent` | Binario Rust statico: si autentica al master (pairing a 2 fasi), poi **pusha** heartbeat, statistiche e minacce via WebSocket ed esegue i comandi regola inviati dal master. Non esiste più alcun pull SSH dal master. |

Layout sul target dopo l'installazione:

```
/opt/sentinelsuite/firedog/
├── bin/        firewall-manager, traffic-analyzer, firewall-init.sh
├── conf/       ulogd.conf, custom_rules, unit firewall-fm, cron, apparmor
├── data/       output runtime
├── logs/       log applicativi
├── rules/      backup iptables
└── export/     export CLI manuali (legacy)

/usr/local/bin/firewall-manager      → symlink a bin/
/etc/firewall/custom_rules.conf      regole custom persistenti

# installati dal pacchetto .deb del dog-agent (processo separato, vedi sotto)
/usr/bin/dog-agent                   binario agent
/etc/dog-agent/agent.conf            configurazione agent (credenziali)
```

## Metodo A — Push dal master (consigliato in LAN)

Dalla UI del master: **Targets → aggiungi target → Install**. Il master via
SSH (chiave configurata in Settings → SSH Keys):

1. verifica l'utente `microcyber` e configura sudoers,
2. hardening SSH (disabilita PasswordAuthentication),
3. carica `firedog-package/` sul target,
4. esegue `install.sh`,
5. verifica l'installazione e configura il cron.

Requisiti sul target: Debian/Ubuntu, utente `microcyber` con la chiave
pubblica del master autorizzata.

## Metodo B — Bootstrap da GitHub (curl | bash)

Per installare **gli strumenti firewall** su un target senza passare dal
master:

```bash
curl -fsSL https://raw.githubusercontent.com/Dognet-Technologies/firedog/develop-v0.0.6/firedog-package/get-firedog.sh | sudo bash
```

Con opzioni (es. senza attivare subito il firewall):

```bash
curl -fsSL .../get-firedog.sh | sudo bash -s -- --skip-init
```

Lo script scarica il tarball del repo (branch/tag configurabile con
`FIREDOG_REF`, default `develop-v0.0.6`), ne estrae `firedog-package/` ed
esegue `install.sh`. Se lanciato in pipe senza tty, la conferma interattiva
di attivazione firewall viene letta da `/dev/tty` oppure viene forzato
`--skip-init` (mai policy DROP senza conferma esplicita).

`install.sh` installa **solo la parte target** (strumenti firewall, ulogd2,
cron, apparmor): né il server né il dog-agent, che ha il suo pacchetto
dedicato (vedi sotto). È idempotente: si può rilanciare per aggiornare.

> **Attenzione**: l'attivazione del firewall applica policy **DROP** su
> INPUT/OUTPUT. Assicurati di avere accesso console/seriale prima di
> confermare, o usa `--skip-init` e attiva dopo con
> `sudo firewall-init.sh && sudo systemctl enable --now firewall-fm`.

## Installazione del dog-agent

Il dog-agent è un componente **della suite Dognet** (serve FireDog,
CyberSheppard e SentinelCore con un solo binario) e ha il proprio processo
di installazione: un pacchetto **`.deb`** prodotto dal repo `dog_agent`.

```bash
# sulla macchina di build (repo dog_agent, richiede cargo-deb)
make deb          # produce target/debian/dog-agent_<ver>_amd64.deb

# sul target
sudo dpkg -i dog-agent_<ver>_amd64.deb
```

Il pacchetto installa `/usr/bin/dog-agent`, seeda
`/etc/dog-agent/agent.conf.example` e registra l'unità systemd
`dog-agent.service` (non abilitata finché la config non è pronta).
`install.sh` degli strumenti firewall **non** tocca l'agent.

## Connessione e autenticazione agent ↔ master (pairing)

L'agent si autentica con un **pairing a 2 fasi** sul WebSocket
`ws(s)://<master>/ws/agent/`:

```
dog-agent                              master
    │  {"api_key", ip, hostname, mac}    │
    ├────────────────────────────────────▶
    │        FASE 1: verifica API key    │  AgentAPIKey attiva (hash SHA-512)
    │        FASE 2: verifica identità   │  SHA512(ip+hostname+mac) ==
    │                                    │  target.identity_hash
    ◀────────────────────────────────────┤
    │  pairing OK → heartbeat/stats/     │
    │  threats push + comandi regole     │
```

Passi operativi:

1. **Sul master** — Settings → **API Keys Agent** → *Genera nuova API Key*.
   La chiave è globale per la flotta, hashata SHA-512 (recuperabile solo con
   password admin).
2. **Sul master** — crea il **Target** (Targets → Add) con **ip, hostname e
   MAC address esatti** della macchina: il master ne calcola
   `identity_hash = SHA512(ip+hostname+mac)` al salvataggio.
3. **Sul target** — edita `/etc/dog-agent/agent.conf` (seedato
   dall'example durante l'installazione):

   ```toml
   [agent]
   log_level = "info"

   [[targets]]
   name          = "nome-descrittivo"
   system_type   = "firedog"
   url           = "http://<master>"        # o https/wss
   api_key       = "<API key generata al passo 1>"
   ip            = "<ip del target>"        # identici al Target sul master
   hostname      = "<hostname>"
   mac           = "aa:bb:cc:dd:ee:ff"
   heartbeat_interval = 30
   ```

4. **Sul target** — avvia l'agent:

   ```bash
   sudo systemctl enable --now dog-agent
   journalctl -u dog-agent -f    # verifica "pairing success"
   ```

5. **Sul master** — il target passa a stato *online* e inizia a ricevere
   heartbeat, statistiche e minacce.

Se il pairing fallisce: API key errata/disattivata (fase 1) oppure
ip/hostname/mac che non coincidono con quelli del Target sul master
(fase 2) — l'errore è visibile sia in `journalctl -u dog-agent` sia nella
UI (Pairing sessions).

## Verifica installazione target

```bash
firewall-manager --list            # CLI risponde
systemctl status firewall-fm       # firewall persistente (dopo l'init)
systemctl status ulogd2            # logging PCAP
systemctl status dog-agent         # agent connesso al master
ls /opt/sentinelsuite/firedog      # layout base
```


# FireDog Package

Questo pacchetto contiene gli strumenti per il monitoring e la gestione del firewall sui target remoti.

## Contenuto

```
firedog-package/
├── install.sh                      # Script principale di installazione
├── bin/
│   ├── firewall-manager            # Gestione regole iptables
│   └── traffic-analyzer            # Analisi traffico e anomalie
├── config/
│   └── firedog.service             # Systemd service unit
├── file_config/                    # Template di configurazione
│   ├── sudoers-microcyber          # Sudoers con NOPASSWD per microcyber
│   ├── sshd_config.hardened        # SSH config hardened
│   ├── firedog-cron                # Cron jobs per task periodici
│   ├── ssh-copy-id.sh              # Helper per copiare chiave SSH
│   ├── preconfigure-target.sh      # Script pre-configurazione completa
│   └── README-file_config.md       # Documentazione dettagliata
└── README.md
```

## Installazione

### Automatica (da FireDog Web Console)
L'installazione viene gestita automaticamente dalla web console tramite SSH.

### Manuale
```bash
sudo bash install.sh
```

## Utilizzo

### Firewall Manager
```bash
# Lista regole iptables
firewall-manager --list

# Statistiche firewall (JSON)
firewall-manager --stats

# Blocca IP
sudo firewall-manager --block 192.168.1.100 --comment "Attacco rilevato"

# Sblocca IP
sudo firewall-manager --unblock 192.168.1.100

# Salva regole correnti
sudo firewall-manager --save

# Ripristina regole da file
sudo firewall-manager --restore /opt/firedog/rules/iptables.20241116.rules
```

### Traffic Analyzer
```bash
# Analizza connessioni attive
traffic-analyzer --connections

# Statistiche interfacce di rete
traffic-analyzer --interfaces

# Pacchetti droppati
traffic-analyzer --dropped

# Rilevamento port scan
traffic-analyzer --scan-detect

# Analisi completa (JSON)
traffic-analyzer --full
```

## Directory

- `/opt/firedog/` - Directory principale
  - `logs/` - Log applicazione
  - `data/` - Dati analisi
  - `pcap/` - File di cattura pacchetti
  - `rules/` - Backup regole iptables

- `/var/log/firedog/` - Log di sistema
  - `analysis.log` - Log analisi traffico
  - `error.log` - Log errori

## Configurazione

File di configurazione: `/opt/firedog/firedog.conf`

```bash
FIREDOG_VERSION=1.0.0
LOG_DIR=/var/log/firedog
DATA_DIR=/opt/firedog/data
PCAP_DIR=/opt/firedog/pcap
RULES_DIR=/opt/firedog/rules
MAX_LOG_SIZE=100M
MAX_PCAP_SIZE=500M
ANALYSIS_INTERVAL=300
```

## Requisiti

- Linux (Ubuntu/Debian/CentOS/RHEL)
- Python 3.6+
- iptables
- tcpdump
- net-tools o iproute2
- Utente `microcyber` con accesso sudo

## Pre-configurazione Target (Consigliata)

Prima di installare FireDog, è consigliato pre-configurare il target per installazione senza password:

```bash
# 1. Genera chiavi SSH (sul sistema web console)
sudo -u microcyber ssh-keygen -t ed25519 -f /opt/firedog/ssh/id_ed25519 -N ""

# 2. Pre-configura target (tutto automatico)
cd /opt/firedog/file_config
./preconfigure-target.sh 192.168.1.100 all

# 3. Verifica configurazione
./preconfigure-target.sh 192.168.1.100 check
```

Vedi `file_config/README-file_config.md` per documentazione completa.

## Permessi Sudo Richiesti

File template: `file_config/sudoers-microcyber`

Permessi principali:
- Gestione iptables (iptables, iptables-save, iptables-restore)
- Esecuzione binari FireDog
- Gestione servizio systemd
- Lettura log e analisi network
- Controllo integrità file

Vedi file template per lista completa.

## Service Systemd

```bash
# Avvia servizio
sudo systemctl start firedog

# Stop servizio
sudo systemctl stop firedog

# Status servizio
sudo systemctl status firedog

# Abilita all'avvio
sudo systemctl enable firedog
```

## Deployment Sistema Web Console

Sul sistema production (web console FireDog):

```bash
# 1. Copia pacchetto
sudo mkdir -p /opt/firedog
sudo cp -r backend/firedog-package/* /opt/firedog/
sudo chown -R microcyber:microcyber /opt/firedog

# 2. Genera chiavi SSH
sudo -u microcyber mkdir -p /opt/firedog/ssh
sudo -u microcyber ssh-keygen -t ed25519 -f /opt/firedog/ssh/id_ed25519 -N ""
sudo chmod 700 /opt/firedog/ssh
sudo chmod 600 /opt/firedog/ssh/id_ed25519
sudo chmod 644 /opt/firedog/ssh/id_ed25519.pub

# 3. Configura environment
echo "SSH_KEY_PATH=/opt/firedog/ssh/id_ed25519" >> .env
echo "FIREDOG_FILE_CONFIG_PATH=/opt/firedog/file_config" >> .env
```

## File Monitorati (Integrity Page)

I seguenti file configurazione sono monitorati via hash per rilevare modifiche:

**Sul web console** (`/opt/firedog/file_config/`):
- `sudoers-microcyber` - Template sudoers
- `sshd_config.hardened` - Template SSH hardened
- `firedog-cron` - Template cron jobs

**Sui target** (dopo installazione):
- `/etc/sudoers.d/microcyber`
- `/etc/ssh/sshd_config`
- `/etc/cron.d/firedog`
- `/usr/local/bin/firewall-manager`
- `/usr/local/bin/traffic-analyzer`

Gli hash sono calcolati con SHA256 e verificati periodicamente.

## Note

- Tutti i file appartengono a `microcyber:microcyber`
- I binari sono installati in `/usr/local/bin/`
- Le chiavi SSH in `/opt/firedog/ssh/`
- I template configurazione in `/opt/firedog/file_config/`
- Le regole iptables backuppate in `/opt/firedog/rules/`
- I log sono ruotati automaticamente se > MAX_LOG_SIZE
- L'analisi traffico viene eseguita ogni ANALYSIS_INTERVAL secondi

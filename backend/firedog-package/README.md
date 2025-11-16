# FireDog Package

Questo pacchetto contiene gli strumenti per il monitoring e la gestione del firewall sui target remoti.

## Contenuto

```
firedog-package/
├── install.sh              # Script principale di installazione
├── bin/
│   ├── firewall-manager    # Gestione regole iptables
│   └── traffic-analyzer    # Analisi traffico e anomalie
├── config/
│   └── firedog.service     # Systemd service unit
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
- Accesso sudo per utente microcyber

## Permessi Sudo Richiesti

```
microcyber ALL=(ALL) NOPASSWD: /usr/sbin/iptables
microcyber ALL=(ALL) NOPASSWD: /usr/sbin/ip6tables
microcyber ALL=(ALL) NOPASSWD: /usr/sbin/iptables-save
microcyber ALL=(ALL) NOPASSWD: /usr/sbin/iptables-restore
microcyber ALL=(ALL) NOPASSWD: /usr/local/bin/firewall-manager
microcyber ALL=(ALL) NOPASSWD: /usr/local/bin/traffic-analyzer
microcyber ALL=(ALL) NOPASSWD: /bin/systemctl restart firedog
microcyber ALL=(ALL) NOPASSWD: /bin/systemctl status firedog
microcyber ALL=(ALL) NOPASSWD: /bin/cat /var/log/firedog/*
```

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

## Note

- I binari sono installati in `/usr/local/bin/`
- Le regole iptables vengono backuppate automaticamente prima di modifiche
- I log sono ruotati automaticamente se > MAX_LOG_SIZE
- L'analisi traffico viene eseguita ogni ANALYSIS_INTERVAL secondi

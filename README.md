# 🛡️ Advanced Firewall System

Sistema di firewall avanzato per Debian/Ubuntu con policy DROP, logging PCAP separato, analisi intelligente del traffico e interfaccia CLI di gestione.

> **Guide di installazione:**
> - Master FireDog (backend Django + frontend React + Celery + nginx): [INSTALL.md](INSTALL.md)
> - Target (strumenti firewall + dog-agent + pairing col master): [INSTALL-TARGET.md](INSTALL-TARGET.md)
>
> Installazione rapida di un target:
> ```bash
> curl -fsSL https://raw.githubusercontent.com/Dognet-Technologies/firedog/develop-v0.0.6/firedog-package/get-firedog.sh | sudo bash
> ```
>
> Questo README descrive gli strumenti firewall contenuti in `firedog-package/`.

## 📋 Caratteristiche

- ✅ Policy DROP di default su INPUT/OUTPUT
- ✅ Protezioni avanzate: SYN flood, port scan, brute force SSH
- ✅ Logging separato INPUT/OUTPUT in formato PCAP con ulogd2
- ✅ Retention automatica 30 giorni / 1GB con logrotate
- ✅ CLI Python per gestione regole
- ✅ Analisi intelligente traffico con threat scoring
- ✅ Avvio automatico con systemd
- ✅ Conforme OWASP/NIST security best practices

## 🔧 Componenti

### 1. `firewall-init.sh`
Script bash di inizializzazione firewall con regole di sicurezza.

**Protezioni implementate:**
- SYN flood protection (max 10 conn/sec)
- Port scan detection (max 15 porte/min)
- SSH brute force protection (max 4 tentativi/min)
- ICMP flood protection (max 5 ping/sec)
- Protezione contro NULL packets, XMAS packets, pacchetti frammentati
- Anti-spoofing (martian packets)

### 2. `firewall-manager.py`
Interfaccia CLI Python per gestione firewall.

**Funzionalità:**
- Aggiunta/rimozione regole INPUT/OUTPUT
- Listing regole con numerazione
- Analisi traffico bloccato
- Threat scoring e identificazione anomalie
- Statistiche firewall
- Persistenza regole

### 3. `traffic-analyzer.py`
Analizzatore avanzato traffico PCAP con machine learning-like scoring.

**Analisi:**
- Calcolo threat score (0-100) per ogni IP
- Classificazione minacce: Critical/High/Medium/Low
- Identificazione pattern attacco: Port Scan, SYN Flood, Service Attack
- Raccomandazioni automatiche

### 4. Configurazione ulogd2
Logging separato INPUT/OUTPUT con stack PCAP ottimizzati.

### 5. Systemd Service
Avvio automatico firewall all'boot del sistema.

## 📦 Installazione

### Prerequisiti
- Debian 10+ o Ubuntu 18.04+
- Accesso root (sudo)
- Connessione internet per installazione pacchetti

### Installazione Rapida

```bash
# 1. Scarica i file
git clone <repository-url>
cd firewall-system

# 2. Rendi eseguibili gli script
chmod +x install.sh firewall-init.sh firewall-manager.py traffic-analyzer.py

# 3. Esegui installazione
sudo ./install.sh
```

Lo script di installazione:
1. Installa dipendenze (iptables, ulogd2, tcpdump, etc.)
2. Configura ulogd2 per logging PCAP
3. Installa gli script di gestione
4. Configura logrotate per retention
5. Crea e abilita systemd service
6. Inizializza il firewall (dopo conferma)

### Installazione Manuale

```bash
# Installa dipendenze
sudo apt update
sudo apt install -y iptables iptables-persistent ulogd2 python3 tcpdump logrotate

# Copia script
sudo cp firewall-init.sh /usr/local/sbin/
sudo cp firewall-manager.py /usr/local/bin/firewall-manager
sudo cp traffic-analyzer.py /usr/local/bin/traffic-analyzer
sudo chmod +x /usr/local/sbin/firewall-init.sh
sudo chmod +x /usr/local/bin/firewall-manager
sudo chmod +x /usr/local/bin/traffic-analyzer

# Configura ulogd2
sudo cp ulogd.conf /etc/ulogd.conf
sudo mkdir -p /var/log/ulogd
sudo systemctl restart ulogd2

# Configura logrotate
sudo cp firewall-pcap-logrotate /etc/logrotate.d/firewall-pcap

# Installa systemd service
sudo cp firewall.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable firewall.service

# Inizializza firewall
sudo /usr/local/sbin/firewall-init.sh
```

## 🚀 Utilizzo

### Comandi Base

```bash
# Mostra aiuto completo
firewall-manager --help

# Lista tutte le regole
firewall-manager --list

# Lista regole di una chain specifica
firewall-manager --list INPUT
firewall-manager --list OUTPUT

# Mostra statistiche firewall
firewall-manager --stats
```

### Gestione Regole INPUT

```bash
# Apri porta 8080 TCP
sudo firewall-manager --add-input 8080

# Apri porta 53 UDP (DNS)
sudo firewall-manager --add-input 53 --protocol udp

# Apri porta 22 solo da IP specifico
sudo firewall-manager --add-input 22 --source 192.168.1.10 --comment "SSH da admin"

# Apri porta 3000 con commento
sudo firewall-manager --add-input 3000 --comment "Node.js app"
```

### Gestione Regole OUTPUT

```bash
# Consenti connessioni verso porta 3306 (MySQL remoto)
sudo firewall-manager --add-output 3306

# Consenti connessioni SMTP verso IP specifico
sudo firewall-manager --add-output 587 --dest 203.0.113.10 --comment "SMTP server"

# Consenti Redis su localhost
sudo firewall-manager --add-output 6379 --dest 127.0.0.1
```

### Rimozione Regole

```bash
# Lista regole con numerazione
firewall-manager --list INPUT

# Rimuovi regola numero 5 da INPUT
sudo firewall-manager --remove INPUT 5

# Rimuovi regola numero 3 da OUTPUT
sudo firewall-manager --remove OUTPUT 3
```

### Analisi Traffico

```bash
# Analizza traffico ultima ora
sudo firewall-manager --analyze

# Analizza traffico ultime 24 ore
sudo firewall-manager --analyze 24

# Mostra minacce con score >= 30 (default)
sudo firewall-manager --threats

# Mostra solo minacce critiche (score >= 70)
sudo firewall-manager --threats 70

# Analisi dettagliata con script dedicato
sudo traffic-analyzer /var/log/ulogd/input_dropped.pcap

# Genera report JSON
sudo traffic-analyzer /var/log/ulogd/input_dropped.pcap --json
```

### Gestione Servizio

```bash
# Stato firewall
sudo systemctl status firewall

# Riavvia firewall
sudo systemctl restart firewall

# Stop firewall (regole rimangono attive per sicurezza)
sudo systemctl stop firewall

# Ricarica regole salvate
sudo systemctl reload firewall

# Disabilita avvio automatico
sudo systemctl disable firewall
```

## 📊 Esempi Pratici

### Scenario 1: Setup Server Web

```bash
# Apri porte web
sudo firewall-manager --add-input 80 --comment "HTTP"
sudo firewall-manager --add-input 443 --comment "HTTPS"

# Verifica regole
firewall-manager --list INPUT
```

### Scenario 2: Database Server Remoto

```bash
# Consenti connessioni MySQL verso server specifico
sudo firewall-manager --add-output 3306 --dest 10.0.1.50 --comment "MySQL prod"

# Verifica
firewall-manager --list OUTPUT
```

### Scenario 3: Analisi Attacco in Corso

```bash
# Mostra minacce in tempo reale
sudo firewall-manager --threats 50

# Analisi dettagliata
sudo traffic-analyzer

# Blocca IP attaccante (se necessario)
# Nota: il traffico è già bloccato, questa è una protezione aggiuntiva
sudo iptables -I INPUT 1 -s 203.0.113.100 -j DROP
sudo firewall-manager --save
```

### Scenario 4: Whitelisting Servizio Specifico

```bash
# Esempio: Jenkins su porta 8080 solo da rete aziendale
sudo firewall-manager --add-input 8080 --source 192.168.1.0/24 --comment "Jenkins rete interna"
```

## 🔍 Interpretazione Threat Score

Il sistema assegna uno score 0-100 a ogni IP basandosi su:

| Score | Livello | Significato | Azione |
|-------|---------|-------------|--------|
| 80-100 | 🔴 CRITICO | Attacco attivo confermato | Blocco immediato |
| 60-79 | 🟠 ALTO | Comportamento molto sospetto | Monitoraggio stretto |
| 40-59 | 🟡 MEDIO | Attività anomala | Verifica legittimità |
| 20-39 | 🟢 BASSO | Leggera anomalia | Osservazione |
| 0-19 | ⚪ MINIMO | Traffico normale | Nessuna azione |

**Fattori che aumentano lo score:**
- Volume pacchetti elevato
- Scanning multiplo porte
- Targeting porte comunemente attaccate (RDP, Telnet, SQL)
- Pattern SYN flood
- Protocolli multipli (potenziale reconnaissance)

## 📁 File e Directory

```
/etc/firewall/
├── iptables.rules           # Regole firewall salvate
└── custom_rules.conf        # Regole personalizzate persistenti

/var/log/ulogd/
├── input_dropped.pcap       # Traffico INPUT bloccato
├── output_dropped.pcap      # Traffico OUTPUT bloccato
└── ulogd.log               # Log daemon ulogd2

/usr/local/sbin/
└── firewall-init.sh        # Script inizializzazione

/usr/local/bin/
├── firewall-manager        # CLI gestione
└── traffic-analyzer        # Analizzatore traffico

/etc/systemd/system/
└── firewall.service        # Systemd unit

/etc/logrotate.d/
└── firewall-pcap           # Configurazione rotazione log
```

## 🔐 Sicurezza

### Principi Implementati (OWASP/NIST)

1. **Defense in Depth**: Protezioni multiple livelli
2. **Fail Secure**: Policy DROP di default
3. **Least Privilege**: Solo traffico necessario consentito
4. **Audit & Logging**: Logging completo traffico bloccato
5. **Rate Limiting**: Protezione flood attacks
6. **Input Validation**: Validazione rigorosa IP/porte/protocolli

### Protezioni Attive

- ✅ SYN Flood Protection
- ✅ Port Scan Detection
- ✅ SSH Brute Force Protection
- ✅ ICMP Flood Protection
- ✅ Invalid Packet Dropping
- ✅ NULL/XMAS Packet Filtering
- ✅ Anti-Spoofing (Martian Packets)
- ✅ Fragment Attack Protection

### Permessi File

```bash
# Verifica permessi corretti
ls -la /etc/firewall/
# Dovrebbe mostrare: drwx------ (700)

ls -la /etc/firewall/iptables.rules
# Dovrebbe mostrare: -rw------- (600)
```

## 🛠️ Troubleshooting

### Problema: Non riesco più a connettermi via SSH

**Causa**: Policy DROP senza regola SSH o SSH bloccato per brute force

**Soluzione**:
```bash
# Da console fisica o IPMI
sudo iptables -I INPUT 1 -p tcp --dport 22 -j ACCEPT
sudo firewall-manager --save

# Oppure ripristina regole precedenti
sudo iptables-restore < /etc/firewall/iptables.rules.backup
```

### Problema: Servizio non funziona dopo attivazione firewall

**Causa**: Porta non aperta

**Soluzione**:
```bash
# Identifica porta necessaria
sudo netstat -tulpn | grep <servizio>

# Apri porta
sudo firewall-manager --add-input <PORTA> --comment "Nome servizio"
```

### Problema: File PCAP molto grandi

**Causa**: Traffico elevato o attacco in corso

**Soluzione**:
```bash
# Forza rotazione immediata
sudo logrotate -f /etc/logrotate.d/firewall-pcap

# Analizza traffico per identificare fonte
sudo traffic-analyzer

# Riduci retention se necessario
sudo nano /etc/logrotate.d/firewall-pcap
# Modifica: rotate 30 -> rotate 7
```

### Problema: ulogd2 non scrive PCAP

**Verifica**:
```bash
# Status service
sudo systemctl status ulogd2

# Verifica configurazione
sudo ulogd -d -c /etc/ulogd.conf

# Controlla permessi
ls -la /var/log/ulogd/

# Riavvia service
sudo systemctl restart ulogd2
```

### Problema: Performance degradate

**Causa**: Regole troppo numerose o logging eccessivo

**Soluzione**:
```bash
# Conta regole attive
sudo iptables -L INPUT | wc -l
sudo iptables -L OUTPUT | wc -l

# Ottimizza: metti regole più frequenti in cima
# Considera ridurre --nflog-threshold in firewall-init.sh
```

## 📈 Monitoring e Manutenzione

### Controlli Giornalieri

```bash
# Statistiche rapide
sudo firewall-manager --stats

# Verifica minacce
sudo firewall-manager --threats

# Spazio disco log
du -sh /var/log/ulogd/
```

### Controlli Settimanali

```bash
# Analisi traffico settimanale
sudo firewall-manager --analyze 168

# Report dettagliato
sudo traffic-analyzer --json

# Verifica servizi attivi
sudo ss -tulpn

# Review regole custom
cat /etc/firewall/custom_rules.conf
```

### Controlli Mensili

```bash
# Audit completo regole
sudo iptables-save > /tmp/firewall-audit-$(date +%Y%m).txt

# Cleanup log vecchi
sudo find /var/log/ulogd -name "*.pcap.*.gz" -mtime +60 -delete

# Update sistema
sudo apt update && sudo apt upgrade -y
```

## 🔄 Backup e Restore

### Backup Regole

```bash
# Backup manuale
sudo iptables-save > ~/firewall-backup-$(date +%Y%m%d).txt

# Backup automatico (crontab)
0 2 * * * /usr/sbin/iptables-save > /backup/firewall-$(date +\%Y\%m\%d).txt
```

### Restore Regole

```bash
# Restore da backup
sudo iptables-restore < ~/firewall-backup-20250115.txt

# Oppure usa il manager
sudo firewall-manager --restore
```

## 🆘 Accesso Emergenza

Se il firewall blocca tutto e perdi accesso:

1. **Da console fisica/IPMI**:
```bash
# Flush tutte le regole (TEMPORANEO)
sudo iptables -F
sudo iptables -P INPUT ACCEPT
sudo iptables -P OUTPUT ACCEPT
sudo iptables -P FORWARD ACCEPT
```

2. **Ripristina stato precedente**:
```bash
sudo iptables-restore < /etc/firewall/iptables.rules.backup
```

3. **Riavvia servizio firewall**:
```bash
sudo systemctl restart firewall
```

## 📚 Risorse Aggiuntive

- [iptables Documentation](https://netfilter.org/documentation/)
- [ulogd2 Manual](https://www.netfilter.org/projects/ulogd/index.html)
- [OWASP Firewall Best Practices](https://owasp.org/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

## 🐛 Bug Report e Contributi

Per segnalare bug o contribuire al progetto, apri una issue su GitHub con:
- Descrizione problema
- Output comandi: `iptables -L -n -v`, `systemctl status firewall`, `dmesg | tail`
- Versione sistema: `lsb_release -a`

## 📄 Licenza

Questo progetto è rilasciato sotto licenza MIT.

## ⚠️ Disclaimer

Questo sistema di firewall è fornito "as is" senza garanzie. È responsabilità dell'utente testare in ambienti non-produzione prima del deploy. Assicurati sempre di avere accesso fisico o out-of-band al server prima di attivare policy DROP.

---

**Versione**: 1.0  
**Ultimo aggiornamento**: Ottobre 2025  
**Compatibilità**: Debian 10+, Ubuntu 18.04+

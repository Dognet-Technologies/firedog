# 🚀 QUICK START GUIDE

## Installazione Rapida (5 minuti)

```bash
# 1. Scarica tutti i file nella directory corrente

# 2. Rendi eseguibili
chmod +x install.sh firewall-init.sh firewall-manager.py traffic-analyzer.py

# 3. Installa (richiede sudo)
sudo ./install.sh
```

## Primi Comandi Essenziali

```bash
# Verifica stato firewall
sudo systemctl status firewall
firewall-manager --stats

# Apri porta SSH se necessario
sudo firewall-manager --add-input 22 --comment "SSH"

# Apri porte web
sudo firewall-manager --add-input 80 --comment "HTTP"
sudo firewall-manager --add-input 443 --comment "HTTPS"

# Lista regole
firewall-manager --list

# Analizza traffico bloccato
sudo firewall-manager --analyze
sudo firewall-manager --threats
```

## ⚠️ IMPORTANTE - Prima di Installare

1. **BACKUP**: Fai backup delle regole iptables esistenti
   ```bash
   sudo iptables-save > ~/iptables-backup-$(date +%Y%m%d).txt
   ```

2. **ACCESSO CONSOLE**: Assicurati di avere accesso fisico o console seriale/IPMI al server

3. **SSH**: Se gestisci da remoto via SSH, l'installer chiederà conferma prima di attivare il firewall

4. **TESTING**: Testa prima in ambiente non-produzione

## 🆘 Accesso Emergenza

Se perdi connessione SSH dopo l'installazione:

**Da console fisica/IPMI:**
```bash
# Accetta tutto temporaneamente
sudo iptables -P INPUT ACCEPT
sudo iptables -P OUTPUT ACCEPT

# Poi aggiungi regola SSH
sudo firewall-manager --add-input 22 --comment "SSH emergency"

# Ripristina policy DROP
sudo iptables -P INPUT DROP
sudo iptables -P OUTPUT DROP
```

## 📁 File Inclusi

- `firewall-init.sh` - Script inizializzazione firewall
- `firewall-manager.py` - CLI gestione firewall  
- `traffic-analyzer.py` - Analizzatore traffico avanzato
- `ulogd.conf` - Configurazione logging PCAP
- `firewall-pcap-logrotate` - Rotazione log automatica
- `firewall.service` - Systemd service
- `install.sh` - Installer automatico
- `README.md` - Documentazione completa
- `QUICK_START.md` - Questa guida

## 📊 Dashboard Comandi Utili

```bash
# Statistiche
firewall-manager --stats

# Lista regole
firewall-manager --list INPUT
firewall-manager --list OUTPUT

# Aggiungi regola
sudo firewall-manager --add-input <PORTA> --protocol tcp --comment "Descrizione"

# Rimuovi regola
sudo firewall-manager --remove INPUT <NUMERO>

# Analisi sicurezza
sudo firewall-manager --threats 50
sudo traffic-analyzer

# Salva regole
sudo firewall-manager --save

# Gestione servizio
sudo systemctl status firewall
sudo systemctl restart firewall
```

## 🛡️ Protezioni Attive

✅ Policy DROP di default  
✅ SYN Flood Protection (10 conn/sec)  
✅ Port Scan Detection (15 porte/min)  
✅ SSH Brute Force (4 tentativi/min)  
✅ ICMP Flood (5 ping/sec)  
✅ Logging PCAP separato INPUT/OUTPUT  
✅ Threat Scoring automatico  
✅ Retention 30 giorni / 1GB  

## 📖 Documentazione Completa

Leggi `README.md` per:
- Documentazione dettagliata
- Esempi scenari d'uso
- Troubleshooting
- Best practices
- Interpretazione threat score

## 🐛 Problemi Comuni

**Servizio non parte dopo installazione**
```bash
sudo journalctl -u firewall -n 50
sudo /usr/local/sbin/firewall-init.sh
```

**PCAP non vengono creati**
```bash
sudo systemctl status ulogd2
sudo systemctl restart ulogd2
```

**Disco pieno**
```bash
sudo logrotate -f /etc/logrotate.d/firewall-pcap
```

## 🔗 Link Utili

- Consulta sempre il README.md per la documentazione completa
- Test delle regole: `sudo iptables -L -n -v --line-numbers`
- Log sistema: `sudo journalctl -xe`
- Log firewall: `tail -f /var/log/firewall-init.log`

---

**Buon utilizzo! 🛡️**

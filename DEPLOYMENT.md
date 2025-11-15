# 🚀 DEPLOYMENT INSTRUCTIONS

## Download & Extract

```bash
# Se hai l'archivio tar.gz
tar -xzf advanced-firewall-system.tar.gz

# Oppure scarica i singoli file da GitHub/repository
git clone <repository-url>
cd firewall-system
```

## Verifica Integrità File

```bash
# Conta file
ls -1 | wc -l
# Dovrebbe essere 13 file + archivio

# Verifica script eseguibili
ls -l *.sh *.py
# Tutti dovrebbero avere permesso x

# Lista completa file necessari
cat INDEX.md
```

## Pre-Installazione Checklist

### 1. Requisiti Sistema
```bash
# Verifica OS
cat /etc/os-release | grep -E 'ID=|VERSION='
# Richiesto: Debian 10+ o Ubuntu 18.04+

# Verifica permessi root
sudo -v
```

### 2. Backup Sistema Attuale
```bash
# Backup regole iptables esistenti
sudo iptables-save > ~/iptables-backup-$(date +%Y%m%d-%H%M%S).txt

# Backup configurazione rete
sudo cp -r /etc/network /etc/network.backup-$(date +%Y%m%d)

# Lista servizi attivi
sudo systemctl list-units --type=service --state=running > ~/services-before.txt
```

### 3. Verifica Connettività
```bash
# Verifica SSH attivo
sudo systemctl status sshd

# Verifica porta SSH
sudo ss -tlnp | grep :22

# Test connessione esterna (se remoto)
echo "Test connessione - mantieni questa sessione SSH aperta durante installazione"
```

### 4. Identifica Porte Necessarie
```bash
# Lista porte in ascolto
sudo ss -tulpn | grep LISTEN

# Salva per riferimento
sudo ss -tulpn > ~/listening-ports-$(date +%Y%m%d).txt
```

## Installazione Standard

### Metodo 1: Installer Automatico (Raccomandato)

```bash
# 1. Rendi eseguibili
chmod +x install.sh firewall-init.sh firewall-manager.py traffic-analyzer.py test-installation.sh

# 2. Review script (IMPORTANTE - leggi cosa fa)
less install.sh

# 3. Esegui installazione
sudo ./install.sh

# 4. Alla richiesta di conferma, digita: yes
# NOTA: Assicurati di avere accesso console prima di confermare!

# 5. Test installazione
./test-installation.sh
```

### Metodo 2: Installazione Passo-Passo (Manuale)

Se preferisci controllo completo:

```bash
# Step 1: Installa dipendenze
sudo apt update
sudo apt install -y iptables iptables-persistent ulogd2 python3 tcpdump logrotate

# Step 2: Copia script
sudo cp firewall-init.sh /usr/local/sbin/
sudo cp firewall-manager.py /usr/local/bin/firewall-manager
sudo cp traffic-analyzer.py /usr/local/bin/traffic-analyzer
sudo chmod +x /usr/local/sbin/firewall-init.sh
sudo chmod +x /usr/local/bin/firewall-manager
sudo chmod +x /usr/local/bin/traffic-analyzer

# Step 3: Configura ulogd2
sudo cp ulogd.conf /etc/ulogd.conf
sudo mkdir -p /var/log/ulogd
sudo chown root:adm /var/log/ulogd
sudo chmod 750 /var/log/ulogd
sudo systemctl enable ulogd2
sudo systemctl restart ulogd2

# Step 4: Configura logrotate
sudo cp firewall-pcap-logrotate /etc/logrotate.d/firewall-pcap
sudo chmod 644 /etc/logrotate.d/firewall-pcap

# Step 5: Installa systemd service
sudo cp firewall.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/firewall.service
sudo systemctl daemon-reload

# Step 6: Crea directory
sudo mkdir -p /etc/firewall /var/lib/firewall
sudo chmod 700 /etc/firewall /var/lib/firewall

# Step 7: REVIEW regole prima di inizializzare
less /usr/local/sbin/firewall-init.sh

# Step 8: Inizializza firewall
sudo /usr/local/sbin/firewall-init.sh

# Step 9: Abilita avvio automatico
sudo systemctl enable firewall.service

# Step 10: Test
./test-installation.sh
```

## Post-Installazione Immediata

### 1. Verifica Servizi
```bash
# Stato firewall
sudo systemctl status firewall
sudo systemctl status ulogd2

# Verifica policy
sudo iptables -L -n -v | head -20
```

### 2. Apri Porte Necessarie

**IMPORTANTE**: Apri subito le porte dei servizi critici!

```bash
# Esempio: SSH (se non già aperta)
sudo firewall-manager --add-input 22 --comment "SSH"

# Esempio: Web server
sudo firewall-manager --add-input 80 --comment "HTTP"
sudo firewall-manager --add-input 443 --comment "HTTPS"

# Verifica
firewall-manager --list INPUT
```

### 3. Test Connettività
```bash
# Da macchina esterna, testa porte
nmap -p 22,80,443 <your-server-ip>

# Test SSH (apri NUOVA sessione, non chiudere quella attuale)
ssh user@your-server-ip

# Se SSH funziona, puoi chiudere la sessione vecchia
```

### 4. Prima Analisi
```bash
# Aspetta qualche minuto che si accumuli traffico, poi:
sudo firewall-manager --analyze 1
sudo firewall-manager --threats
```

## Configurazione Custom

### Regole Personalizzate
```bash
# Copia template
sudo cp custom_rules.conf.example /etc/firewall/custom_rules.conf

# Modifica con le tue regole
sudo nano /etc/firewall/custom_rules.conf

# Ricarica firewall
sudo systemctl restart firewall
```

### Esempio Configurazione Web Server
```bash
# Apri porte web
sudo firewall-manager --add-input 80 --comment "HTTP"
sudo firewall-manager --add-input 443 --comment "HTTPS"

# Se hai backend su porta custom
sudo firewall-manager --add-input 8080 --comment "App backend"

# Verifica
firewall-manager --list INPUT
```

## Verifica Funzionamento

### 1. Test Logging
```bash
# Attendi 1-2 minuti, poi verifica PCAP
sudo ls -lh /var/log/ulogd/
# Dovresti vedere input_dropped.pcap e output_dropped.pcap

# Controlla contenuto
sudo tcpdump -nn -r /var/log/ulogd/input_dropped.pcap -c 10
```

### 2. Test Protezioni
```bash
# Da macchina esterna, simula port scan (SOLO PER TEST!)
# nmap -p 1-100 <your-server-ip>

# Poi controlla minacce
sudo firewall-manager --threats
# Dovresti vedere l'IP dello scan con score elevato
```

### 3. Test Rate Limiting
```bash
# SSH brute force simulation (da macchina test)
for i in {1..10}; do ssh invalid@your-server-ip; done

# Verifica blocco
sudo firewall-manager --analyze
```

## Monitoring Setup

### Cron Jobs Raccomandati
```bash
# Apri crontab
sudo crontab -e

# Aggiungi questi job:
# Analisi giornaliera (1 AM)
0 1 * * * /usr/local/bin/firewall-manager --analyze 24 > /var/log/firewall/daily-analysis-$(date +\%Y\%m\%d).txt

# Backup settimanale regole (domenica 2 AM)
0 2 * * 0 /usr/sbin/iptables-save > /backup/firewall/rules-$(date +\%Y\%m\%d).txt

# Cleanup vecchi backup (mantieni 90 giorni)
0 3 1 * * /usr/bin/find /backup/firewall -name "rules-*.txt" -mtime +90 -delete
```

### Alerting Semplice
```bash
# Script alert per minacce critiche
cat > /usr/local/bin/firewall-alert.sh << 'EOF'
#!/bin/bash
THREATS=$(firewall-manager --threats 80 | grep -c "🔴")
if [ $THREATS -gt 0 ]; then
    echo "WARNING: $THREATS critical threats detected" | \
        mail -s "Firewall Alert" admin@example.com
fi
EOF

sudo chmod +x /usr/local/bin/firewall-alert.sh

# Cron ogni 6 ore
0 */6 * * * /usr/local/bin/firewall-alert.sh
```

## Troubleshooting Post-Installazione

### Problema: Perso accesso SSH
```bash
# Da console fisica/IPMI:
sudo iptables -I INPUT 1 -p tcp --dport 22 -j ACCEPT
sudo iptables-save > /etc/firewall/iptables.rules
```

### Problema: Servizio non funziona
```bash
# Identifica porta
sudo ss -tulpn | grep <process-name>

# Apri porta
sudo firewall-manager --add-input <PORT> --comment "Service name"
```

### Problema: ulogd2 non scrive
```bash
# Check status
sudo systemctl status ulogd2

# Check config
sudo ulogd -d -c /etc/ulogd.conf

# Verifica permessi
sudo ls -la /var/log/ulogd/

# Restart
sudo systemctl restart ulogd2
```

## Rollback Procedura

Se necessario tornare allo stato precedente:

```bash
# 1. Stop servizio
sudo systemctl stop firewall

# 2. Restore regole precedenti
sudo iptables-restore < ~/iptables-backup-YYYYMMDD-HHMMSS.txt

# 3. Policy permissive (TEMPORANEO)
sudo iptables -P INPUT ACCEPT
sudo iptables -P OUTPUT ACCEPT
sudo iptables -P FORWARD ACCEPT

# 4. Rimuovi servizio
sudo systemctl disable firewall
sudo rm /etc/systemd/system/firewall.service
sudo systemctl daemon-reload
```

## Documentazione

Dopo l'installazione, consulta:

1. **QUICK_START.md** - Comandi base e quick reference
2. **README.md** - Documentazione completa
3. **ADVANCED_EXAMPLES.md** - Scenari avanzati
4. **INDEX.md** - Indice completo package

## Support & Resources

```bash
# Help comandi
firewall-manager --help
traffic-analyzer --help

# Log installazione
sudo cat /var/log/firewall-init.log

# Log sistema
sudo journalctl -u firewall -n 50
sudo journalctl -u ulogd2 -n 50
```

## Next Steps

1. ✅ Installazione completata
2. ✅ Porte critiche aperte
3. ✅ Test connettività OK
4. 📝 Documenta regole custom
5. 📝 Setup monitoring/alerting
6. 📝 Testa scenari applicativi
7. 📝 Pianifica review settimanali
8. 📝 Training team su comandi base

---

**🎉 Congratulazioni! Il tuo firewall avanzato è ora attivo e funzionante!**

Per domande: consulta README.md sezione Troubleshooting o esegui test-installation.sh per diagnostica.

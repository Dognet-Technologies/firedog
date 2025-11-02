# 🎓 ESEMPI AVANZATI - Firewall System

## Scenario 1: Server Web con Database

### Setup iniziale
```bash
# Apri porte web pubbliche
sudo firewall-manager --add-input 80 --comment "HTTP public"
sudo firewall-manager --add-input 443 --comment "HTTPS public"

# Database solo da localhost
sudo firewall-manager --add-input 3306 --source 127.0.0.1 --comment "MySQL local"

# SSH solo da IP amministratore
sudo firewall-manager --add-input 22 --source 203.0.113.50 --comment "SSH admin"

# Verifica configurazione
firewall-manager --list INPUT
```

### Monitoraggio
```bash
# Analizza tentativi di attacco ogni ora
watch -n 3600 'sudo firewall-manager --threats 60'

# Statistiche in tempo reale
watch -n 5 'sudo firewall-manager --stats'
```

## Scenario 2: Server Applicazioni Multi-tier

### Backend Application Server
```bash
# API interna porta 8080 solo da load balancer
sudo firewall-manager --add-input 8080 --source 10.0.1.10 --comment "API from LB"

# Redis solo da app server
sudo firewall-manager --add-input 6379 --source 10.0.2.20 --comment "Redis from app"

# Monitoring prometheus
sudo firewall-manager --add-input 9090 --source 10.0.3.0/24 --comment "Prometheus metrics"
```

### Database Server
```bash
# PostgreSQL solo da app servers
sudo firewall-manager --add-input 5432 --source 10.0.2.0/24 --comment "PostgreSQL from apps"

# Backup server
sudo firewall-manager --add-input 5432 --source 10.0.10.50 --comment "Backup server"
```

## Scenario 3: Gestione Emergenza - Attacco DDoS

### Identificazione
```bash
# Analisi immediata minacce
sudo firewall-manager --threats 70

# Analisi dettagliata
sudo traffic-analyzer

# Identifica top 10 IP attaccanti
sudo tcpdump -nn -r /var/log/ulogd/input_dropped.pcap 2>/dev/null | \
  awk '{print $3}' | cut -d'.' -f1-4 | sort | uniq -c | sort -rn | head -10
```

### Mitigazione
```bash
# Blocca singolo IP
sudo iptables -I INPUT 1 -s 203.0.113.100 -j DROP
sudo firewall-manager --save

# Blocca intera subnet
sudo iptables -I INPUT 1 -s 203.0.113.0/24 -j DROP
sudo firewall-manager --save

# Rate limiting più aggressivo su porta attaccata (es. 80)
sudo iptables -I INPUT 1 -p tcp --dport 80 -m limit --limit 10/minute --limit-burst 20 -j ACCEPT
sudo iptables -I INPUT 2 -p tcp --dport 80 -j DROP
sudo firewall-manager --save
```

## Scenario 4: Whitelist Temporanea

### IP temporaneo per manutenzione
```bash
# Aggiungi IP manutenzione (non salvato in custom_rules)
sudo iptables -I INPUT 1 -s 198.51.100.25 -j ACCEPT -m comment --comment "Temp maintenance"

# Verifica
sudo iptables -L INPUT -n -v --line-numbers | head -20

# Rimuovi dopo manutenzione
sudo firewall-manager --remove INPUT 1
sudo firewall-manager --save
```

## Scenario 5: VPN e Tunnel

### OpenVPN Server
```bash
# Porta UDP OpenVPN
sudo firewall-manager --add-input 1194 --protocol udp --comment "OpenVPN"

# Consenti forwarding per VPN (richiede modifica manuale)
sudo iptables -P FORWARD ACCEPT
sudo iptables -A FORWARD -i tun+ -j ACCEPT
sudo iptables -A FORWARD -o tun+ -j ACCEPT
sudo firewall-manager --save
```

### WireGuard
```bash
# Porta UDP WireGuard
sudo firewall-manager --add-input 51820 --protocol udp --comment "WireGuard"

# Masquerading per VPN
sudo iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o eth0 -j MASQUERADE
sudo firewall-manager --save
```

## Scenario 6: Logging Avanzato

### Traffico specifico verso porta
```bash
# Crea chain per logging specifico
sudo iptables -N LOG_PORT_80
sudo iptables -A LOG_PORT_80 -j LOG --log-prefix "HTTP_ACCESS: " --log-level 4
sudo iptables -A LOG_PORT_80 -j ACCEPT

# Usa chain per porta 80
sudo iptables -I INPUT -p tcp --dport 80 -j LOG_PORT_80
sudo firewall-manager --save
```

### Monitoring con rsyslog
```bash
# Aggiungi a /etc/rsyslog.d/firewall.conf
:msg, contains, "HTTP_ACCESS:" /var/log/firewall/http-access.log
:msg, contains, "INPUT_DROP:" /var/log/firewall/input-dropped.log

# Riavvia rsyslog
sudo systemctl restart rsyslog
```

## Scenario 7: Testing Regole

### Test connessione prima di applicare
```bash
# Simulazione: cosa succederebbe se...
sudo iptables -C INPUT -p tcp --dport 8080 -j ACCEPT
# Se ritorna 0: regola esiste
# Se ritorna 1: regola non esiste

# Test con nmap da macchina esterna
nmap -p 22,80,443,3306 <your-server-ip>

# Test connessione specifica
telnet <your-server-ip> 8080
```

## Scenario 8: Geoblocking (avanzato)

### Blocca traffico da paese specifico
```bash
# Installa ipset
sudo apt install ipset

# Scarica lista IP paese (esempio: Cina)
wget -O cn.zone http://www.ipdeny.com/ipblocks/data/countries/cn.zone

# Crea ipset
sudo ipset create china hash:net

# Carica IP
while read line; do
    sudo ipset add china $line
done < cn.zone

# Blocca con iptables
sudo iptables -I INPUT -m set --match-set china src -j DROP

# Persisti ipset
sudo ipset save > /etc/ipset.conf

# Auto-load all'avvio (/etc/rc.local o systemd)
ipset restore < /etc/ipset.conf
```

## Scenario 9: Analisi Forense Post-Attacco

### Estrazione dati da PCAP
```bash
# Converti PCAP in formato leggibile
sudo tcpdump -nn -r /var/log/ulogd/input_dropped.pcap > attack_analysis.txt

# Analisi con tshark (se installato)
sudo tshark -r /var/log/ulogd/input_dropped.pcap \
  -q -z conv,ip \
  -Y "frame.time >= \"2025-10-29 10:00:00\" and frame.time <= \"2025-10-29 11:00:00\""

# Export in formato JSON per analisi
sudo tshark -r /var/log/ulogd/input_dropped.pcap -T json > attack.json

# Statistiche protocolli
sudo tshark -r /var/log/ulogd/input_dropped.pcap -q -z io,phs
```

### Correlazione con log sistema
```bash
# Ricerca eventi correlati in syslog
sudo grep -i "Oct 29 10:" /var/log/syslog | grep -E "(OUT OF|segfault|error)"

# Correlazione con auth log
sudo grep -i "Oct 29 10:" /var/log/auth.log

# Timeline completa
sudo journalctl --since "2025-10-29 10:00:00" --until "2025-10-29 11:00:00" | \
  grep -E "(firewall|iptables|ulogd)"
```

## Scenario 10: Automazione con Cron

### Analisi automatica giornaliera
```bash
# Crea script di report
cat > /usr/local/bin/firewall-daily-report.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y-%m-%d)
REPORT="/var/log/firewall/daily-report-${DATE}.txt"

echo "Firewall Daily Report - ${DATE}" > ${REPORT}
echo "=================================" >> ${REPORT}
echo "" >> ${REPORT}

firewall-manager --stats >> ${REPORT}
echo "" >> ${REPORT}

firewall-manager --threats 40 >> ${REPORT}
echo "" >> ${REPORT}

traffic-analyzer >> ${REPORT}

# Invia via email (se configurato)
# mail -s "Firewall Report ${DATE}" admin@example.com < ${REPORT}
EOF

sudo chmod +x /usr/local/bin/firewall-daily-report.sh

# Aggiungi a crontab
sudo crontab -e
# Aggiungi: 0 1 * * * /usr/local/bin/firewall-daily-report.sh
```

### Cleanup automatico
```bash
# Pulizia PCAP vecchi oltre retention
0 3 * * * /usr/bin/find /var/log/ulogd -name "*.pcap.*.gz" -mtime +30 -delete

# Backup settimanale regole
0 2 * * 0 /usr/sbin/iptables-save > /backup/firewall-$(date +\%Y\%m\%d).txt
```

## Scenario 11: Integrazione con Fail2ban

### Installazione
```bash
sudo apt install fail2ban

# Configura jail per firewall
cat > /etc/fail2ban/jail.d/firewall.conf << 'EOF'
[iptables-firewall]
enabled = true
filter = iptables-firewall
logpath = /var/log/firewall-init.log
maxretry = 5
bantime = 3600
findtime = 600
EOF

# Crea filtro
cat > /etc/fail2ban/filter.d/iptables-firewall.conf << 'EOF'
[Definition]
failregex = INPUT_DROP:.* SRC=<HOST>
ignoreregex =
EOF

# Riavvia fail2ban
sudo systemctl restart fail2ban
```

## Scenario 12: HA Firewall con Keepalived

### Setup su due server
```bash
# Server 1 (MASTER)
sudo apt install keepalived

cat > /etc/keepalived/keepalived.conf << 'EOF'
vrrp_instance VI_1 {
    state MASTER
    interface eth0
    virtual_router_id 51
    priority 100
    advert_int 1
    authentication {
        auth_type PASS
        auth_pass secret123
    }
    virtual_ipaddress {
        10.0.1.100/24
    }
}
EOF

# Server 2 (BACKUP): stessa config ma priority 90

# Sync regole tra server
rsync -avz /etc/firewall/ backup-server:/etc/firewall/
```

## Tips & Tricks

### 1. Performance Optimization
```bash
# Metti regole più frequenti all'inizio
sudo iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT

# Usa conntrack per ridurre overhead
sudo iptables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
```

### 2. Debug Regole
```bash
# Trace pacchetto attraverso chain
sudo iptables -t raw -A PREROUTING -p tcp --dport 8080 -j TRACE
sudo iptables -t raw -A OUTPUT -p tcp --sport 8080 -j TRACE

# Visualizza trace
sudo xtables-monitor -t

# Rimuovi trace dopo debug
sudo iptables -t raw -F
```

### 3. Backup Intelligente
```bash
# Backup con verifica integrità
sudo iptables-save | tee /backup/fw-$(date +%s).txt | md5sum > /backup/fw-$(date +%s).txt.md5

# Restore con verifica
md5sum -c /backup/fw-*.txt.md5 && sudo iptables-restore < /backup/fw-*.txt
```

---

**Nota**: Tutti questi esempi assumono che tu abbia già installato il sistema base. Testa sempre in ambiente non-produzione prima di applicare in produzione!

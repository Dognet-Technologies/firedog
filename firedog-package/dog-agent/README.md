# FireDog Dog Agent

Agent Python per la comunicazione tra macchina target e server FireDog.

## 🚀 Installazione Rapida

### Metodo 1: Script Automatico (Consigliato)

```bash
# Sulla macchina target
sudo ./install.sh
```

Lo script installerà automaticamente:
- ✅ Dipendenze sistema (Python3, pip, iptables)
- ✅ Dipendenze Python (websockets, psutil, scapy)
- ✅ File agent in `/opt/sentinelsuite/firedog/`
- ✅ Configurazione in `/etc/dog-agent/`
- ✅ Servizio systemd `dog-agent`

### Metodo 2: Installazione Manuale

Vedi sezione "Installazione Manuale" sotto.

## ⚙️ Configurazione

Dopo l'installazione, configura l'agent:

```bash
sudo nano /etc/dog-agent/agent.conf
```

**Parametri obbligatori:**
- `server.url`: URL del server FireDog (es: `https://firedog.example.com`)
- `server.api_key`: API key generata dal server

**Parametri opzionali:**
- `server.verify_ssl`: Verifica certificato SSL (default: `true`)
- `agent.notification_interval`: Intervallo heartbeat in secondi (default: `30`)
- `intervention.threat_threshold`: Soglia auto-block minacce (default: `75`)

## 🎯 Pairing con il Server

1. **Sul server**: Crea un target con IP, hostname e MAC address
2. **Sul server**: Avvia il processo di pairing dall'interfaccia web
3. **Sul target**: Avvia l'agent:
   ```bash
   sudo systemctl start dog-agent
   ```
4. **Verifica**: Il pairing dovrebbe completarsi automaticamente in pochi secondi

## 📊 Gestione Servizio

```bash
# Avvia agent
sudo systemctl start dog-agent

# Ferma agent
sudo systemctl stop dog-agent

# Riavvia agent
sudo systemctl restart dog-agent

# Status
sudo systemctl status dog-agent

# Abilita avvio automatico
sudo systemctl enable dog-agent

# Disabilita avvio automatico
sudo systemctl disable dog-agent
```

## 📝 Log

```bash
# Visualizza log in tempo reale
sudo journalctl -u dog-agent -f

# Ultimi 100 log
sudo journalctl -u dog-agent -n 100

# Log file
sudo tail -f /var/log/dog-agent/dog-agent.log
```

## 🔍 Troubleshooting

### Agent non si connette

```bash
# Verifica configurazione
sudo cat /etc/dog-agent/agent.conf

# Verifica connettività
curl https://your-server.com/api/health

# Verifica logs per errori
sudo journalctl -u dog-agent -n 50
```

### Pairing fallisce

Verifica che:
- ✅ IP, hostname e MAC address nel server corrispondano alla macchina target
- ✅ API key sia corretta
- ✅ Sessione di pairing non sia scaduta (timeout 3 minuti)
- ✅ Network consenta connessioni WebSocket

### Controllare identity hash

```bash
# Sul target, esegui:
python3 << 'EOF'
import socket
import uuid
import hashlib

hostname = socket.gethostname()
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
ip = s.getsockname()[0]
s.close()
mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) for i in range(0, 2*6, 2)][::-1])

identity_text = f"{ip}{hostname}{mac}"
identity_hash = hashlib.sha512(identity_text.encode()).hexdigest()

print(f"IP: {ip}")
print(f"Hostname: {hostname}")
print(f"MAC: {mac}")
print(f"Identity Hash: {identity_hash}")
EOF
```

Confronta l'hash generato con quello nel server.

## 🗑️ Disinstallazione

```bash
sudo ./uninstall.sh
```

## 📋 Requisiti

- **OS**: Debian 11/12 o Ubuntu 20.04/22.04
- **Python**: 3.9+
- **Permessi**: Root access
- **Network**: Connessione HTTPS al server FireDog

## 🔐 Security

- ✅ Comunicazione TLS 1.3 (WebSocket Secure)
- ✅ Autenticazione API key SHA512
- ✅ Identity verification con hash
- ✅ File configurazione con permessi 600

## 📦 Struttura File

```
/opt/sentinelsuite/firedog/          # Agent files
├── dog_agent.py                     # Main script
├── config_manager.py
├── websocket_client.py
├── firewall_manager.py
├── threat_detector.py
├── system_monitor.py
├── integrity_monitor.py
└── requirements.txt

/etc/dog-agent/                      # Configuration
└── agent.conf

/var/log/dog-agent/                  # Logs
└── dog-agent.log

/etc/systemd/system/                 # Service
└── dog-agent.service
```

## 🆘 Supporto

Per problemi o domande, consulta la documentazione completa del progetto FireDog.

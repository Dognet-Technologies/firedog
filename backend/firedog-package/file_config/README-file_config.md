# FireDog Configuration Templates

Directory: `/opt/firedog/file_config/`

Questi file di configurazione template permettono di pre-configurare i target prima dell'installazione di FireDog.

## 📁 File Template

### 1. `sudoers-microcyber`
**Destinazione**: `/etc/sudoers.d/microcyber` sul target

File sudoers hardened che garantisce permessi sudo NOPASSWD all'utente microcyber per le operazioni FireDog.

**Permessi configurati**:
- ✅ Gestione iptables (iptables, ip6tables, iptables-save, iptables-restore)
- ✅ Esecuzione binari FireDog (firewall-manager, traffic-analyzer)
- ✅ Gestione servizio systemd (start, stop, restart, status)
- ✅ Lettura log (/var/log/firedog/*, /opt/firedog/logs/*)
- ✅ Analisi network (tcpdump, netstat, ss)
- ✅ Controllo integrità file (sha256sum)

**Installazione manuale**:
```bash
sudo cp sudoers-microcyber /etc/sudoers.d/microcyber
sudo chmod 440 /etc/sudoers.d/microcyber
sudo visudo -c  # Verifica sintassi
```

**Verifica**:
```bash
sudo -u microcyber sudo -n whoami  # Deve stampare "root" senza chiedere password
```

---

### 2. `sshd_config.hardened`
**Destinazione**: `/etc/ssh/sshd_config` sul target

Configurazione SSH hardened per sicurezza massima.

**Modifiche principali**:
- ❌ PasswordAuthentication **disabled** (solo chiave SSH)
- ✅ PubkeyAuthentication **enabled**
- ❌ PermitRootLogin **disabled**
- ✅ Solo utente `microcyber` permesso (AllowUsers)
- ✅ Cifratura forte (ChaCha20-Poly1305, AES-256-GCM)
- ✅ Log verboso per monitoring
- ✅ Timeout e limitazioni connessioni

**⚠️ IMPORTANTE**: Prima di applicare questa configurazione:
1. Verificare che l'autenticazione SSH con chiave funzioni
2. Fare backup del file originale
3. Testare la connessione dopo l'applicazione

**Installazione manuale**:
```bash
# BACKUP!
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup.$(date +%Y%m%d)

# Test configurazione
sudo sshd -t -f sshd_config.hardened

# Applica
sudo cp sshd_config.hardened /etc/ssh/sshd_config
sudo systemctl restart sshd

# Test connessione (da altra shell!)
ssh -i /opt/firedog/ssh/id_ed25519 microcyber@target-ip
```

---

### 3. `firedog-cron`
**Destinazione**: `/etc/cron.d/firedog` sul target

Job cron per esecuzione periodica task FireDog.

**Task schedulati**:
- 🔄 Analisi traffico completa (ogni 5 minuti)
- 📊 Statistiche firewall (ogni 10 minuti)
- 🔍 Rilevamento port scan (ogni 15 minuti)
- 🗑️ Pulizia file vecchi >7 giorni (giornaliero 2 AM)
- 💾 Backup regole iptables (giornaliero 3 AM)
- ❤️ Health check servizio (ogni ora)
- 📈 Statistiche interfacce (ogni ora)
- 📝 Report settimanale (domenica mezzanotte)

**Installazione manuale**:
```bash
sudo cp firedog-cron /etc/cron.d/firedog
sudo chmod 644 /etc/cron.d/firedog

# Verifica sintassi
sudo crontab -l -u microcyber
```

**Monitoraggio esecuzione**:
```bash
sudo grep CRON /var/log/syslog | grep firedog
```

---

## 🛠️ Script Helper

### 4. `ssh-copy-id.sh`
Script per copiare la chiave SSH pubblica sul target.

**Utilizzo**:
```bash
./ssh-copy-id.sh <target-ip> [ssh-port] [username]

# Esempi:
./ssh-copy-id.sh 192.168.1.100
./ssh-copy-id.sh 192.168.1.100 22 microcyber
```

**Cosa fa**:
1. Verifica esistenza chiave pubblica (`/opt/firedog/ssh/id_ed25519.pub`)
2. Crea directory `.ssh` sul target
3. Copia chiave in `~/.ssh/authorized_keys`
4. Testa autenticazione chiave

**Output**:
```
[1/4] Checking if user 'microcyber' exists on target...
[2/4] Creating .ssh directory on target...
[3/4] Copying public key to target...
[4/4] Testing key-based authentication...
✓ SSH key authentication working!
```

---

### 5. `preconfigure-target.sh`
Script completo per pre-configurazione target.

**Utilizzo**:
```bash
./preconfigure-target.sh <target-ip> <operation> [ssh-port] [username]
```

**Operazioni disponibili**:

#### `all` - Configurazione completa
```bash
./preconfigure-target.sh 192.168.1.100 all
```
Esegue tutte le operazioni in sequenza:
1. Copia chiave SSH
2. Configura sudoers
3. Hardening SSH
4. Installa cron jobs

#### `ssh-key` - Solo chiave SSH
```bash
./preconfigure-target.sh 192.168.1.100 ssh-key
```

#### `sudoers` - Solo sudoers
```bash
./preconfigure-target.sh 192.168.1.100 sudoers
```

#### `ssh-harden` - Solo hardening SSH
```bash
./preconfigure-target.sh 192.168.1.100 ssh-harden
```
⚠️ Chiede conferma prima di applicare (disabilita password auth)

#### `cron` - Solo cron jobs
```bash
./preconfigure-target.sh 192.168.1.100 cron
```

#### `check` - Verifica configurazione
```bash
./preconfigure-target.sh 192.168.1.100 check
```

Output esempio:
```
[CHECK] Verifying target configuration...

SSH Key Authentication: ✓ OK
Sudoers NOPASSWD: ✓ OK
User 'microcyber' exists: ✓ OK
SSH Password Auth: ✓ Disabled
Sudoers file: ✓ Exists

Target is ready for FireDog installation
```

---

## 🔐 Setup Chiavi SSH

Prima di usare gli script, generare la coppia di chiavi:

```bash
# Come utente microcyber
sudo -u microcyber ssh-keygen -t ed25519 -f /opt/firedog/ssh/id_ed25519 -N ""

# Verifica
ls -l /opt/firedog/ssh/
# Deve mostrare:
# id_ed25519       (chiave privata - 600)
# id_ed25519.pub   (chiave pubblica - 644)

# Permessi corretti
sudo chown -R microcyber:microcyber /opt/firedog/ssh/
sudo chmod 700 /opt/firedog/ssh/
sudo chmod 600 /opt/firedog/ssh/id_ed25519
sudo chmod 644 /opt/firedog/ssh/id_ed25519.pub
```

---

## 📝 Workflow Completo Pre-configurazione

### Scenario 1: Target completamente nuovo

```bash
# 1. Genera chiavi SSH (se non esistono)
sudo -u microcyber ssh-keygen -t ed25519 -f /opt/firedog/ssh/id_ed25519 -N ""

# 2. Esegui configurazione completa
cd /opt/firedog/file_config
./preconfigure-target.sh 192.168.1.100 all

# 3. Verifica configurazione
./preconfigure-target.sh 192.168.1.100 check

# 4. Ora puoi installare FireDog dalla web console
```

### Scenario 2: Target parzialmente configurato

```bash
# Verifica prima cosa manca
./preconfigure-target.sh 192.168.1.100 check

# Applica solo ciò che serve
./preconfigure-target.sh 192.168.1.100 ssh-key    # Se manca chiave
./preconfigure-target.sh 192.168.1.100 sudoers    # Se manca sudoers
./preconfigure-target.sh 192.168.1.100 ssh-harden # Se SSH non hardened
```

### Scenario 3: Solo setup chiave (installazione interattiva dal web)

```bash
# Copia solo la chiave SSH
./ssh-copy-id.sh 192.168.1.100

# Poi usa la modalità "interattiva" dalla web console
# Il web wizard ti guiderà nel configurare sudoers e SSH
```

---

## 🔍 Monitoring Integrità File

I file in `/opt/firedog/file_config/` sono monitorati dalla pagina **Integrity** della web console.

**File monitorati**:
- `/etc/sudoers.d/microcyber`
- `/etc/ssh/sshd_config`
- `/etc/cron.d/firedog`
- `/usr/local/bin/firewall-manager`
- `/usr/local/bin/traffic-analyzer`

**Come funziona**:
1. Durante installazione vengono calcolati hash SHA256 dei file
2. La web console confronta periodicamente gli hash
3. Modifiche non autorizzate vengono segnalate
4. Puoi ripristinare file modificati usando i template

**Verifica manuale hash**:
```bash
sha256sum /etc/sudoers.d/microcyber
sha256sum /etc/ssh/sshd_config
sha256sum /etc/cron.d/firedog
```

---

## 🚨 Troubleshooting

### Problema: "Permission denied (publickey)"
```bash
# Verifica permessi chiave privata
ls -l /opt/firedog/ssh/id_ed25519  # Deve essere 600

# Verifica chiave copiata sul target
ssh microcyber@target-ip "cat ~/.ssh/authorized_keys"

# Prova connessione con debug
ssh -v -i /opt/firedog/ssh/id_ed25519 microcyber@target-ip
```

### Problema: "sudo requires password"
```bash
# Verifica file sudoers esiste
ssh microcyber@target-ip "sudo ls -l /etc/sudoers.d/microcyber"

# Verifica permessi (deve essere 440)
ssh microcyber@target-ip "sudo stat /etc/sudoers.d/microcyber"

# Verifica sintassi sudoers
ssh microcyber@target-ip "sudo visudo -c"

# Reinstalla sudoers
./preconfigure-target.sh target-ip sudoers
```

### Problema: SSH hardening blocca connessione
```bash
# Se hai accesso fisico al target, ripristina backup:
sudo cp /etc/ssh/sshd_config.backup.* /etc/ssh/sshd_config
sudo systemctl restart sshd

# Altrimenti, usa console fisica/IPMI
```

---

## 📋 Checklist Pre-installazione

Prima di installare FireDog su un target, verifica:

- [ ] Utente `microcyber` esiste sul target
- [ ] Chiave SSH generata su web console (`/opt/firedog/ssh/id_ed25519`)
- [ ] Chiave SSH copiata su target (ssh-copy-id)
- [ ] Connessione SSH con chiave funziona (passwordless)
- [ ] Sudoers configurato (`/etc/sudoers.d/microcyber`)
- [ ] Sudo senza password funziona (`sudo -n whoami`)
- [ ] (Opzionale) SSH hardened (password auth disabled)
- [ ] (Opzionale) Cron jobs installati
- [ ] `preconfigure-target.sh check` restituisce OK

Se tutti i punti sono ✓, il target è pronto per installazione **preconfigured** (senza password).

Se mancano alcuni punti, usa installazione **interactive** (richiede password).

---

## 🔗 Collegamenti Utili

- **Installazione FireDog**: Usa web console → Targets → Install
- **Monitoring integrità**: Web console → Integrity
- **Log targets**: `/var/log/firedog/` e `/opt/firedog/logs/`
- **Documentazione completa**: `/opt/firedog/firedog-package/README.md`

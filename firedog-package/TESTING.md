# 🧪 Guida Test Installazione FireDog su Target

## 📋 Pre-requisiti

**Sul sistema MASTER (dove esegui il test):**
- Accesso SSH come root al target
- Pacchetto `firedog-package/` completo
- Python 3 (per validazione JSON)

**Sul sistema TARGET:**
- OS: Debian 11/12 o Ubuntu 20.04/22.04/24.04
- Accesso SSH come root abilitato (temporaneamente)
- Connessione internet (per `apt-get`)
- Minimo 1GB RAM, 10GB disco

---

## 🚀 Quick Start

### Scenario A: Test CON chiave SSH (Raccomandato)

```bash
cd firedog-package/
./test-target-deployment.sh 192.168.1.50 --with-ssh-key
```

**Questo script:**
1. ✅ Genera chiave SSH temporanea per test
2. ✅ Prepara pacchetto installazione con chiave
3. ✅ Trasferisce pacchetto su target
4. ✅ Esegue installazione interattiva
5. ✅ Testa tutte le funzionalità (SSH, sudo, export, SCP)
6. ✅ Fornisce chiave privata per configurazione web console

**Output atteso:**
```
╔════════════════════════════════════════════╗
║  ✓ TUTTI I TEST PASSATI CON SUCCESSO!     ║
╚════════════════════════════════════════════╝

Il target 192.168.1.50 è pronto per essere aggiunto alla web console.

Informazioni per configurazione web console:
  IP Target:        192.168.1.50
  SSH User:         microcyber
  SSH Port:         22
  SSH Key (privata): /tmp/firedog-test-12345/firedog_master

Comando per copiare chiave privata nel master:
  sudo cp /tmp/firedog-test-12345/firedog_master /opt/firedog/ssh/target_192_168_1_50
  sudo chown www-data:www-data /opt/firedog/ssh/target_192_168_1_50
```

---

### Scenario B: Test SENZA chiave SSH (configurazione manuale dopo)

```bash
cd firedog-package/
./test-target-deployment.sh 192.168.1.50
```

**Questo script:**
1. ✅ Prepara pacchetto senza chiave
2. ✅ Trasferisce e installa su target
3. ⚠️ Salta test SSH (chiave da configurare dopo)

**Configurazione manuale chiave dopo:**

```bash
# 1. Genera chiave sul master
sudo -u www-data ssh-keygen -t ed25519 -f /opt/firedog/ssh/target_192_168_1_50 -N ""

# 2. Sul target, imposta password temporanea
ssh root@192.168.1.50 "echo 'microcyber:TempPass123!' | chpasswd"

# 3. Copia chiave
sudo -u www-data ssh-copy-id -i /opt/firedog/ssh/target_192_168_1_50.pub microcyber@192.168.1.50
# Inserisci password: TempPass123!

# 4. Test
sudo -u www-data ssh -i /opt/firedog/ssh/target_192_168_1_50 microcyber@192.168.1.50 "sudo iptables -L"
```

---

## 📊 Test Eseguiti

Lo script esegue **28+ test automatici**:

### Test Suite 1: Pre-requisiti
- ✅ Connessione SSH root disponibile
- ✅ OS compatibile (Debian/Ubuntu)

### Test Suite 2: Preparazione
- ✅ Pacchetto creato correttamente
- ✅ Chiave SSH generata (se `--with-ssh-key`)
- ✅ Archivio compresso

### Test Suite 3: Transfer
- ✅ Pacchetto trasferito su target

### Test Suite 4: Installazione
- ✅ Esecuzione `install.sh` completata
- ✅ Exit code 0

### Test Suite 5: Componenti
- ✅ Utente `microcyber` creato con shell `/bin/false`
- ✅ Directory `/opt/firedog/.ssh/` creata
- ✅ File `authorized_keys` presente
- ✅ Chiave SSH installata (se fornita)
- ✅ Sudoers `/etc/sudoers.d/microcyber` configurato
- ✅ Script installati:
  - `/usr/local/bin/firewall-manager`
  - `/usr/local/bin/traffic-analyzer`
  - `/usr/local/bin/firedog-ssh-gateway.sh`
  - `/usr/local/sbin/firewall-init.sh`
- ✅ Systemd service installato e abilitato
- ✅ AppArmor profile attivo (se disponibile)
- ✅ Regole iptables configurate (>10 regole)
- ✅ Policy INPUT: DROP

### Test Suite 6: Connessione SSH
- ✅ Autenticazione SSH key funzionante
- ✅ Comando `sudo iptables -L` (NOPASSWD)
- ✅ Export JSON: `firewall-manager --export-json`
- ✅ File JSON creato
- ✅ SCP pull JSON dal target
- ✅ Validazione JSON syntax

### Test Suite 7: Sicurezza
- ✅ Login interattivo bloccato (shell `/bin/false`)
- ✅ Command execution funzionante

---

## 🔍 Troubleshooting

### Errore: "Impossibile connettersi come root"

**Causa:** SSH root non abilitato su target

**Soluzione:**
```bash
# Sul target (console fisica o accesso esistente):
sudo nano /etc/ssh/sshd_config

# Aggiungi temporaneamente:
PermitRootLogin yes

# Riavvia SSH:
sudo systemctl restart sshd

# Copia chiave pubblica dal master:
ssh-copy-id root@TARGET_IP
```

---

### Errore: "OS non Debian/Ubuntu"

**Causa:** Target usa OS non supportato (CentOS, RHEL, etc.)

**Soluzione:** Usa target con Debian/Ubuntu, oppure adatta `install.sh` per altri OS (cambia `apt-get` con `yum`/`dnf`)

---

### Errore: "Sudoers sintassi invalida"

**Causa:** File `/etc/sudoers.d/microcyber` malformato

**Debug:**
```bash
ssh root@TARGET_IP
visudo -c -f /etc/sudoers.d/microcyber
# Mostra errori sintassi
```

**Fix:**
```bash
# Elimina e reinstalla
ssh root@TARGET_IP "rm /etc/sudoers.d/microcyber"
# Poi ri-esegui install.sh
```

---

### Errore: "Autenticazione SSH key fallita"

**Cause possibili:**
1. Chiave non installata correttamente
2. Permessi errati su `.ssh/`
3. SELinux blocca accesso

**Debug:**
```bash
# Verifica chiave su target
ssh root@TARGET_IP "cat /opt/firedog/.ssh/authorized_keys"

# Verifica permessi
ssh root@TARGET_IP "ls -la /opt/firedog/.ssh/"
# Deve essere: drwx------ (700) per .ssh/, -rw------- (600) per authorized_keys

# Test verbose
ssh -vvv -i /path/to/key microcyber@TARGET_IP
# Leggi output per capire dove fallisce
```

**Fix permessi:**
```bash
ssh root@TARGET_IP "chmod 700 /opt/firedog/.ssh && chmod 600 /opt/firedog/.ssh/authorized_keys && chown -R microcyber:microcyber /opt/firedog/.ssh"
```

---

### Warning: "Policy INPUT non DROP"

**Causa:** Installazione non ha completato `firewall-init.sh`

**Fix:**
```bash
ssh root@TARGET_IP "/usr/local/sbin/firewall-init.sh"
```

---

### Errore: "Export JSON fallito"

**Debug:**
```bash
# Test manuale
ssh root@TARGET_IP
su - microcyber -s /bin/bash  # Bypass shell /bin/false per test
sudo /usr/local/bin/firewall-manager --export-json /tmp/test.json
cat /tmp/test.json
```

**Cause comuni:**
- Directory `/opt/firedog/export/` non scrivibile
- Script `firewall-manager` non eseguibile
- Errore Python nel script

---

## 📝 Prossimi Passi Dopo Test Riuscito

### 1. Salva chiave privata nel master

```bash
# Se test con --with-ssh-key
sudo cp /tmp/firedog-test-*/firedog_master /opt/firedog/ssh/target_ID
sudo chown www-data:www-data /opt/firedog/ssh/target_ID
sudo chmod 600 /opt/firedog/ssh/target_ID
```

### 2. Aggiungi target nella web console

**Via API:**
```bash
curl -X POST http://localhost:8000/api/targets/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Target-Test",
    "ip_address": "192.168.1.50",
    "ssh_port": 22,
    "ssh_user": "microcyber",
    "description": "Target di test installazione"
  }'
```

**Via Django Admin:**
1. Accedi: http://localhost:8000/admin/
2. Targets → Add Target
3. Compila campi:
   - Name: Target-Test
   - IP Address: 192.168.1.50
   - SSH Port: 22
   - SSH User: microcyber
4. Save

### 3. Testa pull automatico JSON

```bash
# Sul master Django
python manage.py pull_targets_status

# Verifica JSON scaricato
ls -lh /tmp/firedog-targets-status/*/status.json

# Importa nel DB
python manage.py import_targets_status

# Verifica import
python manage.py shell
>>> from targets.models import FirewallStats
>>> FirewallStats.objects.filter(target__ip_address='192.168.1.50').latest('imported_at')
```

### 4. Configura cron automatico

```bash
# Aggiungi a crontab Django user
sudo crontab -e -u www-data

# Pull ogni 5 minuti
*/5 * * * * cd /home/user/firedog/backend && python manage.py pull_targets_status >> /var/log/firedog/pull.log 2>&1

# Import ogni 6 minuti
*/6 * * * * cd /home/user/firedog/backend && python manage.py import_targets_status >> /var/log/firedog/import.log 2>&1
```

---

## 🔐 Security Checklist Post-Installazione

- [ ] Utente `microcyber` ha shell `/bin/false`
- [ ] SSH key authentication funzionante
- [ ] Password authentication SSH disabilitata sul target
- [ ] Sudoers configurato solo per comandi whitelisted
- [ ] AppArmor profile attivo (se disponibile)
- [ ] Policy iptables DROP attiva
- [ ] SSH root disabilitato sul target (dopo test)
- [ ] Firewall service abilitato e attivo
- [ ] Log `/var/log/firedog/ssh-gateway.log` funzionante

**Hardening finale SSH (opzionale):**
```bash
# Copia sshd_config.hardened sul target
scp firedog-package/file_config/sshd_config.hardened root@TARGET_IP:/tmp/

# Applica (ATTENZIONE: testa prima che SSH key funzioni!)
ssh root@TARGET_IP "
    cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup
    sshd -t -f /tmp/sshd_config.hardened && \
    cp /tmp/sshd_config.hardened /etc/ssh/sshd_config && \
    systemctl restart sshd
"
```

---

## 📞 Support

**Log importanti:**
- Installazione: `/var/log/firewall-init.log`
- SSH Gateway: `/var/log/firedog/ssh-gateway.log`
- Export JSON: `/var/log/firedog-export.log`
- Systemd: `journalctl -u firedog`

**Comandi utili debug:**
```bash
# Stato completo target
ssh root@TARGET_IP "systemctl status firedog"
ssh root@TARGET_IP "iptables -L -n -v"
ssh root@TARGET_IP "journalctl -u firedog -n 50"

# Test manuale export
ssh -i /opt/firedog/ssh/target_ID microcyber@TARGET_IP "sudo firewall-manager --export-json /opt/firedog/export/manual.json"
scp -i /opt/firedog/ssh/target_ID microcyber@TARGET_IP:/opt/firedog/export/manual.json .
python3 -m json.tool manual.json
```

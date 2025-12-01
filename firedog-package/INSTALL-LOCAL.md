# 🚀 Guida Installazione FireDog su Target (Locale)

## 📋 Panoramica

Questa guida spiega come installare FireDog **localmente su un target** connettendosi manualmente al sistema.

**Workflow:**
1. **[UNA TANTUM]** Installa file pacchetto sul master in `/opt/firedog/firedog-package`
2. Prepara pacchetto dal master
3. Copia pacchetto sul target via SCP
4. Connettiti al target (con qualsiasi utente con sudo)
5. Esegui `sudo ./install.sh` SUL TARGET
6. L'installer crea automaticamente l'utente `microcyber`

---

## 🎯 Scenario 1: Installazione CON chiave SSH (Raccomandato)

### Passo 0: Installa file pacchetto sul master (UNA TANTUM)

**Questo passo va fatto solo la prima volta o quando aggiorni i file del pacchetto:**

```bash
cd /home/user/firedog/firedog-package/
sudo ./install-on-master.sh
```

**Output:**
```
✓ Installazione completata!

File del pacchetto installati in:
  /opt/firedog/firedog-package/

Struttura directory master:
  /opt/firedog/
  ├── firedog-package/  (file sorgente per target)
  ├── .ssh/             (chiavi SSH per target)
  ├── exports/          (JSON esportati dai target)
  ├── logs/             (log operazioni)
  └── temp/             (file temporanei)
```

### Passo 1: Prepara il pacchetto (sul master)

```bash
cd /opt/firedog/firedog-package/
sudo ./prepare-package.sh --with-ssh-key
```

**Output:**
```
✓ Archivio creato: /tmp/firedog-package.tar.gz
✓ Chiave SSH generata e salvata

Chiave PRIVATA (master): /opt/firedog/.ssh/firedog_target_20251130_180000
Chiave PUBBLICA (pacchetto): firedog_ssh_key.pub

→ La chiave privata è stata salvata in modo permanente in:
  /opt/firedog/.ssh/
```

**✅ Chiave salvata permanentemente** in `/opt/firedog/.ssh/` sul master

---

### Passo 2: Copia pacchetto sul target

```bash
# Sostituisci 'simone' con il tuo utente
# Sostituisci '192.168.1.50' con IP del tuo target
scp /tmp/firedog-package.tar.gz simone@192.168.1.50:/tmp/
```

---

### Passo 3: Connettiti al target

```bash
ssh simone@192.168.1.50
```

**Nota:** Puoi usare **qualsiasi utente** che abbia accesso sudo (simone, admin, root, etc.)

---

### Passo 4: Esegui installazione SUL TARGET

```bash
# Ora sei sul target come 'simone'

cd /tmp
tar xzf firedog-package.tar.gz
cd firedog-package-*/
sudo ./install.sh
```

**Cosa succede:**
1. Script richiede privilegi root (sudo)
2. Aggiorna sistema e installa dipendenze
3. **CREA automaticamente utente `microcyber`** con shell `/bin/false`
4. Installa chiave SSH in `/opt/firedog/.ssh/authorized_keys`
5. Configura sudoers per `microcyber`
6. Installa firewall-manager, traffic-analyzer, gateway SSH
7. Configura systemd service
8. Installa AppArmor profile (se disponibile)
9. Chiede conferma per inizializzazione firewall

**Conferme richieste:**
```
Procedere con l'inizializzazione? (yes/no):
```
Digita `yes` e premi INVIO.

**⚠️ ATTENZIONE:** L'inizializzazione attiva policy DROP. Assicurati di avere:
- Accesso console fisica (se SSH si blocca)
- OPPURE regole SSH già configurate (lo script le include automaticamente)

---

### Passo 5: Installazione completata!

```
╔════════════════════════════════════════════╗
║  Installazione completata con successo!    ║
╚════════════════════════════════════════════╝

Comandi disponibili:
  firewall-manager --help
  firewall-manager --list
  ...
```

**L'utente `microcyber` è ora creato e configurato!**

---

### Passo 6: Verifica installazione (ancora sul target)

```bash
# Verifica utente creato
id microcyber
# Output: uid=1001(microcyber) gid=1001(microcyber) groups=1001(microcyber)

# Verifica shell
grep microcyber /etc/passwd
# Output: microcyber:x:1001:1001::/home/microcyber:/bin/false

# Verifica chiave SSH installata
sudo cat /opt/firedog/.ssh/authorized_keys
# Output: ssh-ed25519 AAAA... firedog-master

# Verifica firewall attivo
sudo iptables -L | head
# Output: Chain INPUT (policy DROP)

# Verifica service
systemctl status firedog
# Output: active (exited)
```

---

### Passo 7: Testa connessione SSH dal master

```bash
# Torna sul tuo PC/master
exit  # Esci dal target

# Usa la chiave privata salvata in /opt/firedog/.ssh/
SSH_KEY="/opt/firedog/.ssh/firedog_target_20251130_180000"  # Usa il path mostrato allo Step 1

# Test connessione
ssh -i $SSH_KEY microcyber@192.168.1.50 "whoami"
# Output: microcyber

# Test comando firewall
ssh -i $SSH_KEY microcyber@192.168.1.50 "sudo iptables -L -n | head"
# Output: Chain INPUT (policy DROP) ...

# Test export JSON
ssh -i $SSH_KEY microcyber@192.168.1.50 "sudo firewall-manager --export-json /opt/firedog/export/test.json"

# Scarica JSON
scp -i $SSH_KEY microcyber@192.168.1.50:/opt/firedog/export/test.json .
cat test.json | python3 -m json.tool | head -20
```

**Se tutto funziona: ✅ INSTALLAZIONE RIUSCITA!**

---

### Passo 8: Configura ownership chiave per web console

```bash
# La chiave è già salvata in /opt/firedog/.ssh/
# Configura solo ownership per www-data (Django)

sudo chown www-data:www-data $SSH_KEY
sudo chmod 600 $SSH_KEY

# Verifica
ls -l $SSH_KEY
# Output: -rw------- 1 www-data www-data ... /opt/firedog/.ssh/firedog_target_...

# Ora la web console può usare questa chiave per connettersi
```

---

## 🔧 Scenario 2: Installazione SENZA chiave SSH

### Differenza

Non generi chiave SSH durante preparazione pacchetto. La configuri **manualmente DOPO** l'installazione.

### Passo 0: Installa file pacchetto sul master (UNA TANTUM)

```bash
cd /home/user/firedog/firedog-package/
sudo ./install-on-master.sh
```

### Passo 1-4: Come Scenario 1 ma senza `--with-ssh-key`

```bash
# Passo 1
cd /opt/firedog/firedog-package/
sudo ./prepare-package.sh  # SENZA --with-ssh-key

# Passo 2-4: identici
```

### Passo 5: Configurazione manuale chiave SSH

**Opzione A - Dal master:**

```bash
# Sul master, genera chiave in /opt/firedog/.ssh/
sudo mkdir -p /opt/firedog/.ssh
sudo ssh-keygen -t ed25519 -f /opt/firedog/.ssh/target_key -N ""

# Copia sul target (richiederà password di microcyber)
# Prima imposta password temporanea su target:
ssh simone@192.168.1.50
sudo passwd microcyber  # Imposta password temporanea

# Poi dal master:
sudo ssh-copy-id -i /opt/firedog/.ssh/target_key.pub microcyber@192.168.1.50
# Inserisci password temporanea

# Configura ownership
sudo chown www-data:www-data /opt/firedog/.ssh/target_key
sudo chmod 600 /opt/firedog/.ssh/target_key

# Test
ssh -i /opt/firedog/.ssh/target_key microcyber@192.168.1.50 "sudo iptables -L"
```

**Opzione B - Manualmente sul target:**

```bash
# Sul target (come root o con sudo)
sudo -i

# Copia chiave pubblica del master (se esiste già)
cat >> /opt/firedog/.ssh/authorized_keys << 'EOF'
ssh-ed25519 AAAA...tua_chiave_pubblica_qui...
EOF

# Fix permessi
chmod 600 /opt/firedog/.ssh/authorized_keys
chown microcyber:microcyber /opt/firedog/.ssh/authorized_keys
```

---

## 🧪 Test Post-Installazione

Script automatico per verificare installazione:

```bash
# Sul master, dopo installazione
cd /home/user/firedog/firedog-package/
./test-post-install.sh 192.168.1.50 /opt/firedog/ssh/target_key
```

---

## ❓ FAQ

### Q: Quale utente uso per connettermi al target?

**R:** Qualsiasi utente con accesso sudo (simone, admin, tuo_user, etc.)
```bash
ssh tuo_user@target  # OK
ssh simone@target    # OK
ssh admin@target     # OK
```

L'importante è che possa eseguire `sudo ./install.sh`

---

### Q: L'utente microcyber esiste già sul mio target, cosa succede?

**R:** Lo script lo rileva e:
- Aggiorna la shell a `/bin/false` (sicurezza)
- Aggiunge la chiave SSH se non presente
- **NON** sovrascrive configurazioni esistenti

---

### Q: Posso usare un utente diverso da 'microcyber'?

**R:** Sì, modifica la variabile `FIREDOG_USER` in `install.sh`:
```bash
# install.sh linea 55
FIREDOG_USER="tuo_utente_preferito"
```

---

### Q: L'installazione blocca la mia connessione SSH?

**R:** Lo script include automaticamente regola per SSH porta 22:
```bash
# firewall-init.sh linea 205
iptables -A INPUT -p tcp --dport 22 -m conntrack --ctstate NEW -j SSH_PROTECT
```

**Se usi porta SSH diversa**, modifica `firewall-init.sh` PRIMA di eseguire:
```bash
# Cambia da:
iptables -A INPUT -p tcp --dport 22 ...

# A:
iptables -A INPUT -p tcp --dport TUA_PORTA ...
```

---

### Q: Come annullo l'installazione se qualcosa va storto?

**R:** Durante l'installazione, prima dell'inizializzazione firewall:
```bash
# Quando chiede: "Procedere con l'inizializzazione? (yes/no):"
Digita: no

# Poi rimuovi manualmente:
sudo rm -rf /opt/firedog
sudo userdel -r microcyber
sudo rm /etc/sudoers.d/microcyber
sudo rm /usr/local/bin/firewall-manager
sudo rm /usr/local/bin/traffic-analyzer
sudo systemctl disable firedog
sudo rm /etc/systemd/system/firewall.service
```

---

### Q: Dopo l'installazione, come aggiungo il target alla web console?

**R:** Via Django Admin o API:

**Django Admin:**
1. http://localhost:8000/admin/targets/target/add/
2. Compila:
   - Name: Target-Debian-01
   - IP: 192.168.1.50
   - SSH Port: 22
   - SSH User: microcyber
3. Save

**API:**
```bash
curl -X POST http://localhost:8000/api/targets/ \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Target-Debian-01",
    "ip_address": "192.168.1.50",
    "ssh_port": 22,
    "ssh_user": "microcyber"
  }'
```

---

## 📞 Troubleshooting

### Errore: "permission denied" durante ./install.sh

**Soluzione:**
```bash
chmod +x install.sh
sudo ./install.sh
```

---

### Errore: "visudo: syntax error in /etc/sudoers.d/microcyber"

**Causa:** File sudoers corrotto

**Soluzione:**
```bash
sudo rm /etc/sudoers.d/microcyber
# Ri-esegui installazione
```

---

### SSH non funziona dopo installazione firewall

**Debug:**
```bash
# Sul target (console fisica o SSH esistente prima del firewall)
sudo iptables -L INPUT -n -v | grep 22

# Dovrebbe mostrare:
# ACCEPT tcp -- * * 0.0.0.0/0 0.0.0.0/0 tcp dpt:22
```

**Fix temporaneo:**
```bash
# Permetti SSH temporaneamente
sudo iptables -I INPUT 1 -p tcp --dport 22 -j ACCEPT

# Poi salva regole
sudo iptables-save > /etc/firewall/iptables.rules
```

---

### JSON export non funziona

**Test manuale:**
```bash
ssh -i /opt/firedog/ssh/key microcyber@target

# Sul target:
sudo /usr/local/bin/firewall-manager --export-json /tmp/test.json
cat /tmp/test.json | python3 -m json.tool
```

---

## 🔐 Security Checklist Post-Installazione

- [ ] Utente `microcyber` creato con shell `/bin/false`
- [ ] SSH key authentication funzionante
- [ ] Sudoers configurato correttamente (visudo -c)
- [ ] AppArmor profile attivo (se disponibile)
- [ ] Firewall policy DROP attiva
- [ ] SSH porta 22 accessibile
- [ ] Export JSON funzionante
- [ ] Service firedog enabled e active
- [ ] Password utente microcyber NON impostata (o rimossa dopo test)

**Hardening opzionale:**
```bash
# Disabilita password SSH globalmente
sudo nano /etc/ssh/sshd_config
# PasswordAuthentication no
sudo systemctl restart sshd
```

---

## 📚 Files Importanti

**Sul master:**
```
/opt/firedog/.ssh/
  firedog_target_TIMESTAMP       # Chiave privata per connessione a target
  firedog_target_TIMESTAMP.pub   # Chiave pubblica (copiata nel pacchetto)
```

**Sul target dopo installazione:**
```
/opt/firedog/
  .ssh/authorized_keys           # Chiave pubblica per accesso master
  export/status.json             # Export automatico (ogni 60s)

/usr/local/bin/
  firewall-manager               # CLI principale
  traffic-analyzer               # Analisi traffico
  firedog-ssh-gateway.sh         # Gateway forced commands

/etc/firewall/
  iptables.rules                 # Regole salvate
  custom_rules.conf              # Regole personalizzate

/var/log/
  firewall-init.log              # Log installazione
  firedog/ssh-gateway.log        # Log comandi SSH
  firedog-export.log             # Log export automatico
```

---

## ✅ Prossimi Passi

Dopo installazione riuscita:

1. **Aggiungi target in web console** (vedi FAQ)
2. **Configura pull automatico** (cron ogni 5 min)
3. **Testa API firewall** via web console
4. **Monitora log** per verificare funzionamento

Buona installazione! 🚀

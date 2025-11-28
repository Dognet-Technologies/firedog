# FireDog - Ruoli e Permessi

Sistema di autorizzazione basato su ruoli per FireDog.

## 📋 Ruoli Disponibili

### 1. Admin (microcyber)
**Permessi completi:**
- ✅ Visualizzare tutti i dati (targets, regole, statistiche, minacce)
- ✅ Creare/modificare/eliminare targets
- ✅ Aggiungere/rimuovere regole firewall
- ✅ Bloccare/sbloccare IP
- ✅ Modificare configurazioni
- ✅ Eseguire operazioni SSH sui target
- ✅ Accesso Django Admin

### 2. Reporter (user1)
**Permessi sola lettura:**
- ✅ Visualizzare targets e loro stato
- ✅ Visualizzare regole firewall
- ✅ Visualizzare minacce rilevate
- ✅ Visualizzare statistiche e dashboard
- ✅ Visualizzare audit logs
- ❌ **NON** può creare/modificare/eliminare risorse
- ❌ **NON** può aggiungere/rimuovere regole
- ❌ **NON** può eseguire operazioni SSH

## 🔐 Autenticazione

### JWT Token
FireDog usa **JWT (JSON Web Tokens)** per l'autenticazione:

```bash
# 1. Ottenere token
POST /api/token/
{
    "username": "microcyber",
    "password": "your_password"
}

# Response:
{
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}

# 2. Usare token nelle richieste
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

### Token Lifetime
- **Access Token**: 60 minuti
- **Refresh Token**: 24 ore (1440 minuti)

### CSRF Protection
Django CSRF protection è attivo per tutte le richieste non-API.

## 🛡️ Custom Permissions

### IsAdminUser
Solo utenti nel gruppo "Admin" possono accedere.

**Uso:**
```python
from accounts.permissions import IsAdminUser

class MyView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
```

### IsReporterOrAdmin
Utenti nel gruppo "Reporter" o "Admin".

**Uso:**
```python
from accounts.permissions import IsReporterOrAdmin

class MyView(APIView):
    permission_classes = [IsAuthenticated, IsReporterOrAdmin]
```

### IsAdminOrReadOnly
Admin può tutto, altri solo GET/HEAD/OPTIONS.

**Uso:**
```python
from accounts.permissions import IsAdminOrReadOnly

class MyViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
```

## 🔧 API Gestione Regole Firewall

### Aggiungere Regola (Solo Admin)

```http
POST /api/rules/add_via_ssh/
Authorization: Bearer <token>
Content-Type: application/json

{
    "target_id": 1,
    "chain": "INPUT",
    "port": 80,
    "protocol": "tcp",
    "source_ip": "192.168.1.0/24",  // opzionale
    "comment": "HTTP traffic"         // opzionale
}
```

**Response Success (201):**
```json
{
    "success": true,
    "message": "Regola aggiunta con successo",
    "command": "sudo /usr/local/bin/firewall-manager --add-input 80 tcp --source 192.168.1.0/24 --comment \"HTTP traffic\"",
    "output": "[✓] Regola INPUT aggiunta: TCP/80 da 192.168.1.0/24\n"
}
```

**Response Error (500):**
```json
{
    "success": false,
    "message": "Errore aggiunta regola",
    "command": "...",
    "error": "Porta già in uso\n"
}
```

### Rimuovere Regola (Solo Admin)

```http
POST /api/rules/remove_via_ssh/
Authorization: Bearer <token>
Content-Type: application/json

{
    "target_id": 1,
    "chain": "INPUT",
    "rule_number": 5
}
```

**Response Success (200):**
```json
{
    "success": true,
    "message": "Regola rimossa con successo",
    "command": "sudo /usr/local/bin/firewall-manager --remove INPUT 5",
    "output": "[✓] Regola #5 rimossa da chain INPUT\n"
}
```

### Validazioni Input

**AddFirewallRuleViaSSHSerializer:**
- `target_id`: required, target deve esistere e essere online
- `chain`: required, choices: INPUT, OUTPUT
- `port`: required, range: 1-65535
- `protocol`: default: tcp, choices: tcp, udp
- `source_ip`: opzionale, solo per INPUT, validato come IP
- `dest_ip`: opzionale, solo per OUTPUT, validato come IP
- `comment`: opzionale, max 256 char, sanitizzato (solo alfanumerici, spazi, -, _, .)

**RemoveFirewallRuleViaSSHSerializer:**
- `target_id`: required, target deve esistere e essere online
- `chain`: required, choices: INPUT, OUTPUT, FORWARD
- `rule_number`: required, min: 1

## 🔒 Sicurezza

### Input Sanitization
Tutti gli input sono sanitizzati:
- **Commenti**: rimossi caratteri shell pericolosi (solo `a-zA-Z0-9 -_.`)
- **IP addresses**: validati con Django validators
- **Porte**: validate range 1-65535
- **Chain/Protocol**: scelte fisse (no input arbitrario)

### Command Construction
Comandi SSH costruiti in modo sicuro:
```python
cmd_parts = [
    'sudo', '/usr/local/bin/firewall-manager',
    f'--add-{chain_lower}',
    str(port),  # Sempre int
    protocol    # Sempre da choices
]
```

### Audit Logging
Tutte le operazioni sono registrate in `AuditLog`:
- Utente che ha eseguito l'operazione
- Azione (add_firewall_rule_ssh, remove_firewall_rule_ssh)
- Target coinvolto
- Dettagli (comando, parametri, exit_code)
- Timestamp
- Successo/fallimento

### SSH Timeout
Timeout di 30 secondi per operazioni SSH (prevenzione hang).

## 📝 Setup Iniziale

### 1. Eseguire Migrazioni

```bash
cd /opt/firedog/backend
source /opt/firedog/venv/bin/activate  # Se virtualenv presente
python manage.py migrate accounts
```

Questo creerà:
- Gruppo "Admin" con tutti i permessi
- Gruppo "Reporter" con permessi view only
- Assegnerà microcyber → Admin
- Assegnerà user1 → Reporter (se esiste)

### 2. Creare Utenti

```bash
# Creare utente Reporter
python manage.py createsuperuser --username user1 --email user1@example.com

# Assegnare al gruppo Reporter
python manage.py shell
>>> from django.contrib.auth.models import User, Group
>>> user1 = User.objects.get(username='user1')
>>> reporter_group = Group.objects.get(name='Reporter')
>>> user1.groups.add(reporter_group)
>>> user1.is_staff = False  # Reporter non ha accesso Django Admin
>>> user1.save()
```

### 3. Verificare Permessi

```bash
# Controllare gruppi utente
python manage.py shell
>>> from django.contrib.auth.models import User
>>> microcyber = User.objects.get(username='microcyber')
>>> microcyber.groups.values_list('name', flat=True)
<QuerySet ['Admin']>

>>> user1 = User.objects.get(username='user1')
>>> user1.groups.values_list('name', flat=True)
<QuerySet ['Reporter']>
```

## 🧪 Testing

### Test Permessi Admin

```bash
# Login come Admin
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "microcyber", "password": "your_password"}'

# Aggiungere regola (deve funzionare)
curl -X POST http://localhost:8000/api/rules/add_via_ssh/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"target_id": 1, "chain": "INPUT", "port": 8080, "protocol": "tcp", "comment": "Test"}'
```

### Test Permessi Reporter

```bash
# Login come Reporter
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "user1", "password": "reporter_password"}'

# Visualizzare regole (deve funzionare)
curl http://localhost:8000/api/rules/ \
  -H "Authorization: Bearer <access_token>"

# Aggiungere regola (deve fallire con 403)
curl -X POST http://localhost:8000/api/rules/add_via_ssh/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"target_id": 1, "chain": "INPUT", "port": 8080, "protocol": "tcp"}'

# Expected response:
# {
#   "detail": "Solo gli amministratori possono eseguire questa azione."
# }
```

## 📚 Riferimenti

- Django Groups & Permissions: https://docs.djangoproject.com/en/stable/topics/auth/
- Django REST Framework Permissions: https://www.django-rest-framework.org/api-guide/permissions/
- SimpleJWT: https://django-rest-framework-simplejwt.readthedocs.io/

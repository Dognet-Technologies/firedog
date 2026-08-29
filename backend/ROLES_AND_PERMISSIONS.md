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

Le regole sono un CRUD standard DRF su `/api/rules/` (`FirewallRuleViewSet`):
lettura per tutti gli utenti autenticati, scrittura solo Admin
(`IsAdminOrReadOnly`). Creazione/cancellazione dispatchano il comando
all'agent del target via WebSocket (`rules.services.dispatch_add_rule` /
`dispatch_remove_rule`) — se l'agent non è connesso la regola resta
persistita in DB con `is_synced=False` in attesa della prossima
riconciliazione. Non c'è più un percorso SSH diretto: `connection_type="ssh"`
è legacy e non più supportato per la gestione regole.

### Aggiungere Regola (Solo Admin)

```http
POST /api/rules/
Authorization: Bearer <token>
Content-Type: application/json

{
    "target": 1,
    "chain": "INPUT",
    "port": 80,
    "protocol": "tcp",
    "action": "ACCEPT",
    "source_ip": "192.168.1.0/24",  // opzionale
    "interface": "eth0",             // opzionale, NIC specifica (multi-homed)
    "comment": "HTTP traffic"        // opzionale
}
```

**Response Success (201):** il record `FirewallRule` creato (vedi
`FirewallRuleSerializer`), con `is_synced=false` finché l'agent non conferma.

### Rimuovere Regola (Solo Admin)

```http
DELETE /api/rules/{id}/
Authorization: Bearer <token>
```

**Response Success (204):** nessun body.

### Validazioni Input

`FirewallRuleSerializer` (ModelSerializer):
- `target`: required, FK a un Target esistente
- `chain`: required, choices: INPUT, OUTPUT, FORWARD
- `interface`: opzionale, NIC specifica — applicata come `-i` su INPUT, `-o`
  su OUTPUT, non supportata su FORWARD (vedi tool MCP `create_rule`)
- `port`: opzionale, range: 1-65535
- `protocol`: default: tcp, choices: tcp, udp, icmp, all
- `source_ip` / `dest_ip`: opzionali, validati come IP
- `comment`: opzionale, max 256 char

## 🔒 Sicurezza

### Input Sanitization
- **IP addresses**: validati con Django validators
- **Porte**: validate range 1-65535
- **Chain/Protocol/Action**: scelte fisse (no input arbitrario)

### Audit Logging
Le operazioni di scrittura via MCP sono registrate in `AuditLog` (utente,
azione, target, valori). Le operazioni via REST ereditano il logging
standard del ViewSet.

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
curl -X POST http://localhost:8000/api/rules/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"target": 1, "chain": "INPUT", "port": 8080, "protocol": "tcp", "action": "ACCEPT", "comment": "Test"}'
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
curl -X POST http://localhost:8000/api/rules/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"target": 1, "chain": "INPUT", "port": 8080, "protocol": "tcp", "action": "ACCEPT"}'

# Expected response:
# {
#   "detail": "Solo gli amministratori possono eseguire questa azione."
# }
```

## 📚 Riferimenti

- Django Groups & Permissions: https://docs.djangoproject.com/en/stable/topics/auth/
- Django REST Framework Permissions: https://www.django-rest-framework.org/api-guide/permissions/
- SimpleJWT: https://django-rest-framework-simplejwt.readthedocs.io/

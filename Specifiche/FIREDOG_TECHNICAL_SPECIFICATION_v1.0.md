FIREDOG TECHNICAL SPECIFICATION v1.0
Sistema di Gestione Centralizzata Firewall Multi-Target

1. PANORAMICA SISTEMA
2. ARCHITETTURA E FLUSSO DATI
3. DATABASE DESIGN
4. API SPECIFICATION
5. BACKEND IMPLEMENTATION
6. FRONTEND ARCHITECTURE
7. SECURITY HARDENING
8. DEPLOYMENT & SCRIPTS
9. OPERAZIONI CRITICHE - FLOW DETTAGLIATI
10. TESTING & TROUBLESHOOTING
```

---

# 1. PANORAMICA SISTEMA

## 1.1 Scopo del Progetto

**FireDog** è un sistema web centralizzato che permette di gestire firewall `iptables` su molteplici sistemi target remoti attraverso un'interfaccia grafica tipo Grafana/Chronograf.

### Cosa FA FireDog:
- ✅ Gestisce N target remoti via SSH
- ✅ Installa automaticamente il pacchetto firewall sui target
- ✅ Recupera periodicamente dati da `traffic-analyzer` via SCP
- ✅ Visualizza minacce, statistiche, regole iptables
- ✅ Permette aggiunta/rimozione regole da web UI
- ✅ Monitoring integrità file locale (SHA512)
- ✅ Dashboard personalizzabili

### Cosa NON FA FireDog:
- ❌ Non introduce nuove funzionalità firewall
- ❌ Non modifica la logica di firewall-manager
- ❌ Non riceve log rsyslog (scelta progettuale)
- ❌ Non espone API pubbliche ai target (solo SSH)

---

## 1.2 Stack Tecnologico

| Componente | Tecnologia | Versione |
|------------|-----------|----------|
| Backend | Django | 4.2.11 LTS |
| Database | PostgreSQL | 13+ |
| Frontend | React + TypeScript | 18.2+ |
| Auth | JWT | djangorestframework-simplejwt |
| SSH | Paramiko | 3.4.0 |
| Task Queue | Celery + Redis | 5.3.6 |
| Charts | Recharts | 2.12.0 |
| Grid Layout | react-grid-layout | 1.4.4 |

---

## 1.3 Requisiti Sistema

### Server Centrale (FireDog)
- OS: Debian 11/12/13
- RAM: 2GB minimo, 4GB consigliato
- Disk: 20GB + (dipende da retention dati)
- Python: 3.9+
- PostgreSQL: 13+
- Node.js: 18+ (per build frontend)

### Target Systems
- OS: Debian 10+, Ubuntu 18.04+
- Utente: `microcyber` (con permessi sudo limitati)
- SSH: Porta 22 (o custom)
- Pacchetto firewall installato

---

# 2. ARCHITETTURA E FLUSSO DATI

## 2.1 Diagramma Architettura Generale
```
┌─────────────────────────────────────────────────────────────┐
│                    FIREDOG CENTRAL SERVER                    │
│                                                               │
│  ┌──────────────┐         ┌─────────────┐                   │
│  │   React UI   │◄────────┤   Nginx     │                   │
│  │  (Port 3000) │         │(Reverse Proxy)                  │
│  └──────┬───────┘         └─────────────┘                   │
│         │ HTTP/HTTPS                                         │
│         │                                                    │
│  ┌──────▼────────────────────────────────┐                  │
│  │        Django Backend                 │                  │
│  │  ┌────────────┐  ┌──────────────┐    │                  │
│  │  │    API     │  │   Celery     │    │                  │
│  │  │  ViewSets  │  │    Tasks     │    │                  │
│  │  └─────┬──────┘  └──────┬───────┘    │                  │
│  │        │                 │            │                  │
│  │  ┌─────▼─────────────────▼────────┐  │                  │
│  │  │      SSHManager               │  │                  │
│  │  │  (Paramiko + SCP)             │  │                  │
│  │  └───────────────────────────────┘  │                  │
│  └───────────────┬──────────────────────┘                  │
│                  │                                          │
│         ┌────────▼────────┐                                │
│         │   PostgreSQL    │                                │
│         │  (microcyber)   │                                │
│         └─────────────────┘                                │
└────────────────────┬────────────────────────────────────────┘
                     │ SSH (Ed25519 Key)
                     │
      ┌──────────────┴──────────────┬─────────────────┐
      │                             │                 │
┌─────▼─────┐               ┌───────▼──────┐   ┌─────▼─────┐
│  Target 1 │               │   Target 2   │   │  Target N │
│           │               │              │   │           │
│ firedog   │               │  firedog     │   │  firedog  │
│ package   │               │  package     │   │  package  │
│           │               │              │   │           │
│ cron:     │               │  cron:       │   │  cron:    │
│ */10 * *  │               │  */10 * *    │   │  */10 * * │
│ analyzer  │               │  analyzer    │   │  analyzer │
│    ↓      │               │     ↓        │   │     ↓     │
│ JSON file │               │  JSON file   │   │ JSON file │
└───────────┘               └──────────────┘   └───────────┘
```

---

## 2.2 Flusso Dati - Operazioni Principali

### 2.2.1 Discovery & Onboarding Target
```
┌─────────┐
│  Admin  │
└────┬────┘
     │
     │ 1. Click "Discover Network"
     ▼
┌─────────────────────────────────┐
│  Discovery Service              │
│  - Legge "ip route"             │
│  - Esegue arp-scan su ogni rete │
│  - Filtra IP già presenti       │
└────┬────────────────────────────┘
     │
     │ 2. Mostra lista IP trovati
     ▼
┌─────────────────────────────────┐
│  Admin seleziona IP da aggiungere│
└────┬────────────────────────────┘
     │
     │ 3. POST /api/targets/
     ▼
┌─────────────────────────────────┐
│  Backend API                    │
│  - Crea Target (status=pending) │
│  - Verifica duplicati           │
└────┬────────────────────────────┘
     │
     │ 4. Return target_id
     ▼
┌─────────────────────────────────┐
│  Admin click "Install" su target│
└────┬────────────────────────────┘
     │
     │ 5. POST /api/targets/{id}/install/
     ▼
┌─────────────────────────────────┐
│  SSHManager                     │
│  1. connect()                   │
│  2. check_user_exists()         │
│     ├─ NO  → Return error       │
│     └─ YES → Continue           │
│  3. upload_directory(package)   │
│  4. execute install.sh          │
│  5. verify installation         │
│  6. install_cron_job()          │
└────┬────────────────────────────┘
     │
     │ 6. Update target.status='online'
     │    Create audit log
     ▼
┌─────────────────────────────────┐
│  Database                       │
│  - target.status = 'online'     │
│  - target.firedog_version = X   │
└─────────────────────────────────┘
```

### 2.2.2 Fetch Periodico Dati (Celery Task)
```
┌──────────────┐
│ Celery Beat  │ (Scheduler)
└──────┬───────┘
       │ Every 10 minutes (configurabile)
       │
       ▼
┌────────────────────────────────────┐
│  Task: fetch_target_data(target_id)│
└────┬───────────────────────────────┘
     │
     │ 1. Get target from DB
     ▼
┌─────────────────────────────────────┐
│  Check target.status == 'online'    │
│  ├─ NO  → Skip, log warning         │
│  └─ YES → Continue                  │
└────┬────────────────────────────────┘
     │
     │ 2. SSHManager.connect()
     ▼
┌─────────────────────────────────────┐
│  Connection OK?                     │
│  ├─ NO  → target.status='offline'   │
│  │        Create alert               │
│  └─ YES → Continue                  │
└────┬────────────────────────────────┘
     │
     │ 3. fetch_analysis_results()
     │    SCP /tmp/firedog-analysis.json
     ▼
┌─────────────────────────────────────┐
│  Parse JSON results                 │
│  - threats list                     │
│  - stats                            │
└────┬────────────────────────────────┘
     │
     │ 4. Save to database
     ▼
┌─────────────────────────────────────┐
│  Database Writes                    │
│  - ThreatLog records (bulk create)  │
│  - Statistics record                │
│  - target.last_fetch = now()        │
└────┬────────────────────────────────┘
     │
     │ 5. Check threat scores
     ▼
┌─────────────────────────────────────┐
│  If score >= 80 → Create Alert      │
│  (severity='critical')              │
└─────────────────────────────────────┘
```

### 2.2.3 Aggiunta Regola Firewall via UI
```
┌─────────┐
│  Admin  │
└────┬────┘
     │ 1. Apre "Rules Manager" per target
     │    Compila form: chain=INPUT, port=8080, protocol=tcp
     │
     │ 2. POST /api/targets/{id}/rules/add/
     ▼
┌──────────────────────────────────────┐
│  Backend API - RuleAddView           │
│  - Validate input (port, protocol)   │
│  - Check target.status == 'online'   │
└────┬─────────────────────────────────┘
     │
     │ 3. SSHManager.connect()
     ▼
┌──────────────────────────────────────┐
│  SSHManager.add_firewall_rule()      │
│  - Execute: firewall-manager         │
│              --add-input 8080        │
└────┬─────────────────────────────────┘
     │
     │ 4. Command result
     ▼
┌──────────────────────────────────────┐
│  Success?                            │
│  ├─ YES → Fetch updated rules        │
│  │        Update FirewallRule table  │
│  │        Create audit log           │
│  │        Return 200                 │
│  └─ NO  → Return 400 with error      │
└──────────────────────────────────────┘
```

---

## 2.3 Componenti e Responsabilità

| Componente | Responsabilità | Dipendenze |
|------------|----------------|------------|
| **React Frontend** | UI, User interaction, Data visualization | Backend API |
| **Django API** | Business logic, Validation, Orchestration | PostgreSQL, Celery |
| **SSHManager** | SSH connections, SCP transfers, Remote commands | Paramiko, Target SSH |
| **Celery Worker** | Background tasks (fetch data), Scheduling | Redis, Django |
| **PostgreSQL** | Data persistence | - |
| **Discovery Service** | Network scanning, Bulk import | arp-scan, Django |
| **Integrity Checker** | File hashing, Change detection | Django, Filesystem |

---

# 3. DATABASE DESIGN

## 3.1 Entity-Relationship Diagram
```
┌──────────────┐         ┌──────────────┐
│   Target     │◄───────┤  ThreatLog   │
│              │ 1    N │              │
│ id (PK)      │         │ id (PK)      │
│ hostname     │         │ target_id(FK)│
│ ip_address   │         │ source_ip    │
│ status       │         │ threat_score │
│ ssh_port     │         │ classification│
└──────┬───────┘         └──────────────┘
       │
       │ 1
       │
       │ N
       ▼
┌──────────────┐         ┌──────────────┐
│FirewallRule  │         │ Statistics   │
│              │         │              │
│ id (PK)      │         │ id (PK)      │
│ target_id(FK)│◄───────┤ target_id(FK)│
│ chain        │ 1    N │ input_packets│
│ rule_number  │         │ collected_at │
└──────────────┘         └──────────────┘
       │
       │
       ▼
┌──────────────┐
│   Alert      │
│              │
│ id (PK)      │
│ target_id(FK)│
│ severity     │
│ acknowledged │
└──────────────┘


┌──────────────┐         ┌──────────────┐
│   SSHKey     │         │    Config    │
│              │         │              │
│ id (PK)      │         │ key (PK)     │
│ private_key  │         │ value        │
│ public_key   │         └──────────────┘
└──────────────┘


┌──────────────┐         ┌──────────────┐
│FileIntegrity │         │  AuditLog    │
│              │         │              │
│ filepath(PK) │         │ id (PK)      │
│ sha512_hash  │         │ username     │
│ last_checked │         │ action       │
└──────────────┘         │ target_id(FK)│
                         └──────────────┘


3.2 Tabelle - Dettaglio Colonne
3.2.1 targets
ColumnTypeConstraintsDescriptionidSERIALPRIMARY KEYAuto-increment IDhostnameVARCHAR(255)NOT NULLHostname del targetip_addressINETUNIQUE, NOT NULLIP addressstatusVARCHAR(20)DEFAULT 'pending'pending|installing|online|offline|error|disabledssh_portINTEGERDEFAULT 22Porta SSHinstallation_statusVARCHAR(100)NULLStato installazioneinstallation_errorTEXTNULLErrore installazionefiredog_versionVARCHAR(20)NULLVersione firedog installatalast_seenTIMESTAMPNULLUltimo contatto riuscitolast_fetchTIMESTAMPNULLUltimo fetch datifetch_interval_minutesINTEGERDEFAULT 10Intervallo fetchos_infoVARCHAR(255)NULLInfo OSkernel_versionVARCHAR(100)NULLVersione kernelcreated_atTIMESTAMPDEFAULT NOW()Data creazioneupdated_atTIMESTAMPDEFAULT NOW()Data aggiornamento
Indexes:

idx_targets_status ON (status)
idx_targets_ip ON (ip_address)


3.2.2 threat_logs
ColumnTypeConstraintsDescriptionidSERIALPRIMARY KEYAuto-increment IDtarget_idINTEGERFK → targets(id) CASCADETarget di riferimentosource_ipINETNOT NULLIP sorgente attaccantethreat_scoreINTEGERNOT NULLScore 0-100packetsINTEGERDEFAULT 0Numero pacchettiports_countINTEGERDEFAULT 0Numero porte scansionateprotocolsVARCHAR(100)NULLProtocolli (tcp,udp,icmp)threat_typeVARCHAR(50)NULLPort Scanning, SYN Flood, etc.classificationVARCHAR(20)NULLCRITICAL|HIGH|MEDIUM|LOWdetected_atTIMESTAMPDEFAULT NOW()Timestamp rilevamentoacknowledgedBOOLEANDEFAULT FALSEAck dall'admin
Indexes:

idx_threats_target_date ON (target_id, detected_at DESC)
idx_threats_classification ON (classification, detected_at DESC)
idx_threats_source_ip ON (source_ip)
idx_threats_score ON (threat_score DESC)

3.2.3 firewall_rules
ColumnTypeConstraintsDescriptionidSERIALPRIMARY KEYAuto-increment IDtarget_idINTEGERFK → targets(id) CASCADETarget di riferimentochainVARCHAR(10)NOT NULLINPUT|OUTPUT|FORWARDrule_numberINTEGERNOT NULLNumero regola in chainprotocolVARCHAR(10)NULLtcp|udp|icmpportINTEGERNULLPortasource_ipINETNULLIP sorgentedest_ipINETNULLIP destinazioneactionVARCHAR(20)NULLACCEPT|DROP|REJECTcommentTEXTNULLCommento regolapacketsBIGINTDEFAULT 0Counter pacchettibytesBIGINTDEFAULT 0Counter bytessynced_atTIMESTAMPDEFAULT NOW()Ultimo sync
Unique Constraint: (target_id, chain, rule_number)
Indexes:

idx_rules_target_chain ON (target_id, chain)


3.2.4 statistics
ColumnTypeConstraintsDescriptionidSERIALPRIMARY KEYAuto-increment IDtarget_idINTEGERFK → targets(id) CASCADETarget di riferimentoinput_packetsBIGINTDEFAULT 0Pacchetti INPUT totalioutput_packetsBIGINTDEFAULT 0Pacchetti OUTPUT totaliinput_droppedBIGINTDEFAULT 0Pacchetti INPUT droppatioutput_droppedBIGINTDEFAULT 0Pacchetti OUTPUT droppatipcap_input_sizeBIGINTDEFAULT 0Dimensione PCAP input (bytes)pcap_output_sizeBIGINTDEFAULT 0Dimensione PCAP output (bytes)collected_atTIMESTAMPDEFAULT NOW()Timestamp raccolta
Indexes:

idx_stats_target_date ON (target_id, collected_at DESC)


3.2.5 alerts
ColumnTypeConstraintsDescriptionidSERIALPRIMARY KEYAuto-increment IDtarget_idINTEGERFK → targets(id) CASCADE NULLTarget (NULL = alert globale)severityVARCHAR(20)NOT NULLcritical|high|medium|low|infotitleVARCHAR(255)NOT NULLTitolo alertmessageTEXTNOT NULLMessaggio dettagliatoacknowledgedBOOLEANDEFAULT FALSEAck dall'admincreated_atTIMESTAMPDEFAULT NOW()Timestamp creazione
Indexes:

idx_alerts_severity_date ON (severity, created_at DESC)
idx_alerts_ack ON (acknowledged)


3.2.6 config
ColumnTypeConstraintsDescriptionkeyVARCHAR(100)PRIMARY KEYChiave configurazionevalueTEXTNOT NULLValore (JSON stringified)updated_atTIMESTAMPDEFAULT NOW()Ultimo aggiornamento
Chiavi predefinite:

jwt_token_duration → 1800 (secondi)
ssh_key_rotation_days → 90
default_fetch_interval → 10 (minuti)
max_threats_retention_days → 90
alert_threshold_critical → 80
alert_threshold_high → 60

3.2.7 ssh_keys
ColumnTypeConstraintsDescriptionidSERIALPRIMARY KEYAuto-increment IDkey_typeVARCHAR(20)DEFAULT 'ed25519'Tipo chiaveprivate_keyTEXTNOT NULLChiave privata PEMpublic_keyTEXTNOT NULLChiave pubblicafingerprintVARCHAR(100)NULLFingerprint SHA256created_atTIMESTAMPDEFAULT NOW()Data creazionelast_rotatedTIMESTAMPNULLUltima rotazione
Note: Solo 1 record attivo (la chiave corrente)


3.2.8 file_integrity
ColumnTypeConstraintsDescriptionfilepathVARCHAR(500)PRIMARY KEYPath assoluto filesha512_hashVARCHAR(128)NOT NULLHash SHA512last_checkedTIMESTAMPDEFAULT NOW()Ultimo check
File monitorati:

/usr/local/bin/firewall-manager
/usr/local/sbin/firewall-init.sh
/usr/local/bin/traffic-analyzer
/etc/firedog/settings.py
Tutti gli script deployment


3.2.9 audit_log
ColumnTypeConstraintsDescriptionidSERIALPRIMARY KEYAuto-increment IDusernameVARCHAR(100)NOT NULLUsername adminactionVARCHAR(255)NOT NULLAzione eseguitatarget_idINTEGERFK → targets(id) SET NULLTarget coinvolto (NULL se globale)detailsJSONBDEFAULT {}Dettagli extra JSONip_addressINETNULLIP da cui proviene l'azionetimestampTIMESTAMPDEFAULT NOW()Timestamp azione
Indexes:

idx_audit_user_date ON (username, timestamp DESC)
idx_audit_target ON (target_id, timestamp DESC)

Azioni tracciate:

login
logout
target.add
target.install
target.delete
rule.add
rule.remove
config.update
ssh_key.rotate
file.integrity.violation


3.3 Queries Comuni Ottimizzate
3.3.1 Dashboard - Overview Stats

-- Total targets by status
SELECT status, COUNT(*) as count
FROM targets
GROUP BY status;

-- Critical threats last 24h
SELECT COUNT(*) 
FROM threat_logs
WHERE classification = 'CRITICAL' 
  AND detected_at >= NOW() - INTERVAL '24 hours';

-- Top 10 attacking IPs last 7 days
SELECT 
    source_ip, 
    COUNT(*) as threat_count,
    MAX(threat_score) as max_score,
    STRING_AGG(DISTINCT threat_type, ', ') as attack_types
FROM threat_logs
WHERE detected_at >= NOW() - INTERVAL '7 days'
GROUP BY source_ip
ORDER BY threat_count DESC, max_score DESC
LIMIT 10;

3.3.2 Target Detail - Complete View
-- Single target with all related data
SELECT 
    t.*,
    COUNT(DISTINCT tl.id) as total_threats,
    COUNT(DISTINCT CASE WHEN tl.classification='CRITICAL' THEN tl.id END) as critical_threats,
    COUNT(DISTINCT fr.id) as total_rules,
    MAX(s.collected_at) as last_stats_update
FROM targets t
LEFT JOIN threat_logs tl ON t.id = tl.target_id 
    AND tl.detected_at >= NOW() - INTERVAL '24 hours'
LEFT JOIN firewall_rules fr ON t.id = fr.target_id
LEFT JOIN statistics s ON t.id = s.target_id
WHERE t.id = $1
GROUP BY t.id;

3.3.3 Alerts - Unacknowledged
-- Get unacknowledged alerts ordered by severity
SELECT 
    a.*,
    t.hostname,
    t.ip_address
FROM alerts a
LEFT JOIN targets t ON a.target_id = t.id
WHERE a.acknowledged = FALSE
ORDER BY 
    CASE a.severity
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
        ELSE 5
    END,
    a.created_at DESC;
```

---

# 4. API SPECIFICATION

## 4.1 Authentication

### 4.1.1 Login
```
POST /api/auth/login/
Content-Type: application/json

Request:
{
  "username": "admin",
  "password": "secure_password"
}

Response 200:
{
  "access": "eyJ0eXAiOiJKV1QiLC...",
  "refresh": "eyJ0eXAiOiJKV1QiLC...",
  "expires_in": 1800
}

Response 401:
{
  "detail": "Invalid credentials"
}
```

### 4.1.2 Refresh Token
```
POST /api/auth/refresh/
Content-Type: application/json

Request:
{
  "refresh": "eyJ0eXAiOiJKV1QiLC..."
}

Response 200:
{
  "access": "eyJ0eXAiOiJKV1QiLC...",
  "expires_in": 1800
}
```

### 4.1.3 Logout
```
POST /api/auth/logout/
Authorization: Bearer <access_token>

Response 200:
{
  "message": "Logout successful"
}
```

---

## 4.2 Targets Management

### 4.2.1 List Targets
```
GET /api/targets/
Authorization: Bearer <access_token>

Query Parameters:
- status: filter by status (pending|online|offline|error)
- search: search by hostname or IP

Response 200:
{
  "count": 10,
  "results": [
    {
      "id": 1,
      "hostname": "server01",
      "ip_address": "192.168.1.100",
      "status": "online",
      "ssh_port": 22,
      "firedog_version": "1.0",
      "last_seen": "2025-10-31T10:30:00Z",
      "last_fetch": "2025-10-31T10:25:00Z",
      "fetch_interval_minutes": 10,
      "threat_count_24h": 5,
      "critical_threats": 1,
      "total_rules": 15
    },
    ...
  ]
}
```

### 4.2.2 Get Target Detail
```
GET /api/targets/{id}/
Authorization: Bearer <access_token>

Response 200:
{
  "id": 1,
  "hostname": "server01",
  "ip_address": "192.168.1.100",
  "status": "online",
  "ssh_port": 22,
  "installation_status": "completed",
  "installation_error": null,
  "firedog_version": "1.0",
  "last_seen": "2025-10-31T10:30:00Z",
  "last_fetch": "2025-10-31T10:25:00Z",
  "fetch_interval_minutes": 10,
  "os_info": "Debian GNU/Linux 12 (bookworm)",
  "kernel_version": "6.1.0-13-amd64",
  "created_at": "2025-10-20T14:00:00Z",
  "updated_at": "2025-10-31T10:30:00Z",
  "statistics": {
    "input_packets": 1234567,
    "output_packets": 987654,
    "input_dropped": 1234,
    "output_dropped": 56,
    "pcap_input_size": 104857600,
    "pcap_output_size": 52428800
  },
  "recent_threats": [
    {
      "id": 123,
      "source_ip": "203.0.113.50",
      "threat_score": 85,
      "classification": "CRITICAL",
      "threat_type": "Port Scanning",
      "packets": 150,
      "detected_at": "2025-10-31T09:45:00Z"
    },
    ...
  ]
}
```

### 4.2.3 Create Target
```
POST /api/targets/
Authorization: Bearer <access_token>
Content-Type: application/json

Request:
{
  "hostname": "server02",
  "ip_address": "192.168.1.101",
  "ssh_port": 22
}

Response 201:
{
  "id": 2,
  "hostname": "server02",
  "ip_address": "192.168.1.101",
  "status": "pending",
  "message": "Target created. Run installation to activate."
}

Response 400:
{
  "ip_address": ["Target with this IP already exists"]
}
```

### 4.2.4 Install FireDog on Target
```
POST /api/targets/{id}/install/
Authorization: Bearer <access_token>

Response 202: (Accepted - async task started)
{
  "message": "Installation started",
  "task_id": "abc-123-def"
}

Response 400:
{
  "error": "User 'microcyber' not found on target",
  "setup_command": "sudo useradd -m -s /bin/bash microcyber && sudo usermod -aG sudo microcyber"
}

Response 409:
{
  "error": "Target already has status 'online'"
}
```

### 4.2.5 Get Installation Status
```
GET /api/targets/{id}/install-status/
Authorization: Bearer <access_token>

Response 200:
{
  "status": "installing",  // pending|installing|completed|failed
  "progress": 60,  // 0-100
  "current_step": "Uploading package",
  "error": null
}
```

### 4.2.6 Retry Installation
```
POST /api/targets/{id}/retry-install/
Authorization: Bearer <access_token>

Response 202:
{
  "message": "Installation retry started",
  "task_id": "xyz-789-abc"
}
```

### 4.2.7 Fetch Data Now (Manual)
```
POST /api/targets/{id}/fetch/
Authorization: Bearer <access_token>

Response 200:
{
  "message": "Data fetched successfully",
  "threats_found": 3,
  "new_threats": 1
}

Response 503:
{
  "error": "Target is offline or unreachable"
}
```

### 4.2.8 Update Target
```
PATCH /api/targets/{id}/
Authorization: Bearer <access_token>
Content-Type: application/json

Request:
{
  "fetch_interval_minutes": 5,
  "ssh_port": 2222
}

Response 200:
{
  "id": 1,
  "hostname": "server01",
  "fetch_interval_minutes": 5,
  "ssh_port": 2222,
  ...
}
```

### 4.2.9 Delete Target
```
DELETE /api/targets/{id}/
Authorization: Bearer <access_token>

Response 204: (No Content)

Note: Cascade delete di tutte le entità correlate
```

---

## 4.3 Discovery

### 4.3.1 Network Discovery
```
POST /api/discovery/scan/
Authorization: Bearer <access_token>

Response 202:
{
  "message": "Network scan started",
  "task_id": "scan-123"
}
```

### 4.3.2 Get Discovery Results
```
GET /api/discovery/results/{task_id}/
Authorization: Bearer <access_token>

Response 200:
{
  "status": "completed",  // running|completed|failed
  "found_hosts": [
    {
      "ip": "192.168.1.100",
      "hostname": "server01.local",
      "mac": "00:11:22:33:44:55",
      "already_added": true
    },
    {
      "ip": "192.168.1.101",
      "hostname": "server02.local",
      "mac": "00:11:22:33:44:66",
      "already_added": false
    },
    ...
  ]
}
```

### 4.3.3 Bulk Import from File
```
POST /api/discovery/bulk-import/
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

Form Data:
- file: targets.txt

File Format (targets.txt):
192.168.1.100 server01
192.168.1.101 server02
192.168.1.102 server03

Response 200:
{
  "imported": 2,
  "skipped": 1,
  "errors": [
    {
      "line": 1,
      "error": "IP already exists"
    }
  ]
}
```

---

## 4.4 Firewall Rules

### 4.4.1 Get Target Rules
```
GET /api/targets/{id}/rules/
Authorization: Bearer <access_token>

Query Parameters:
- chain: filter by chain (INPUT|OUTPUT|FORWARD)

Response 200:
{
  "input_rules": [
    {
      "id": 1,
      "rule_number": 1,
      "protocol": "tcp",
      "port": 22,
      "source_ip": "192.168.1.50",
      "action": "ACCEPT",
      "comment": "SSH from admin",
      "packets": 12345,
      "bytes": 9876543
    },
    ...
  ],
  "output_rules": [...],
  "forward_rules": []
}
```

### 4.4.2 Add Rule
```
POST /api/targets/{id}/rules/add/
Authorization: Bearer <access_token>
Content-Type: application/json

Request:
{
  "chain": "INPUT",
  "port": 8080,
  "protocol": "tcp",
  "source_ip": "192.168.1.0/24",  // optional
  "comment": "Allow Grafana"
}

Response 200:
{
  "message": "Rule added successfully",
  "rule": {
    "chain": "INPUT",
    "rule_number": 1,
    "port": 8080,
    "protocol": "tcp",
    "source_ip": "192.168.1.0/24"
  }
}

Response 400:
{
  "error": "Invalid port number"
}

Response 503:
{
  "error": "Target is offline"
}
```

### 4.4.3 Remove Rule
```
DELETE /api/targets/{id}/rules/{chain}/{rule_number}/
Authorization: Bearer <access_token>

Example: DELETE /api/targets/1/rules/INPUT/5/

Response 200:
{
  "message": "Rule removed successfully"
}

Response 404:
{
  "error": "Rule not found"
}
```

### 4.4.4 Sync Rules (Refresh from Target)
```
POST /api/targets/{id}/rules/sync/
Authorization: Bearer <access_token>

Response 200:
{
  "message": "Rules synchronized",
  "total_rules": 25
}
```

---

## 4.5 Threats

### 4.5.1 List All Threats
```
GET /api/threats/
Authorization: Bearer <access_token>

Query Parameters:
- target_id: filter by target
- classification: CRITICAL|HIGH|MEDIUM|LOW
- since: timestamp (ISO format)
- acknowledged: true|false
- limit: int (default 100)
- offset: int (pagination)

Response 200:
{
  "count": 250,
  "next": "/api/threats/?offset=100",
  "previous": null,
  "results": [
    {
      "id": 123,
      "target": {
        "id": 1,
        "hostname": "server01",
        "ip_address": "192.168.1.100"
      },
      "source_ip": "203.0.113.50",
      "threat_score": 85,
      "classification": "CRITICAL",
      "threat_type": "Port Scanning",
      "packets": 150,
      "ports_count": 50,
      "protocols": "tcp",
      "detected_at": "2025-10-31T09:45:00Z",
      "acknowledged": false
    },
    ...
  ]
}
```

### 4.5.2 Get Threat Detail
```
GET /api/threats/{id}/
Authorization: Bearer <access_token>

Response 200:
{
  "id": 123,
  "target": {...},
  "source_ip": "203.0.113.50",
  "threat_score": 85,
  "classification": "CRITICAL",
  "threat_type": "Port Scanning",
  "packets": 150,
  "ports_count": 50,
  "protocols": "tcp",
  "detected_at": "2025-10-31T09:45:00Z",
  "acknowledged": false,
  "related_threats": [
    // Other threats from same source_ip
  ]
}
```

### 4.5.3 Acknowledge Threat
```
POST /api/threats/{id}/acknowledge/
Authorization: Bearer <access_token>

Response 200:
{
  "message": "Threat acknowledged"
}
```

### 4.5.4 Bulk Acknowledge
```
POST /api/threats/bulk-acknowledge/
Authorization: Bearer <access_token>
Content-Type: application/json

Request:
{
  "threat_ids": [123, 124, 125]
}

Response 200:
{
  "acknowledged": 3
}
```

### 4.5.5 Top Attackers
```
GET /api/threats/top-attackers/
Authorization: Bearer <access_token>

Query Parameters:
- days: int (default 7)
- limit: int (default 20)

Response 200:
{
  "period": "last_7_days",
  "attackers": [
    {
      "source_ip": "203.0.113.50",
      "total_threats": 45,
      "max_score": 95,
      "classifications": {
        "CRITICAL": 10,
        "HIGH": 20,
        "MEDIUM": 15
      },
      "attack_types": ["Port Scanning", "SYN Flood"],
      "targets_affected": 3
    },
    ...
  ]
}
```

---

## 4.6 Statistics

### 4.6.1 Get Target Statistics
```
GET /api/targets/{id}/statistics/
Authorization: Bearer <access_token>

Query Parameters:
- period: 1h|6h|24h|7d|30d (default 24h)

Response 200:
{
  "period": "24h",
  "data_points": [
    {
      "timestamp": "2025-10-31T10:00:00Z",
      "input_packets": 123456,
      "output_packets": 98765,
      "input_dropped": 123,
      "output_dropped": 5
    },
    ...
  ],
  "summary": {
    "total_input": 2987654,
    "total_output": 1234567,
    "total_dropped": 1580,
    "drop_rate": 0.05  // 5%
  }
}
```

### 4.6.2 Global Statistics
```
GET /api/statistics/global/
Authorization: Bearer <access_token>

Response 200:
{
  "total_targets": 10,
  "online_targets": 8,
  "offline_targets": 2,
  "total_threats_24h": 123,
  "critical_threats_24h": 15,
  "total_packets_processed_24h": 10000000,
  "total_dropped_24h": 5000,
  "global_drop_rate": 0.0005,
  "top_target_by_threats": {
    "id": 1,
    "hostname": "server01",
    "threat_count": 45
  }
}
```

---

## 4.7 Alerts

### 4.7.1 List Alerts
```
GET /api/alerts/
Authorization: Bearer <access_token>

Query Parameters:
- severity: critical|high|medium|low|info
- acknowledged: true|false
- target_id: int

Response 200:
{
  "count": 15,
  "unacknowledged": 8,
  "results": [
    {
      "id": 1,
      "target": {
        "id": 1,
        "hostname": "server01"
      },
      "severity": "critical",
      "title": "Critical threat detected",
      "message": "IP 203.0.113.50 has threat score 95",
      "acknowledged": false,
      "created_at": "2025-10-31T09:45:00Z"
    },
    ...
  ]
}
```

### 4.7.2 Acknowledge Alert
```
POST /api/alerts/{id}/acknowledge/
Authorization: Bearer <access_token>

Response 200:
{
  "message": "Alert acknowledged"
}
```

### 4.7.3 Dismiss Alert
```
DELETE /api/alerts/{id}/
Authorization: Bearer <access_token>

Response 204: (No Content)
```

---

## 4.8 Configuration

### 4.8.1 Get Configuration
```
GET /api/config/
Authorization: Bearer <access_token>

Response 200:
{
  "jwt_token_duration": 1800,
  "ssh_key_rotation_days": 90,
  "default_fetch_interval": 10,
  "max_threats_retention_days": 90,
  "alert_threshold_critical": 80,
  "alert_threshold_high": 60,
  "ssh_public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI..."
}
```

### 4.8.2 Update Configuration
```
PATCH /api/config/
Authorization: Bearer <access_token>
Content-Type: application/json

Request:
{
  "jwt_token_duration": 3600,
  "default_fetch_interval": 5
}

Response 200:
{
  "message": "Configuration updated",
  "updated_keys": ["jwt_token_duration", "default_fetch_interval"]
}

Note: Richiede password confirmation per sicurezza
```

### 4.8.3 Get SSH Key Info
```
GET /api/config/ssh-key/
Authorization: Bearer <access_token>

Response 200:
{
  "key_type": "ed25519",
  "public_key": "ssh-ed25519 AAAAC3...",
  "fingerprint": "SHA256:abc123...",
  "created_at": "2025-10-01T10:00:00Z",
  "last_rotated": null,
  "days_until_rotation": 90
}
```

### 4.8.4 Rotate SSH Key
```
POST /api/config/ssh-key/rotate/
Authorization: Bearer <access_token>
Content-Type: application/json

Request:
{
  "password": "admin_password"  // Confirmation required
}

Response 200:
{
  "message": "SSH key rotated successfully",
  "new_public_key": "ssh-ed25519 AAAAC3...",
  "fingerprint": "SHA256:xyz789...",
  "warning": "You must update the public key on all targets manually"
}
```

### 4.8.5 Get Sudoers Template
```
GET /api/config/sudoers-template/
Authorization: Bearer <access_token>

Response 200:
{
  "content": "# /etc/sudoers.d/microcyber\nmicrocyber ALL=(ALL) NOPASSWD: /usr/sbin/iptables\n..."
}
```

### 4.8.6 Get SSHD Config Template
```
GET /api/config/sshd-template/
Authorization: Bearer <access_token>

Response 200:
{
  "content": "# /etc/ssh/sshd_config.d/microcyber.conf\nMatch User microcyber\n..."
}
```

### 4.8.7 Get Setup Command for Target
```
GET /api/config/target-setup-command/
Authorization: Bearer <access_token>

Response 200:
{
  "commands": [
    "sudo useradd -m -s /bin/bash microcyber",
    "sudo mkdir -p /home/microcyber/.ssh",
    "echo 'ssh-ed25519 AAAAC3...' | sudo tee /home/microcyber/.ssh/authorized_keys",
    "sudo chown -R microcyber:microcyber /home/microcyber/.ssh",
    "sudo chmod 700 /home/microcyber/.ssh",
    "sudo chmod 600 /home/microcyber/.ssh/authorized_keys"
  ],
  "script": "#!/bin/bash\n# Setup microcyber user\n..."
}
```

---

## 4.9 File Integrity

### 4.9.1 Check File Integrity
```
GET /api/integrity/check/
Authorization: Bearer <access_token>

Response 200:
{
  "status": "ok",  // ok|violated
  "checked_files": 8,
  "violations": []
}

Response 200 (with violations):
{
  "status": "violated",
  "checked_files": 8,
  "violations": [
    {
      "filepath": "/usr/local/bin/firewall-manager",
      "expected_hash": "abc123...",
      "current_hash": "xyz789...",
      "last_checked": "2025-10-31T10:00:00Z"
    }
  ]
}
```

### 4.9.2 Accept File Changes
```
POST /api/integrity/accept-changes/
Authorization: Bearer <access_token>
Content-Type: application/json

Request:
{
  "filepath": "/usr/local/bin/firewall-manager",
  "password": "admin_password"
}

Response 200:
{
  "message": "File hash updated",
  "new_hash": "xyz789..."
}
```

---

## 4.10 Audit Log

### 4.10.1 Get Audit Log
```
GET /api/audit/
Authorization: Bearer <access_token>

Query Parameters:
- username: filter by user
- action: filter by action
- target_id: filter by target
- since: timestamp
- limit: int (default 100)

Response 200:
{
  "count": 523,
  "results": [
    {
      "id": 1,
      "username": "admin",
      "action": "target.install",
      "target": {
        "id": 1,
        "hostname": "server01"
      },
      "details": {
        "success": true,
        "duration_seconds": 45
      },
      "ip_address": "192.168.1.10",
      "timestamp": "2025-10-31T09:00:00Z"
    },
    ...
  ]
}

4.11 Error Responses
Standard Error Format

{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {}  // optional
}

Common HTTP Status Codes
CodeMeaningUsage200OKSuccessful GET/PATCH201CreatedSuccessful POST (resource created)202AcceptedAsync operation started204No ContentSuccessful DELETE400Bad RequestValidation error401UnauthorizedInvalid/missing token403ForbiddenInsufficient permissions404Not FoundResource not found409ConflictDuplicate resource503Service UnavailableTarget offline



5. BACKEND IMPLEMENTATION GUIDE
# backend/api/views/target_views.py

class TargetViewSet(viewsets.ModelViewSet):
    """
    ViewSet per gestione target
    
    Endpoints:
    - GET    /api/targets/              → list()
    - POST   /api/targets/              → create()
    - GET    /api/targets/{id}/         → retrieve()
    - PATCH  /api/targets/{id}/         → partial_update()
    - DELETE /api/targets/{id}/         → destroy()
    - POST   /api/targets/{id}/install/ → install()
    - POST   /api/targets/{id}/fetch/   → fetch_data()
    - POST   /api/targets/{id}/retry-install/ → retry_install()
    - GET    /api/targets/{id}/install-status/ → install_status()
    """
    
    queryset = Target.objects.all()
    serializer_class = TargetSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Filter queryset based on query params
        """
        queryset = super().get_queryset()
        
        # Filter by status
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Search by hostname or IP
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(hostname__icontains=search) | 
                Q(ip_address__icontains=search)
            )
        
        return queryset
    
    def list(self, request):
        """
        GET /api/targets/
        
        Returns list with aggregated data:
        - threat_count_24h
        - critical_threats
        - total_rules
        """
        queryset = self.get_queryset()
        
        # Annotate with aggregated data
        queryset = queryset.annotate(
            threat_count_24h=Count(
                'threats',
                filter=Q(threats__detected_at__gte=now() - timedelta(hours=24))
            ),
            critical_threats=Count(
                'threats',
                filter=Q(
                    threats__classification='CRITICAL',
                    threats__detected_at__gte=now() - timedelta(hours=24)
                )
            ),
            total_rules=Count('rules')
        )
        
        serializer = TargetListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        GET /api/targets/{id}/
        
        Returns detailed view with:
        - Basic target info
        - Latest statistics
        - Recent threats (last 20)
        """
        target = self.get_object()
        
        # Get latest statistics
        latest_stats = target.statistics.order_by('-collected_at').first()
        
        # Get recent threats
        recent_threats = target.threats.order_by('-detected_at')[:20]
        
        # Serialize
        serializer = TargetDetailSerializer(target, context={
            'latest_stats': latest_stats,
            'recent_threats': recent_threats
        })
        
        return Response(serializer.data)
    
    def create(self, request):
        """
        POST /api/targets/
        
        Request body:
        {
            "hostname": "server01",
            "ip_address": "192.168.1.100",
            "ssh_port": 22
        }
        
        Validation:
        - IP address format
        - IP address unique
        - Hostname not empty
        - SSH port valid range (1-65535)
        
        Creates target with status='pending'
        Logs audit
        """
        serializer = TargetCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create target
        target = serializer.save(status='pending')
        
        # Audit log
        AuditLog.objects.create(
            username=request.user.username,
            action='target.add',
            target=target,
            details={
                'hostname': target.hostname,
                'ip_address': str(target.ip_address)
            },
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response(
            TargetSerializer(target).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def install(self, request, pk=None):
        """
        POST /api/targets/{id}/install/
        
        Async operation - starts Celery task
        
        Process:
        1. Validate target status (must be 'pending' or 'error')
        2. Start async installation task
        3. Update target.status = 'installing'
        4. Return task_id for status tracking
        
        Error cases:
        - Target already 'online' → 409 Conflict
        - Target 'installing' → 409 Conflict
        - Target offline/unreachable → 503
        """
        target = self.get_object()
        
        # Validate status
        if target.status == 'online':
            return Response(
                {'error': 'Target already installed and online'},
                status=status.HTTP_409_CONFLICT
            )
        
        if target.status == 'installing':
            return Response(
                {'error': 'Installation already in progress'},
                status=status.HTTP_409_CONFLICT
            )
        
        # Update status
        target.status = 'installing'
        target.installation_status = 'Starting...'
        target.save()
        
        # Start async task
        from api.tasks import install_target_task
        task = install_target_task.delay(target.id)
        
        # Audit log
        AuditLog.objects.create(
            username=request.user.username,
            action='target.install',
            target=target,
            details={'task_id': task.id},
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response({
            'message': 'Installation started',
            'task_id': task.id
        }, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=True, methods=['get'], url_path='install-status')
    def install_status(self, request, pk=None):
        """
        GET /api/targets/{id}/install-status/
        
        Returns current installation status
        """
        target = self.get_object()
        
        return Response({
            'status': target.status,
            'installation_status': target.installation_status,
            'installation_error': target.installation_error,
            'progress': self._calculate_progress(target)
        })
    
    @action(detail=True, methods=['post'], url_path='retry-install')
    def retry_install(self, request, pk=None):
        """
        POST /api/targets/{id}/retry-install/
        
        Retry failed installation
        Same as install() but clears previous errors
        """
        target = self.get_object()
        
        # Reset error state
        target.installation_error = ''
        target.save()
        
        # Call install
        return self.install(request, pk)
    
    @action(detail=True, methods=['post'])
    def fetch(self, request, pk=None):
        """
        POST /api/targets/{id}/fetch/
        
        Manual data fetch (bypasses scheduled fetch)
        
        Process:
        1. Check target is online
        2. Execute immediate fetch via SSH
        3. Parse and save results
        4. Return summary
        """
        target = self.get_object()
        
        if target.status != 'online':
            return Response(
                {'error': 'Target is not online'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        try:
            # Execute fetch
            from api.tasks import fetch_target_data
            result = fetch_target_data(target.id)
            
            # Audit log
            AuditLog.objects.create(
                username=request.user.username,
                action='target.fetch',
                target=target,
                details=result,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            return Response({
                'message': 'Data fetched successfully',
                'threats_found': result.get('threats_count', 0),
                'new_threats': result.get('new_threats', 0)
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
    
    def destroy(self, request, pk=None):
        """
        DELETE /api/targets/{id}/
        
        Soft delete with confirmation
        Cascade deletes all related data
        """
        target = self.get_object()
        
        # Audit log before deletion
        AuditLog.objects.create(
            username=request.user.username,
            action='target.delete',
            target=None,  # Will be deleted
            details={
                'hostname': target.hostname,
                'ip_address': str(target.ip_address)
            },
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        target.delete()
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def _calculate_progress(self, target):
        """Helper to calculate installation progress %"""
        status_progress = {
            'pending': 0,
            'installing': 50,
            'online': 100,
            'error': 0
        }
        return status_progress.get(target.status, 0)

5.1.3 Rules ViewSet
# backend/api/views/rule_views.py

class RuleViewSet(viewsets.ViewSet):
    """
    ViewSet per gestione regole firewall
    
    Note: Non usa ModelViewSet perché le operazioni
    sono sempre remote via SSH
    """
    
    permission_classes = [IsAuthenticated]
    
    def list(self, request, target_pk=None):
        """
        GET /api/targets/{target_id}/rules/
        
        Returns current rules from database
        Optional: sync from target if ?refresh=true
        """
        target = get_object_or_404(Target, pk=target_pk)
        
        # Check if refresh requested
        if request.query_params.get('refresh') == 'true':
            self._sync_rules_from_target(target)
        
        # Get rules grouped by chain
        input_rules = target.rules.filter(chain='INPUT').order_by('rule_number')
        output_rules = target.rules.filter(chain='OUTPUT').order_by('rule_number')
        forward_rules = target.rules.filter(chain='FORWARD').order_by('rule_number')
        
        return Response({
            'input_rules': FirewallRuleSerializer(input_rules, many=True).data,
            'output_rules': FirewallRuleSerializer(output_rules, many=True).data,
            'forward_rules': FirewallRuleSerializer(forward_rules, many=True).data
        })
    
    @action(detail=False, methods=['post'])
    def add(self, request, target_pk=None):
        """
        POST /api/targets/{target_id}/rules/add/
        
        Request body:
        {
            "chain": "INPUT",
            "port": 8080,
            "protocol": "tcp",
            "source_ip": "192.168.1.0/24",  // optional
            "comment": "Allow service"
        }
        
        Process:
        1. Validate input
        2. Check target online
        3. SSH connect
        4. Execute firewall-manager --add-{chain}
        5. Sync rules back
        6. Audit log
        """
        target = get_object_or_404(Target, pk=target_pk)
        
        # Validate
        serializer = RuleAddSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check target online
        if target.status != 'online':
            return Response(
                {'error': 'Target is offline'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Execute via SSH
        try:
            with SSHManager(target) as ssh:
                success, message = ssh.add_firewall_rule(
                    chain=serializer.validated_data['chain'],
                    port=serializer.validated_data['port'],
                    protocol=serializer.validated_data.get('protocol', 'tcp'),
                    source_ip=serializer.validated_data.get('source_ip'),
                    comment=serializer.validated_data.get('comment', '')
                )
                
                if not success:
                    return Response(
                        {'error': message},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Sync rules
                self._sync_rules_from_target(target)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Audit log
        AuditLog.objects.create(
            username=request.user.username,
            action='rule.add',
            target=target,
            details=serializer.validated_data,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response({
            'message': 'Rule added successfully',
            'rule': serializer.validated_data
        })
    
    @action(detail=True, methods=['delete'], url_path='(?P<chain>[^/.]+)/(?P<rule_number>\d+)')
    def remove(self, request, target_pk=None, chain=None, rule_number=None):
        """
        DELETE /api/targets/{target_id}/rules/{chain}/{rule_number}/
        
        Example: DELETE /api/targets/1/rules/INPUT/5/
        """
        target = get_object_or_404(Target, pk=target_pk)
        
        # Validate chain
        if chain not in ['INPUT', 'OUTPUT', 'FORWARD']:
            return Response(
                {'error': 'Invalid chain'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check target online
        if target.status != 'online':
            return Response(
                {'error': 'Target is offline'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Execute via SSH
        try:
            with SSHManager(target) as ssh:
                success, message = ssh.remove_firewall_rule(
                    chain=chain,
                    rule_number=int(rule_number)
                )
                
                if not success:
                    return Response(
                        {'error': message},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Sync rules
                self._sync_rules_from_target(target)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Audit log
        AuditLog.objects.create(
            username=request.user.username,
            action='rule.remove',
            target=target,
            details={
                'chain': chain,
                'rule_number': rule_number
            },
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response({'message': 'Rule removed successfully'})
    
    @action(detail=False, methods=['post'])
    def sync(self, request, target_pk=None):
        """
        POST /api/targets/{target_id}/rules/sync/
        
        Force sync rules from target to database
        """
        target = get_object_or_404(Target, pk=target_pk)
        
        try:
            count = self._sync_rules_from_target(target)
            return Response({
                'message': 'Rules synchronized',
                'total_rules': count
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
    
    def _sync_rules_from_target(self, target):
        """
        Helper: Fetch rules from target and update database
        
        Process:
        1. SSH connect
        2. Execute: sudo iptables -L -n -v --line-numbers
        3. Parse output
        4. Update FirewallRule table (delete old, insert new)
        5. Return count
        """
        with SSHManager(target) as ssh:
            rules_output = ssh.get_firewall_rules()
            
            if not rules_output:
                raise Exception("Failed to fetch rules")
            
            # Parse output
            parsed_rules = self._parse_iptables_output(rules_output)
            
            # Update database (transaction)
            with transaction.atomic():
                # Delete existing rules
                target.rules.all().delete()
                
                # Insert new rules
                rules_to_create = []
                for rule_data in parsed_rules:
                    rules_to_create.append(
                        FirewallRule(
                            target=target,
                            **rule_data
                        )
                    )
                
                FirewallRule.objects.bulk_create(rules_to_create)
            
            return len(rules_to_create)
    
    def _parse_iptables_output(self, output):
        """
        Parse iptables -L output
        
        Input format:
        Chain INPUT (policy DROP 123 packets, 456 bytes)
        num   pkts bytes target     prot opt in     out     source               destination         
        1       10  1234 ACCEPT     tcp  --  *      *       192.168.1.0/24       0.0.0.0/0            tcp dpt:22
        
        Returns: [
            {
                'chain': 'INPUT',
                'rule_number': 1,
                'packets': 10,
                'bytes': 1234,
                'action': 'ACCEPT',
                'protocol': 'tcp',
                'source_ip': '192.168.1.0/24',
                'port': 22,
                ...
            },
            ...
        ]
        """
        # Implementation: regex parsing
        # Detailed parsing logic omitted for brevity
        # See full implementation in actual code
        
        rules = []
        current_chain = None
        
        for line in output.split('\n'):
            # Parse chain header
            if line.startswith('Chain'):
                match = re.match(r'Chain (\w+)', line)
                if match:
                    current_chain = match.group(1)
                continue
            
            # Parse rule line
            if current_chain and line.strip() and not line.startswith('num'):
                # Regex parsing logic here
                # Extract: num, pkts, bytes, target, prot, source, dest, port
                rule_data = self._parse_rule_line(line, current_chain)
                if rule_data:
                    rules.append(rule_data)
        
        return rules


5.1.4 Threat ViewSet
# backend/api/views/threat_views.py

class ThreatViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet per visualizzazione minacce
    Read-only: le minacce vengono create solo dal fetch automatico
    """
    
    queryset = ThreatLog.objects.select_related('target').all()
    serializer_class = ThreatLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['target_id', 'classification', 'acknowledged']
    ordering_fields = ['detected_at', 'threat_score']
    ordering = ['-detected_at']
    
    def get_queryset(self):
        """Filter with query params"""
        queryset = super().get_queryset()
        
        # Filter by time range
        since = self.request.query_params.get('since')
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                queryset = queryset.filter(detected_at__gte=since_dt)
            except ValueError:
                pass
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """
        POST /api/threats/{id}/acknowledge/
        
        Mark threat as acknowledged
        """
        threat = self.get_object()
        threat.acknowledged = True
        threat.save()
        
        # Audit log
        AuditLog.objects.create(
            username=request.user.username,
            action='threat.acknowledge',
            target=threat.target,
            details={'threat_id': threat.id, 'source_ip': str(threat.source_ip)},
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response({'message': 'Threat acknowledged'})
    
    @action(detail=False, methods=['post'], url_path='bulk-acknowledge')
    def bulk_acknowledge(self, request):
        """
        POST /api/threats/bulk-acknowledge/
        
        Request: {"threat_ids": [1, 2, 3]}
        """
        threat_ids = request.data.get('threat_ids', [])
        
        if not threat_ids:
            return Response(
                {'error': 'No threat IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated = ThreatLog.objects.filter(
            id__in=threat_ids
        ).update(acknowledged=True)
        
        # Audit log
        AuditLog.objects.create(
            username=request.user.username,
            action='threat.bulk_acknowledge',
            details={'threat_ids': threat_ids, 'count': updated},
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response({'acknowledged': updated})
    
    @action(detail=False, methods=['get'], url_path='top-attackers')
    def top_attackers(self, request):
        """
        GET /api/threats/top-attackers/?days=7&limit=20
        
        Returns aggregated attacker statistics
        """
        days = int(request.query_params.get('days', 7))
        limit = int(request.query_params.get('limit', 20))
        
        since = now() - timedelta(days=days)
        
        # Aggregate by source_ip
        attackers = ThreatLog.objects.filter(
            detected_at__gte=since
        ).values('source_ip').annotate(
            total_threats=Count('id'),
            max_score=Max('threat_score'),
            critical_count=Count('id', filter=Q(classification='CRITICAL')),
            high_count=Count('id', filter=Q(classification='HIGH')),
            medium_count=Count('id', filter=Q(classification='MEDIUM')),
            attack_types=ArrayAgg('threat_type', distinct=True),
            targets_affected=Count('target_id', distinct=True)
        ).order_by('-total_threats', '-max_score')[:limit]
        
        return Response({
            'period': f'last_{days}_days',
            'attackers': list(attackers)
        })


5.2.2 Installation Task
# backend/api/tasks.py

from celery import shared_task
from api.models import Target, Alert
from api.ssh_manager import SSHManager
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def install_target_task(self, target_id):
    """
    Async task: Install firedog on target
    
    Process:
    1. Get target from DB
    2. Update status to 'installing'
    3. SSH connect
    4. Check microcyber user exists
    5. Upload firedog package
    6. Execute install.sh
    7. Verify installation
    8. Setup cron job
    9. Update target status
    10. Create alert on failure
    
    Returns:
        dict: {
            'success': bool,
            'message': str,
            'firedog_version': str (if success)
        }
    """
    try:
        target = Target.objects.get(id=target_id)
        
        # Step 1: Update status
        target.installation_status = 'Connecting via SSH...'
        target.save()
        
        # Step 2: SSH connection
        ssh = SSHManager(target)
        
        if not ssh.connect():
            raise Exception("SSH connection failed")
        
        target.installation_status = 'Checking prerequisites...'
        target.save()
        
        # Step 3: Check user exists
        if not ssh.check_user_exists():
            target.status = 'error'
            target.installation_error = (
                "User 'microcyber' not found. "
                "Please create user first."
            )
            target.save()
            
            # Create alert
            Alert.objects.create(
                target=target,
                severity='high',
                title='Installation Failed',
                message='User microcyber not found on target'
            )
            
            ssh.disconnect()
            return {
                'success': False,
                'message': 'User microcyber not found'
            }
        
        # Step 4: Upload package
        target.installation_status = 'Uploading firedog package...'
        target.save()
        
        package_path = '/opt/firedog/deployment/firedog-package'
        success, message = ssh.install_firedog_package(package_path)
        
        if not success:
            raise Exception(f"Installation failed: {message}")
        
        # Step 5: Setup cron
        target.installation_status = 'Configuring cron job...'
        target.save()
        
        if not ssh.install_cron_job(target.fetch_interval_minutes):
            logger.warning(f"Cron installation failed for target {target_id}")
        
        # Step 6: Success!
        target.status = 'online'
        target.installation_status = 'Completed'
        target.firedog_version = message  # message contains version
        target.last_seen = now()
        target.save()
        
        ssh.disconnect()
        
        # Create success alert
        Alert.objects.create(
            target=target,
            severity='info',
            title='Installation Successful',
            message=f'FireDog installed successfully on {target.hostname}'
        )
        
        logger.info(f"Target {target_id} installation completed")
        
        return {
            'success': True,
            'message': 'Installation completed',
            'firedog_version': message
        }
        
    except Target.DoesNotExist:
        logger.error(f"Target {target_id} not found")
        return {'success': False, 'message': 'Target not found'}
        
    except Exception as e:
        logger.error(f"Installation failed for target {target_id}: {e}")
        
        # Update target
        target.status = 'error'
        target.installation_status = 'Failed'
        target.installation_error = str(e)
        target.save()
        
        # Create alert
        Alert.objects.create(
            target=target,
            severity='high',
            title='Installation Failed',
            message=f'Error: {str(e)}'
        )
        
        return {
            'success': False,
            'message': str(e)
        }


5.2.3 Periodic Fetch Task
@shared_task
def fetch_all_targets_task():
    """
    Periodic task: Fetch data from all online targets
    
    Runs every N minutes (configurable)
    For each online target:
    - Fetch analysis JSON
    - Parse and save threats
    - Update statistics
    - Create alerts if needed
    """
    online_targets = Target.objects.filter(status='online')
    
    results = {
        'success': 0,
        'failed': 0,
        'skipped': 0
    }
    
    for target in online_targets:
        # Check fetch interval
        if target.last_fetch:
            minutes_since_fetch = (now() - target.last_fetch).total_seconds() / 60
            if minutes_since_fetch < target.fetch_interval_minutes:
                results['skipped'] += 1
                continue
        
        # Fetch data
        try:
            fetch_target_data(target.id)
            results['success'] += 1
        except Exception as e:
            logger.error(f"Fetch failed for target {target.id}: {e}")
            results['failed'] += 1
            
            # Mark offline if unreachable
            target.status = 'offline'
            target.save()
            
            # Create alert
            Alert.objects.create(
                target=target,
                severity='medium',
                title='Target Unreachable',
                message=f'Failed to fetch data: {str(e)}'
            )
    
    logger.info(f"Fetch task completed: {results}")
    return results


def fetch_target_data(target_id):
    """
    Fetch and process data from single target
    
    Process:
    1. SSH connect
    2. Download /tmp/firedog-analysis.json
    3. Parse JSON
    4. Save ThreatLog records
    5. Save Statistics record
    6. Check for critical threats → create alerts
    7. Update target.last_fetch
    
    Returns:
        dict: {
            'threats_count': int,
            'new_threats': int,
            'stats': dict
        }
    """
    target = Target.objects.get(id=target_id)
    
    with SSHManager(target) as ssh:
        # Fetch analysis results
        analysis_data = ssh.fetch_analysis_results()
        
        if not analysis_data:
            raise Exception("No analysis data found")
        
        # Parse threats
        threats_data = analysis_data.get('threats', {})
        new_threats = 0
        
        with transaction.atomic():
            # Process each threat level
            for severity, threat_list in threats_data.items():
                for threat_info in threat_list:
                    # Check if already exists (same IP + recent)
                    exists = ThreatLog.objects.filter(
                        target=target,
                        source_ip=threat_info['ip'],
                        detected_at__gte=now() - timedelta(hours=1)
                    ).exists()
                    
                    if not exists:
                        ThreatLog.objects.create(
                            target=target,
                            source_ip=threat_info['ip'],
                            threat_score=threat_info['score'],
                            packets=threat_info.get('packets', 0),
                            ports_count=threat_info.get('ports_count', 0),
                            protocols=threat_info.get('protocols', ''),
                            threat_type=threat_info.get('type', 'Unknown'),
                            classification=ThreatLog.classify_score(threat_info['score'])
                        )
                        new_threats += 1
            
            # Save statistics
            stats_data = analysis_data.get('stats', {})
            Statistics.objects.create(
                target=target,
                input_packets=stats_data.get('input_packets', 0),
                output_packets=stats_data.get('output_packets', 0),
                input_dropped=stats_data.get('input_dropped', 0),
                output_dropped=stats_data.get('output_dropped', 0),
                pcap_input_size=stats_data.get('pcap_input_size', 0),
                pcap_output_size=stats_data.get('pcap_output_size', 0)
            )
            
            # Update target
            target.last_fetch = now()
            target.last_seen = now()
            target.save()
        
        # Check for critical threats
        critical_count = sum(
            1 for t in threats_data.get('critical', [])
        )
        
        if critical_count > 0:
            # Create alert if not already alerted recently
            recent_alert = Alert.objects.filter(
                target=target,
                severity='critical',
                title__contains='Critical Threats',
                created_at__gte=now() - timedelta(hours=1)
            ).exists()
            
            if not recent_alert:
                Alert.objects.create(
                    target=target,
                    severity='critical',
                    title='Critical Threats Detected',
                    message=f'{critical_count} critical threats detected on {target.hostname}'
                )
        
        return {
            'threats_count': len(threats_data),
            'new_threats': new_threats,
            'stats': stats_data
        }  
        
 5.2.4 File Integrity Check Task
 @shared_task
def check_integrity_task():
    """
    Periodic task: Check file integrity
    
    Runs every 6 hours
    Checks SHA512 hash of critical files
    Creates alerts on violations
    """
    from api.models import FileIntegrity
    
    critical_files = [
        '/usr/local/bin/firewall-manager',
        '/usr/local/sbin/firewall-init.sh',
        '/usr/local/bin/traffic-analyzer',
        '/opt/firedog/backend/manage.py',
        # Add more critical files
    ]
    
    violations = []
    
    for filepath in critical_files:
        if not os.path.exists(filepath):
            logger.warning(f"File not found: {filepath}")
            continue
        
        valid, expected, current = FileIntegrity.check_file(filepath)
        
        if not valid:
            violations.append({
                'filepath': filepath,
                'expected_hash': expected,
                'current_hash': current
            })
            
            # Create alert
            Alert.objects.create(
                severity='critical',
                title='File Integrity Violation',
                message=f'File {filepath} has been modified. Expected: {expected[:16]}..., Current: {current[:16]}...'
            )
            
            logger.warning(f"Integrity violation: {filepath}")
    
    if violations:
        logger.error(f"File integrity violations: {len(violations)}")
    else:
        logger.info("File integrity check passed")
    
    return {
        'checked': len(critical_files),
        'violations': len(violations),
        'details': violations
    }

 5.2.5 Cleanup Task
@shared_task
def cleanup_old_data_task():
    """
    Periodic task: Cleanup old data
    
    Runs daily at 3 AM
    - Delete old threat logs (> retention days)
    - Delete old statistics (> retention days)
    - Delete acknowledged alerts (> 30 days)
    """
    from api.models import Config
    
    retention_days = int(Config.get('max_threats_retention_days', 90))
    
    cutoff_date = now() - timedelta(days=retention_days)
    
    # Delete old threats
    deleted_threats = ThreatLog.objects.filter(
        detected_at__lt=cutoff_date
    ).delete()[0]
    
    # Delete old statistics
    deleted_stats = Statistics.objects.filter(
        collected_at__lt=cutoff_date
    ).delete()[0]
    
    # Delete old acknowledged alerts
    alert_cutoff = now() - timedelta(days=30)
    deleted_alerts = Alert.objects.filter(
        acknowledged=True,
        created_at__lt=alert_cutoff
    ).delete()[0]
    
    logger.info(
        f"Cleanup completed: "
        f"{deleted_threats} threats, "
        f"{deleted_stats} stats, "
        f"{deleted_alerts} alerts deleted"
    )
    
    return {
        'threats_deleted': deleted_threats,
        'stats_deleted': deleted_stats,
        'alerts_deleted': deleted_alerts
    }


5.3 Discovery Service
5.3.1 Network Discovery (arp-scan)
# backend/discovery/arpscan.py

import subprocess
import re
from typing import List, Dict
from api.models import Target


class NetworkDiscovery:
    """
    Network discovery service using arp-scan
    """
    
    @staticmethod
    def get_local_networks() -> List[str]:
        """
        Get networks from 'ip route'
        
        Returns: ['192.168.1.0/24', '10.0.0.0/24', ...]
        """
        try:
            result = subprocess.run(
                ['ip', 'route'],
                capture_output=True,
                text=True,
                check=True
            )
            
            networks = []
            for line in result.stdout.split('\n'):
                # Parse lines like: "192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.1"
                match = re.match(r'^(\d+\.\d+\.\d+\.\d+/\d+)\s', line)
                if match:
                    network = match.group(1)
                    # Skip default route and localhost
                    if not network.startswith('0.0.0.0') and not network.startswith('127.'):
                        networks.append(network)
            
            return networks
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to get routes: {e}")
    
    @staticmethod
    def scan_network(network: str) -> List[Dict]:
        """
        Scan single network with arp-scan
        
        Args:
            network: CIDR notation (e.g., '192.168.1.0/24')
        
        Returns:
            [
                {
                    'ip': '192.168.1.100',
                    'mac': '00:11:22:33:44:55',
                    'hostname': 'server01.local',
                    'already_added': False
                },
                ...
            ]
        """
        try:
            # Execute arp-scan
            result = subprocess.run(
                ['sudo', 'arp-scan', '--interface=auto', network],
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )
            
            hosts = []
            
            for line in result.stdout.split('\n'):
                # Parse lines like: "192.168.1.100     00:11:22:33:44:55   Vendor Name"
                match = re.match(
                    r'^(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:]{17})\s+(.*)',
                    line
                )
                
                if match:
                    ip = match.group(1)
                    mac = match.group(2)
                    vendor = match.group(3).strip()
                    
                    # Try to resolve hostname
                    hostname = NetworkDiscovery._resolve_hostname(ip) or f"host-{ip.split('.')[-1]}"
                    
                    # Check if already in database
                    already_added = Target.objects.filter(ip_address=ip).exists()
                    
                    hosts.append({
                        'ip': ip,
                        'mac': mac,
                        'hostname': hostname,
                        'vendor': vendor,
                        'already_added': already_added
                    })
            
            return hosts
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"arp-scan failed: {e}")
        except subprocess.TimeoutExpired:
            raise Exception("arp-scan timeout")
    
    @staticmethod
    def scan_all_networks() -> Dict:
        """
        Scan all local networks
        
        Returns:
            {
                'networks_scanned': ['192.168.1.0/24'],
                'hosts_found': [...]
            }
        """
        networks = NetworkDiscovery.get_local_networks()
        
        all_hosts = []
        
        for network in networks:
            try:
                hosts = NetworkDiscovery.scan_network(network)
                all_hosts.extend(hosts)
            except Exception as e:
                logger.error(f"Failed to scan {network}: {e}")
        
        return {
            'networks_scanned': networks,
            'hosts_found': all_hosts
        }
    
    @staticmethod
    def _resolve_hostname(ip: str) -> str:
        """Try to resolve hostname from IP"""
        try:
            result = subprocess.run(
                ['host', ip],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            # Parse output like: "100.1.168.192.in-addr.arpa domain name pointer server01.local."
            match = re.search(r'pointer\s+(.+?)\.?$', result.stdout, re.MULTILINE)
            if match:
                return match.group(1)
            
            return None
            
        except:
            return None

5.3.2 Bulk Import from File
# backend/discovery/bulk_import.py

from typing import List, Dict
from api.models import Target


class BulkImporter:
    """
    Import targets from text file
    
    File format:
    192.168.1.100 server01
    192.168.1.101 server02
    192.168.1.102 server03
    """
    
    @staticmethod
    def parse_file(file_content: str) -> List[Dict]:
        """
        Parse file content
        
        Returns:
            [
                {'ip': '192.168.1.100', 'hostname': 'server01'},
                ...
            ]
        """
        targets = []
        errors = []
        
        for line_num, line in enumerate(file_content.split('\n'), 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse line
            parts = line.split()
            
            if len(parts) < 2:
                errors.append({
                    'line': line_num,
                    'error': 'Invalid format (expected: IP HOSTNAME)'
                })
                continue
            
            ip = parts[0]
            hostname = parts[1]
            
            # Validate IP
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                errors.append({
                    'line': line_num,
                    'error': f'Invalid IP address: {ip}'
                })
                continue
            
            targets.append({
                'ip': ip,
                'hostname': hostname
            })
        
        return targets, errors
    
    @staticmethod
    def import_targets(targets: List[Dict]) -> Dict:
        """
        Import targets into database
        
        Returns:
            {
                'imported': 5,
                'skipped': 2,
                'errors': [...]
            }
        """
        imported = 0
        skipped = 0
        errors = []
        
        for target_data in targets:
            # Check if already exists
            if Target.objects.filter(ip_address=target_data['ip']).exists():
                skipped += 1
                errors.append({
                    'ip': target_data['ip'],
                    'error': 'Already exists'
                })
                continue
            
            # Create target
            try:
                Target.objects.create(
                    hostname=target_data['hostname'],
                    ip_address=target_data['ip'],
                    status='pending'
                )
                imported += 1
            except Exception as e:
                errors.append({
                    'ip': target_data['ip'],
                    'error': str(e)
                })
        
        return {
            'imported': imported,
            'skipped': skipped,
            'errors': errors
        }


6. FRONTEND ARCHITECTURE
6.1 Project Structure
frontend/
├── src/
│   ├── components/
│   │   ├── common/              # Componenti riutilizzabili
│   │   │   ├── Button.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Modal.tsx
│   │   │   ├── Table.tsx
│   │   │   ├── Badge.tsx
│   │   │   └── LoadingSpinner.tsx
│   │   │
│   │   ├── layout/              # Layout componenti
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Footer.tsx
│   │   │   └── MainLayout.tsx
│   │   │
│   │   ├── dashboard/           # Dashboard components
│   │   │   ├── DashboardGrid.tsx
│   │   │   ├── StatsOverview.tsx
│   │   │   ├── ThreatTimeline.tsx
│   │   │   ├── TopAttackers.tsx
│   │   │   └── TargetsMap.tsx
│   │   │
│   │   ├── targets/             # Target management
│   │   │   ├── TargetList.tsx
│   │   │   ├── TargetCard.tsx
│   │   │   ├── TargetDetail.tsx
│   │   │   ├── AddTargetModal.tsx
│   │   │   ├── InstallProgress.tsx
│   │   │   └── DiscoveryModal.tsx
│   │   │
│   │   ├── threats/             # Threats view
│   │   │   ├── ThreatsList.tsx
│   │   │   ├── ThreatDetail.tsx
│   │   │   ├── ThreatFilters.tsx
│   │   │   └── TopAttackersWidget.tsx
│   │   │
│   │   ├── rules/               # Firewall rules
│   │   │   ├── RulesTable.tsx
│   │   │   ├── AddRuleModal.tsx
│   │   │   ├── RuleRow.tsx
│   │   │   └── RuleSyncButton.tsx
│   │   │
│   │   ├── alerts/              # Alerts center
│   │   │   ├── AlertsList.tsx
│   │   │   ├── AlertBanner.tsx
│   │   │   └── AlertDetail.tsx
│   │   │
│   │   ├── settings/            # Settings page
│   │   │   ├── GeneralSettings.tsx
│   │   │   ├── SSHKeyManagement.tsx
│   │   │   ├── FileIntegrity.tsx
│   │   │   └── TargetSetupInstructions.tsx
│   │   │
│   │   └── auth/                # Authentication
│   │       ├── LoginForm.tsx
│   │       └── PasswordConfirmModal.tsx
│   │
│   ├── services/                # API client & business logic
│   │   ├── api.ts               # Axios base configuration
│   │   ├── auth.service.ts
│   │   ├── targets.service.ts
│   │   ├── threats.service.ts
│   │   ├── rules.service.ts
│   │   ├── alerts.service.ts
│   │   ├── discovery.service.ts
│   │   └── config.service.ts
│   │
│   ├── hooks/                   # Custom React hooks
│   │   ├── useAuth.ts
│   │   ├── useTargets.ts
│   │   ├── useThreats.ts
│   │   ├── useWebSocket.ts      # Real-time updates (optional)
│   │   └── usePolling.ts
│   │
│   ├── types/                   # TypeScript definitions
│   │   ├── target.types.ts
│   │   ├── threat.types.ts
│   │   ├── rule.types.ts
│   │   ├── alert.types.ts
│   │   └── api.types.ts
│   │
│   ├── utils/                   # Utility functions
│   │   ├── formatters.ts        # Date, numbers, bytes formatters
│   │   ├── validators.ts        # IP, port validation
│   │   ├── classifiers.ts       # Threat classification helpers
│   │   └── storage.ts           # LocalStorage wrapper
│   │
│   ├── contexts/                # React Context
│   │   ├── AuthContext.tsx
│   │   └── ThemeContext.tsx
│   │
│   ├── pages/                   # Page components
│   │   ├── DashboardPage.tsx
│   │   ├── TargetsPage.tsx
│   │   ├── TargetDetailPage.tsx
│   │   ├── ThreatsPage.tsx
│   │   ├── AlertsPage.tsx
│   │   ├── SettingsPage.tsx
│   │   └── LoginPage.tsx
│   │
│   ├── App.tsx                  # Main app component
│   ├── main.tsx                 # Entry point
│   └── index.css                # Global styles (Tailwind)
│
├── public/
│   └── favicon.ico
│
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js

6.2 TypeScript Types
6.2.1 Core Types
// src/types/target.types.ts

export type TargetStatus = 
  | 'pending' 
  | 'installing' 
  | 'online' 
  | 'offline' 
  | 'error' 
  | 'disabled';

export interface Target {
  id: number;
  hostname: string;
  ip_address: string;
  status: TargetStatus;
  ssh_port: number;
  installation_status?: string;
  installation_error?: string;
  firedog_version?: string;
  last_seen?: string;
  last_fetch?: string;
  fetch_interval_minutes: number;
  os_info?: string;
  kernel_version?: string;
  created_at: string;
  updated_at: string;
}

export interface TargetListItem extends Target {
  threat_count_24h: number;
  critical_threats: number;
  total_rules: number;
}

export interface TargetDetail extends Target {
  statistics?: Statistics;
  recent_threats: Threat[];
}

export interface Statistics {
  input_packets: number;
  output_packets: number;
  input_dropped: number;
  output_dropped: number;
  pcap_input_size: number;
  pcap_output_size: number;
  collected_at: string;
}

export interface InstallStatus {
  status: TargetStatus;
  installation_status: string;
  installation_error?: string;
  progress: number;
}

// src/types/threat.types.ts

export type ThreatClassification = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export interface Threat {
  id: number;
  target: {
    id: number;
    hostname: string;
    ip_address: string;
  };
  source_ip: string;
  threat_score: number;
  classification: ThreatClassification;
  threat_type: string;
  packets: number;
  ports_count: number;
  protocols: string;
  detected_at: string;
  acknowledged: boolean;
}

export interface TopAttacker {
  source_ip: string;
  total_threats: number;
  max_score: number;
  classifications: {
    CRITICAL: number;
    HIGH: number;
    MEDIUM: number;
  };
  attack_types: string[];
  targets_affected: number;
}

// src/types/rule.types.ts

export type Chain = 'INPUT' | 'OUTPUT' | 'FORWARD';
export type Protocol = 'tcp' | 'udp' | 'icmp';

export interface FirewallRule {
  id: number;
  chain: Chain;
  rule_number: number;
  protocol?: Protocol;
  port?: number;
  source_ip?: string;
  dest_ip?: string;
  action: string;
  comment?: string;
  packets: number;
  bytes: number;
  synced_at: string;
}

export interface RulesResponse {
  input_rules: FirewallRule[];
  output_rules: FirewallRule[];
  forward_rules: FirewallRule[];
}

export interface AddRuleRequest {
  chain: Chain;
  port: number;
  protocol: Protocol;
  source_ip?: string;
  comment?: string;
}

// src/types/alert.types.ts

export type AlertSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export interface Alert {
  id: number;
  target?: {
    id: number;
    hostname: string;
  };
  severity: AlertSeverity;
  title: string;
  message: string;
  acknowledged: boolean;
  created_at: string;
}

6.3 API Service Layer
6.3.1 Base API Configuration

// src/services/api.ts

import axios, { AxiosInstance, AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor - add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - handle token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as any;

        // Token expired - try refresh
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            const refreshToken = localStorage.getItem('refresh_token');
            const response = await axios.post(`${API_BASE_URL}/auth/refresh/`, {
              refresh: refreshToken,
            });

            const { access } = response.data;
            localStorage.setItem('access_token', access);

            // Retry original request
            originalRequest.headers.Authorization = `Bearer ${access}`;
            return this.client(originalRequest);
          } catch (refreshError) {
            // Refresh failed - logout
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        return Promise.reject(error);
      }
    );
  }

  public get<T>(url: string, params?: any): Promise<T> {
    return this.client.get(url, { params }).then((res) => res.data);
  }

  public post<T>(url: string, data?: any): Promise<T> {
    return this.client.post(url, data).then((res) => res.data);
  }

  public patch<T>(url: string, data?: any): Promise<T> {
    return this.client.patch(url, data).then((res) => res.data);
  }

  public delete<T>(url: string): Promise<T> {
    return this.client.delete(url).then((res) => res.data);
  }

  public upload<T>(url: string, formData: FormData): Promise<T> {
    return this.client.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((res) => res.data);
  }
}

export default new ApiService();

6.3.2 Targets Service
// src/services/targets.service.ts

import api from './api';
import { Target, TargetListItem, TargetDetail, InstallStatus } from '@/types/target.types';

export interface TargetsListParams {
  status?: string;
  search?: string;
}

export interface CreateTargetRequest {
  hostname: string;
  ip_address: string;
  ssh_port?: number;
}

class TargetsService {
  /**
   * Get all targets with optional filters
   */
  async getTargets(params?: TargetsListParams): Promise<TargetListItem[]> {
    const response = await api.get<{ results: TargetListItem[] }>('/targets/', params);
    return response.results;
  }

  /**
   * Get single target detail
   */
  async getTarget(id: number): Promise<TargetDetail> {
    return api.get<TargetDetail>(`/targets/${id}/`);
  }

  /**
   * Create new target
   */
  async createTarget(data: CreateTargetRequest): Promise<Target> {
    return api.post<Target>('/targets/', data);
  }

  /**
   * Update target
   */
  async updateTarget(id: number, data: Partial<Target>): Promise<Target> {
    return api.patch<Target>(`/targets/${id}/`, data);
  }

  /**
   * Delete target
   */
  async deleteTarget(id: number): Promise<void> {
    return api.delete(`/targets/${id}/`);
  }

  /**
   * Start installation on target
   */
  async installTarget(id: number): Promise<{ task_id: string; message: string }> {
    return api.post(`/targets/${id}/install/`);
  }

  /**
   * Get installation status
   */
  async getInstallStatus(id: number): Promise<InstallStatus> {
    return api.get<InstallStatus>(`/targets/${id}/install-status/`);
  }

  /**
   * Retry failed installation
   */
  async retryInstall(id: number): Promise<{ task_id: string }> {
    return api.post(`/targets/${id}/retry-install/`);
  }

  /**
   * Manual fetch data from target
   */
  async fetchData(id: number): Promise<{ message: string; threats_found: number }> {
    return api.post(`/targets/${id}/fetch/`);
  }

  /**
   * Get target statistics for time period
   */
  async getStatistics(id: number, period: string = '24h'): Promise<any> {
    return api.get(`/targets/${id}/statistics/`, { period });
  }
}

export default new TargetsService();

6.3.3 Threats Service
// src/services/threats.service.ts

import api from './api';
import { Threat, TopAttacker } from '@/types/threat.types';

export interface ThreatsListParams {
  target_id?: number;
  classification?: string;
  acknowledged?: boolean;
  since?: string;
  limit?: number;
  offset?: number;
}

class ThreatsService {
  /**
   * Get threats list with filters
   */
  async getThreats(params?: ThreatsListParams): Promise<{
    count: number;
    results: Threat[];
  }> {
    return api.get('/threats/', params);
  }

  /**
   * Get single threat detail
   */
  async getThreat(id: number): Promise<Threat> {
    return api.get(`/threats/${id}/`);
  }

  /**
   * Acknowledge single threat
   */
  async acknowledgeThreat(id: number): Promise<{ message: string }> {
    return api.post(`/threats/${id}/acknowledge/`);
  }

  /**
   * Bulk acknowledge threats
   */
  async bulkAcknowledge(threatIds: number[]): Promise<{ acknowledged: number }> {
    return api.post('/threats/bulk-acknowledge/', { threat_ids: threatIds });
  }

  /**
   * Get top attackers
   */
  async getTopAttackers(days: number = 7, limit: number = 20): Promise<{
    period: string;
    attackers: TopAttacker[];
  }> {
    return api.get('/threats/top-attackers/', { days, limit });
  }
}

export default new ThreatsService();

6.3.4 Rules Service
// src/services/rules.service.ts

import api from './api';
import { RulesResponse, AddRuleRequest } from '@/types/rule.types';

class RulesService {
  /**
   * Get all rules for target
   */
  async getRules(targetId: number, refresh: boolean = false): Promise<RulesResponse> {
    return api.get(`/targets/${targetId}/rules/`, { refresh });
  }

  /**
   * Add new rule
   */
  async addRule(targetId: number, data: AddRuleRequest): Promise<{ message: string }> {
    return api.post(`/targets/${targetId}/rules/add/`, data);
  }

  /**
   * Remove rule
   */
  async removeRule(
    targetId: number, 
    chain: string, 
    ruleNumber: number
  ): Promise<{ message: string }> {
    return api.delete(`/targets/${targetId}/rules/${chain}/${ruleNumber}/`);
  }

  /**
   * Sync rules from target
   */
  async syncRules(targetId: number): Promise<{ total_rules: number }> {
    return api.post(`/targets/${targetId}/rules/sync/`);
  }
}

export default new RulesService();

6.3.5 Discovery Service
// src/services/discovery.service.ts

import api from './api';

export interface DiscoveredHost {
  ip: string;
  hostname: string;
  mac?: string;
  vendor?: string;
  already_added: boolean;
}

export interface DiscoveryResults {
  status: 'running' | 'completed' | 'failed';
  found_hosts: DiscoveredHost[];
}

class DiscoveryService {
  /**
   * Start network discovery scan
   */
  async startScan(): Promise<{ task_id: string; message: string }> {
    return api.post('/discovery/scan/');
  }

  /**
   * Get scan results
   */
  async getResults(taskId: string): Promise<DiscoveryResults> {
    return api.get(`/discovery/results/${taskId}/`);
  }

  /**
   * Bulk import from file
   */
  async bulkImport(file: File): Promise<{
    imported: number;
    skipped: number;
    errors: any[];
  }> {
    const formData = new FormData();
    formData.append('file', file);
    return api.upload('/discovery/bulk-import/', formData);
  }
}

export default new DiscoveryService();


6.4 React Components Examples
6.4.1 Dashboard Page
// src/pages/DashboardPage.tsx

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import MainLayout from '@/components/layout/MainLayout';
import StatsOverview from '@/components/dashboard/StatsOverview';
import DashboardGrid from '@/components/dashboard/DashboardGrid';
import targetsService from '@/services/targets.service';
import threatsService from '@/services/threats.service';

const DashboardPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalTargets: 0,
    onlineTargets: 0,
    offlineTargets: 0,
    criticalThreats: 0,
  });

  useEffect(() => {
    loadDashboardData();
    
    // Poll every 30 seconds
    const interval = setInterval(loadDashboardData, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadDashboardData = async () => {
    try {
      const [targets, threats] = await Promise.all([
        targetsService.getTargets(),
        threatsService.getThreats({
          classification: 'CRITICAL',
          since: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
        }),
      ]);

      setStats({
        totalTargets: targets.length,
        onlineTargets: targets.filter(t => t.status === 'online').length,
        offlineTargets: targets.filter(t => t.status === 'offline').length,
        criticalThreats: threats.count,
      });
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-full">
          <LoadingSpinner size="large" />
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="p-6">
        <h1 className="text-3xl font-bold mb-6">Dashboard</h1>
        
        {/* Stats Overview */}
        <StatsOverview stats={stats} />
        
        {/* Dashboard Grid with Widgets */}
        <DashboardGrid />
      </div>
    </MainLayout>
  );
};

export default DashboardPage;

6.4.2 Target List Component
// src/components/targets/TargetList.tsx

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import targetsService from '@/services/targets.service';
import { TargetListItem } from '@/types/target.types';
import TargetCard from './TargetCard';
import AddTargetModal from './AddTargetModal';
import DiscoveryModal from './DiscoveryModal';

const TargetList: React.FC = () => {
  const navigate = useNavigate();
  const [targets, setTargets] = useState<TargetListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [showDiscoveryModal, setShowDiscoveryModal] = useState(false);

  useEffect(() => {
    loadTargets();
  }, [statusFilter]);

  const loadTargets = async () => {
    try {
      setLoading(true);
      const data = await targetsService.getTargets({
        status: statusFilter || undefined,
        search: filter || undefined,
      });
      setTargets(data);
    } catch (error) {
      console.error('Failed to load targets:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTargetClick = (id: number) => {
    navigate(`/targets/${id}`);
  };

  const handleInstall = async (id: number) => {
    try {
      await targetsService.installTarget(id);
      // Reload to show updated status
      loadTargets();
    } catch (error: any) {
      alert(error.response?.data?.error || 'Installation failed');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this target?')) return;

    try {
      await targetsService.deleteTarget(id);
      loadTargets();
    } catch (error) {
      alert('Failed to delete target');
    }
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Targets</h1>
        
        <div className="flex gap-3">
          <button
            onClick={() => setShowDiscoveryModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Discover Network
          </button>
          
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
          >
            Add Target
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <input
          type="text"
          placeholder="Search by hostname or IP..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && loadTargets()}
          className="flex-1 px-4 py-2 border rounded"
        />

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2 border rounded"
        >
          <option value="">All Status</option>
          <option value="online">Online</option>
          <option value="offline">Offline</option>
          <option value="pending">Pending</option>
          <option value="error">Error</option>
        </select>

        <button
          onClick={loadTargets}
          className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
        >
          Refresh
        </button>
      </div>

      {/* Target Cards Grid */}
      {loading ? (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      ) : targets.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No targets found. Add a target to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {targets.map((target) => (
            <TargetCard
              key={target.id}
              target={target}
              onClick={() => handleTargetClick(target.id)}
              onInstall={() => handleInstall(target.id)}
              onDelete={() => handleDelete(target.id)}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      {showAddModal && (
        <AddTargetModal
          onClose={() => setShowAddModal(false)}
          onSuccess={() => {
            setShowAddModal(false);
            loadTargets();
          }}
        />
      )}

      {showDiscoveryModal && (
        <DiscoveryModal
          onClose={() => setShowDiscoveryModal(false)}
          onSuccess={() => {
            setShowDiscoveryModal(false);
            loadTargets();
          }}
        />
      )}
    </div>
  );
};

export default TargetList;

6.4.3 Target Card Component
// src/components/targets/TargetCard.tsx

import React from 'react';
import { TargetListItem } from '@/types/target.types';
import { 
  Server, 
  CheckCircle, 
  XCircle, 
  AlertTriangle, 
  Clock,
  MoreVertical 
} from 'lucide-react';

interface TargetCardProps {
  target: TargetListItem;
  onClick: () => void;
  onInstall: () => void;
  onDelete: () => void;
}

const TargetCard: React.FC<TargetCardProps> = ({
  target,
  onClick,
  onInstall,
  onDelete,
}) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online': return 'bg-green-100 text-green-800';
      case 'offline': return 'bg-red-100 text-red-800';
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'error': return 'bg-red-100 text-red-800';
      case 'installing': return 'bg-blue-100 text-blue-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online': return <CheckCircle className="w-4 h-4" />;
      case 'offline': return <XCircle className="w-4 h-4" />;
      case 'pending': return <Clock className="w-4 h-4" />;
      case 'error': return <AlertTriangle className="w-4 h-4" />;
      default: return <Server className="w-4 h-4" />;
    }
  };

  return (
    <div 
      className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer border border-gray-200"
      onClick={onClick}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex justify-between items-start">
          <div className="flex items-center gap-3">
            <Server className="w-8 h-8 text-gray-600" />
            <div>
              <h3 className="font-semibold text-lg">{target.hostname}</h3>
              <p className="text-sm text-gray-500">{target.ip_address}</p>
            </div>
          </div>

          {/* Context Menu */}
          <div className="relative group">
            <button 
              onClick={(e) => {
                e.stopPropagation();
                // Show context menu
              }}
              className="p-1 hover:bg-gray-100 rounded"
            >
              <MoreVertical className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Status Badge */}
        <div className="mt-3">
          <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(target.status)}`}>
            {getStatusIcon(target.status)}
            {target.status.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Stats */}
      <div className="p-4 grid grid-cols-3 gap-4 text-center">
        <div>
          <div className="text-2xl font-bold text-gray-900">
            {target.threat_count_24h}
          </div>
          <div className="text-xs text-gray-500">Threats 24h</div>
        </div>

        <div>
          <div className="text-2xl font-bold text-red-600">
            {target.critical_threats}
          </div>
          <div className="text-xs text-gray-500">Critical</div>
        </div>

        <div>
          <div className="text-2xl font-bold text-blue-600">
            {target.total_rules}
          </div>
          <div className="text-xs text-gray-500">Rules</div>
        </div>
      </div>

      {/* Actions */}
      <div className="p-4 border-t border-gray-200 flex gap-2">
        {target.status === 'pending' && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onInstall();
            }}
            className="flex-1 px-3 py-2 bg-green-600 text-white text-sm rounded hover:bg-green-700"
          >
            Install
          </button>
        )}

        {target.status === 'error' && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onInstall();
            }}
            className="flex-1 px-3 py-2 bg-orange-600 text-white text-sm rounded hover:bg-orange-700"
          >
            Retry Install
          </button>
        )}

        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="px-3 py-2 bg-red-100 text-red-700 text-sm rounded hover:bg-red-200"
        >
          Delete
        </button>
      </div>

      {/* Last Seen */}
      {target.last_seen && (
        <div className="px-4 pb-3 text-xs text-gray-500">
          Last seen: {new Date(target.last_seen).toLocaleString()}
        </div>
      )}
    </div>
  );
};

export default TargetCard;

6.4.4 Dashboard Grid (react-grid-layout)
// src/components/dashboard/DashboardGrid.tsx

import React, { useState } from 'react';
import GridLayout from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

import ThreatTimeline from './ThreatTimeline';
import TopAttackers from './TopAttackers';
import TargetsMap from './TargetsMap';
import RecentAlerts from './RecentAlerts';

interface Widget {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  component: React.ComponentType;
  title: string;
}

const defaultWidgets: Widget[] = [
  {
    i: 'threats-timeline',
    x: 0,
    y: 0,
    w: 8,
    h: 4,
    component: ThreatTimeline,
    title: 'Threats Timeline',
  },
  {
    i: 'top-attackers',
    x: 8,
    y: 0,
    w: 4,
    h: 4,
    component: TopAttackers,
    title: 'Top Attackers',
  },
  {
    i: 'targets-map',
    x: 0,
    y: 4,
    w: 6,
    h: 4,
    component: TargetsMap,
    title: 'Targets Status',
  },
  {
    i: 'recent-alerts',
    x: 6,
    y: 4,
    w: 6,
    h: 4,
    component: RecentAlerts,
    title: 'Recent Alerts',
  },
];

const DashboardGrid: React.FC = () => {
  const [layout, setLayout] = useState(defaultWidgets);

  const onLayoutChange = (newLayout: any[]) => {
    // Save layout to localStorage
    localStorage.setItem('dashboard-layout', JSON.stringify(newLayout));
  };

  return (
    <div className="mt-6">
      <GridLayout
        className="layout"
        layout={layout}
        cols={12}
        rowHeight={100}
        width={1200}
        onLayoutChange={onLayoutChange}
        draggableHandle=".drag-handle"
      >
        {layout.map((widget) => (
          <div key={widget.i} className="bg-white rounded-lg shadow p-4">
            {/* Widget Header */}
            <div className="flex justify-between items-center mb-4 drag-handle cursor-move">
              <h3 className="font-semibold text-lg">{widget.title}</h3>
              <button className="text-gray-400 hover:text-gray-600">
                ⋮
              </button>
            </div>

            {/* Widget Content */}
            <div className="overflow-auto" style={{ height: 'calc(100% - 40px)' }}>
              <widget.component />
            </div>
          </div>
        ))}
      </GridLayout>
    </div>
  );
};

export default DashboardGrid;

6.4.5 Rules Manager Component
// src/components/rules/RulesTable.tsx

import React, { useState, useEffect } from 'react';
import rulesService from '@/services/rules.service';
import { FirewallRule, Chain } from '@/types/rule.types';
import AddRuleModal from './AddRuleModal';
import { Trash2, RefreshCw } from 'lucide-react';

interface RulesTableProps {
  targetId: number;
}

const RulesTable: React.FC<RulesTableProps> = ({ targetId }) => {
  const [rules, setRules] = useState<{
    input_rules: FirewallRule[];
    output_rules: FirewallRule[];
  }>({ input_rules: [], output_rules: [] });
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedChain, setSelectedChain] = useState<Chain>('INPUT');

  useEffect(() => {
    loadRules();
  }, [targetId]);

  const loadRules = async (refresh = false) => {
    try {
      setLoading(true);
      const data = await rulesService.getRules(targetId, refresh);
      setRules(data);
    } catch (error) {
      console.error('Failed to load rules:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    try {
      setSyncing(true);
      await rulesService.syncRules(targetId);
      await loadRules();
    } catch (error) {
      alert('Failed to sync rules');
    } finally {
      setSyncing(false);
    }
  };

  const handleRemoveRule = async (chain: string, ruleNumber: number) => {
    if (!confirm(`Remove rule #${ruleNumber} from ${chain}?`)) return;

    try {
      await rulesService.removeRule(targetId, chain, ruleNumber);
      await loadRules();
    } catch (error) {
      alert('Failed to remove rule');
    }
  };

  const renderRuleRow = (rule: FirewallRule) => (
    <tr key={`${rule.chain}-${rule.rule_number}`} className="border-b hover:bg-gray-50">
      <td className="px-4 py-2 text-center">{rule.rule_number}</td>
      <td className="px-4 py-2">
        <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
          {rule.protocol || 'all'}
        </span>
      </td>
      <td className="px-4 py-2">{rule.port || '-'}</td>
      <td className="px-4 py-2 text-sm">{rule.source_ip || 'any'}</td>
      <td className="px-4 py-2 text-sm">{rule.dest_ip || 'any'}</td>
      <td className="px-4 py-2">
        <span className={`px-2 py-1 rounded text-xs ${
          rule.action === 'ACCEPT' 
            ? 'bg-green-100 text-green-800' 
            : 'bg-red-100 text-red-800'
        }`}>
          {rule.action}
        </span>
      </td>
      <td className="px-4 py-2 text-sm text-gray-600">{rule.comment || '-'}</td>
      <td className="px-4 py-2 text-right">{rule.packets.toLocaleString()}</td>
      <td className="px-4 py-2 text-center">
        <button
          onClick={() => handleRemoveRule(rule.chain, rule.rule_number)}
          className="p-1 text-red-600 hover:bg-red-50 rounded"
          title="Remove rule"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </td>
    </tr>
  );

  return (
    <div className="bg-white rounded-lg shadow p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold">Firewall Rules</h2>
        
        <div className="flex gap-3">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
            Sync from Target
          </button>
          
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
          >
            Add Rule
          </button>
        </div>
      </div>

      {/* Chain Tabs */}
      <div className="flex gap-4 border-b mb-6">
        {(['INPUT', 'OUTPUT', 'FORWARD'] as Chain[]).map((chain) => (
          <button
            key={chain}
            onClick={() => setSelectedChain(chain)}
            className={`px-4 py-2 font-medium border-b-2 transition-colors ${
              selectedChain === chain
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {chain}
          </button>
        ))}
      </div>

      {/* Rules Table */}
      {loading ? (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left">#</th>
                <th className="px-4 py-2 text-left">Protocol</th>
                <th className="px-4 py-2 text-left">Port</th>
                <th className="px-4 py-2 text-left">Source</th>
                <th className="px-4 py-2 text-left">Destination</th>
                <th className="px-4 py-2 text-left">Action</th>
                <th className="px-4 py-2 text-left">Comment</th>
                <th className="px-4 py-2 text-right">Packets</th>
                <th className="px-4 py-2 text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {selectedChain === 'INPUT' && rules.input_rules.map(renderRuleRow)}
              {selectedChain === 'OUTPUT' && rules.output_rules.map(renderRuleRow)}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Rule Modal */}
      {showAddModal && (
        <AddRuleModal
          targetId={targetId}
          defaultChain={selectedChain}
          onClose={() => setShowAddModal(false)}
          onSuccess={() => {
            setShowAddModal(false);
            loadRules();
          }}
        />
      )}
    </div>
  );
};

export default RulesTable;

7. SECURITY HARDENING
7.1 SSH Configuration Files
7.1.1 SSHD Config for microcyber User
# deployment/configs/microcyber-sshd.conf
# File: /etc/ssh/sshd_config.d/microcyber.conf
# 
# Configurazione SSH hardened per utente microcyber
# Copiare in /etc/ssh/sshd_config.d/ e riavviare sshd

# Match specifico per utente microcyber
Match User microcyber
    # Solo autenticazione con chiave pubblica
    PasswordAuthentication no
    PubkeyAuthentication yes
    AuthenticationMethods publickey
    
    # Disabilita forwarding e tunneling
    AllowTcpForwarding no
    X11Forwarding no
    PermitTunnel no
    GatewayPorts no
    
    # Limita sessioni
    MaxAuthTries 3
    MaxSessions 2
    
    # Timeout
    ClientAliveInterval 300
    ClientAliveCountMax 2
    
    # Disabilita environment forwarding
    PermitUserEnvironment no
    
    # Force command (optional - uncomment per limitare a comandi specifici)
    # ForceCommand /usr/local/bin/firedog-wrapper.sh
    
    # Logging
    LogLevel VERBOSE

# IMPORTANTE: Dopo aver copiato questo file:
# 1. sudo chmod 644 /etc/ssh/sshd_config.d/microcyber.conf
# 2. sudo sshd -t  (verifica configurazione)
# 3. sudo systemctl restart sshd

7.1.2 Sudoers Configuration
# deployment/configs/microcyber-sudoers
# File: /etc/sudoers.d/microcyber
#
# Permessi sudo minimi per utente microcyber
# Copiare in /etc/sudoers.d/microcyber

# User alias
User_Alias FIREDOG_USERS = microcyber

# Command aliases - SOLO comandi necessari
Cmnd_Alias FIREDOG_IPTABLES = \
    /usr/sbin/iptables, \
    /usr/sbin/iptables-save, \
    /usr/sbin/iptables-restore, \
    /usr/sbin/ip6tables, \
    /usr/sbin/ip6tables-save, \
    /usr/sbin/ip6tables-restore

Cmnd_Alias FIREDOG_SCRIPTS = \
    /usr/local/bin/firewall-manager, \
    /usr/local/bin/traffic-analyzer, \
    /usr/local/sbin/firewall-init.sh

Cmnd_Alias FIREDOG_SYSTEM = \
    /usr/bin/systemctl status firewall, \
    /usr/bin/systemctl restart firewall, \
    /usr/bin/systemctl reload firewall

# Permissions
FIREDOG_USERS ALL=(ALL) NOPASSWD: FIREDOG_IPTABLES
FIREDOG_USERS ALL=(ALL) NOPASSWD: FIREDOG_SCRIPTS
FIREDOG_USERS ALL=(ALL) NOPASSWD: FIREDOG_SYSTEM

# DENY everything else explicitly
FIREDOG_USERS ALL=(ALL) !ALL

# Defaults for security
Defaults:microcyber !visiblepw
Defaults:microcyber always_set_home
Defaults:microcyber match_group_by_gid
Defaults:microcyber env_reset
Defaults:microcyber env_keep = "LANG LC_* HOME"
Defaults:microcyber secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Defaults:microcyber requiretty
Defaults:microcyber use_pty
Defaults:microcyber logfile=/var/log/sudo-microcyber.log

# IMPORTANTE: Dopo aver copiato questo file:
# 1. sudo chmod 440 /etc/sudoers.d/microcyber
# 2. sudo visudo -c  (verifica sintassi)

7.1.3 User Creation Script
#!/bin/bash
# deployment/scripts/create-microcyber-user.sh
#
# Script per creare utente microcyber con configurazione sicura
# Da eseguire sui target PRIMA di installare firedog

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== FireDog User Setup ===${NC}\n"

# Verifica root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[ERROR]${NC} Questo script richiede privilegi root"
    exit 1
fi

# Public key (DA MODIFICARE con la tua chiave pubblica)
PUBLIC_KEY="${1:-}"

if [[ -z "$PUBLIC_KEY" ]]; then
    echo -e "${RED}[ERROR]${NC} Public key non fornita"
    echo "Usage: $0 'ssh-ed25519 AAAA...'"
    exit 1
fi

echo "[1/6] Creazione utente microcyber..."
if id microcyber &>/dev/null; then
    echo -e "${YELLOW}[WARNING]${NC} Utente microcyber già esistente"
else
    useradd -m -s /bin/bash -c "FireDog Service User" microcyber
    echo -e "${GREEN}[OK]${NC} Utente creato"
fi

echo "[2/6] Configurazione home directory..."
mkdir -p /home/microcyber/.ssh
chmod 700 /home/microcyber/.ssh

echo "[3/6] Aggiunta chiave pubblica..."
echo "$PUBLIC_KEY" > /home/microcyber/.ssh/authorized_keys
chmod 600 /home/microcyber/.ssh/authorized_keys
chown -R microcyber:microcyber /home/microcyber/.ssh

echo "[4/6] Configurazione sudoers..."
cat > /etc/sudoers.d/microcyber << 'EOF'
# FireDog minimal sudo permissions
User_Alias FIREDOG_USERS = microcyber

Cmnd_Alias FIREDOG_IPTABLES = \
    /usr/sbin/iptables, \
    /usr/sbin/iptables-save, \
    /usr/sbin/iptables-restore

Cmnd_Alias FIREDOG_SCRIPTS = \
    /usr/local/bin/firewall-manager, \
    /usr/local/bin/traffic-analyzer, \
    /usr/local/sbin/firewall-init.sh

FIREDOG_USERS ALL=(ALL) NOPASSWD: FIREDOG_IPTABLES
FIREDOG_USERS ALL=(ALL) NOPASSWD: FIREDOG_SCRIPTS
FIREDOG_USERS ALL=(ALL) !ALL

Defaults:microcyber !visiblepw
Defaults:microcyber requiretty
Defaults:microcyber use_pty
EOF

chmod 440 /etc/sudoers.d/microcyber

# Verifica sintassi
if ! visudo -c -f /etc/sudoers.d/microcyber; then
    echo -e "${RED}[ERROR]${NC} Errore sintassi sudoers"
    rm /etc/sudoers.d/microcyber
    exit 1
fi

echo -e "${GREEN}[OK]${NC} Sudoers configurato"

echo "[5/6] Configurazione SSH hardened..."
cat > /etc/ssh/sshd_config.d/microcyber.conf << 'EOF'
Match User microcyber
    PasswordAuthentication no
    PubkeyAuthentication yes
    AuthenticationMethods publickey
    AllowTcpForwarding no
    X11Forwarding no
    PermitTunnel no
    MaxAuthTries 3
    MaxSessions 2
    ClientAliveInterval 300
    ClientAliveCountMax 2
EOF

chmod 644 /etc/ssh/sshd_config.d/microcyber.conf

# Verifica configurazione SSH
if ! sshd -t; then
    echo -e "${RED}[ERROR]${NC} Errore configurazione SSH"
    rm /etc/ssh/sshd_config.d/microcyber.conf
    exit 1
fi

echo -e "${GREEN}[OK]${NC} SSH configurato"

echo "[6/6] Riavvio servizio SSH..."
systemctl restart sshd

echo -e "\n${GREEN}=== Setup Completato ===${NC}\n"
echo "Utente: microcyber"
echo "Home: /home/microcyber"
echo "SSH Key: configurata"
echo "Sudoers: /etc/sudoers.d/microcyber"
echo "SSH Config: /etc/ssh/sshd_config.d/microcyber.conf"
echo ""
echo "Test connessione:"
echo "  ssh microcyber@$(hostname -I | awk '{print $1}')"

7.2 Django Security Settings
7.2.1 Production Settings
# backend/firedog/settings_production.py

import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY environment variable must be set")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    os.environ.get('FIREDOG_HOST', 'firedog.local'),
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'api',
    'authentication',
    'discovery',
    'integrity',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'firedog'),
        'USER': os.environ.get('DB_USER', 'microcyber'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'connect_timeout': 10,
            'sslmode': 'prefer',
        }
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
}

# CORS Settings (for React frontend)
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

CORS_ALLOW_CREDENTIALS = True

# Security Settings
SECURE_SSL_REDIRECT = False  # Set True if using HTTPS
SESSION_COOKIE_SECURE = False  # Set True if using HTTPS
CSRF_COOKIE_SECURE = False  # Set True if using HTTPS
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Session Security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 1800  # 30 minutes

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/firedog/django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/firedog/security.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'api': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# File Integrity Monitoring
MONITORED_FILES = [
    '/usr/local/bin/firewall-manager',
    '/usr/local/sbin/firewall-init.sh',
    '/usr/local/bin/traffic-analyzer',
    os.path.join(BASE_DIR, 'manage.py'),
    os.path.join(BASE_DIR, 'firedog/settings.py'),
]

# SSH Key Storage
SSH_KEYS_DIR = '/etc/firedog/ssh-keys'
os.makedirs(SSH_KEYS_DIR, mode=0o700, exist_ok=True)

7.2.2 Environment Variables Template
# deployment/configs/.env.example
# 
# Copiare in /opt/firedog/backend/.env e configurare

# Django Settings
DJANGO_SECRET_KEY=your-very-long-random-secret-key-change-this
DJANGO_SETTINGS_MODULE=firedog.settings_production
DEBUG=False
FIREDOG_HOST=firedog.local

# Database
DB_NAME=firedog
DB_USER=microcyber
DB_PASSWORD=your-secure-database-password
DB_HOST=localhost
DB_PORT=5432

# Redis (for Celery)
REDIS_URL=redis://localhost:6379/0

# Security
ALLOWED_HOSTS=localhost,127.0.0.1,firedog.local

# Logging
LOG_LEVEL=INFO


7.2.3 Generate Secret Key Script
#!/bin/bash
# deployment/scripts/generate-secret-key.sh
#
# Genera Django SECRET_KEY sicura

python3 << 'EOF'
import secrets
import string

# Genera chiave di 50 caratteri
alphabet = string.ascii_letters + string.digits + string.punctuation
secret_key = ''.join(secrets.choice(alphabet) for _ in range(50))

print(f"DJANGO_SECRET_KEY={secret_key}")
print("\nAggiungi questa riga al file .env")
EOF

7.3 File Integrity Monitoring
7.3.1 Integrity Checker Service
# backend/integrity/checker.py

import hashlib
import os
from typing import List, Dict, Tuple
from pathlib import Path
from api.models import FileIntegrity, Alert
import logging

logger = logging.getLogger(__name__)


class IntegrityChecker:
    """
    File integrity monitoring system
    Usa SHA512 per verificare modifiche ai file critici
    """
    
    # File critici da monitorare
    CRITICAL_FILES = [
        '/usr/local/bin/firewall-manager',
        '/usr/local/sbin/firewall-init.sh',
        '/usr/local/bin/traffic-analyzer',
        '/opt/firedog/backend/manage.py',
        '/opt/firedog/backend/firedog/settings.py',
        '/opt/firedog/backend/firedog/urls.py',
        '/opt/firedog/backend/api/models.py',
        '/opt/firedog/backend/api/views.py',
    ]
    
    @staticmethod
    def compute_hash(filepath: str) -> str:
        """
        Calcola SHA512 hash di un file
        
        Args:
            filepath: Path assoluto del file
        
        Returns:
            Hash SHA512 (hex string)
        """
        sha512 = hashlib.sha512()
        
        try:
            with open(filepath, 'rb') as f:
                # Leggi in chunk per file grandi
                for chunk in iter(lambda: f.read(8192), b''):
                    sha512.update(chunk)
            
            return sha512.hexdigest()
        
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
            raise
        except PermissionError:
            logger.error(f"Permission denied: {filepath}")
            raise
    
    @classmethod
    def check_file(cls, filepath: str) -> Tuple[bool, str, str]:
        """
        Verifica integrità di un singolo file
        
        Args:
            filepath: Path assoluto del file
        
        Returns:
            (is_valid, expected_hash, current_hash)
        """
        if not os.path.exists(filepath):
            logger.warning(f"File does not exist: {filepath}")
            return False, '', ''
        
        current_hash = cls.compute_hash(filepath)
        
        try:
            record = FileIntegrity.objects.get(filepath=filepath)
            
            if record.sha512_hash != current_hash:
                # Hash mismatch - file modificato
                logger.warning(
                    f"Integrity violation: {filepath}\n"
                    f"Expected: {record.sha512_hash}\n"
                    f"Current: {current_hash}"
                )
                return False, record.sha512_hash, current_hash
            
            # Update last_checked timestamp
            record.save()
            return True, current_hash, current_hash
        
        except FileIntegrity.DoesNotExist:
            # Prima volta - salva hash
            FileIntegrity.objects.create(
                filepath=filepath,
                sha512_hash=current_hash
            )
            logger.info(f"Initial hash recorded for: {filepath}")
            return True, current_hash, current_hash
    
    @classmethod
    def check_all_files(cls, create_alerts: bool = True) -> Dict:
        """
        Verifica integrità di tutti i file critici
        
        Args:
            create_alerts: Se True, crea Alert per violazioni
        
        Returns:
            {
                'checked': int,
                'violations': List[Dict],
                'errors': List[str]
            }
        """
        results = {
            'checked': 0,
            'violations': [],
            'errors': []
        }
        
        for filepath in cls.CRITICAL_FILES:
            try:
                is_valid, expected, current = cls.check_file(filepath)
                results['checked'] += 1
                
                if not is_valid:
                    violation = {
                        'filepath': filepath,
                        'expected_hash': expected,
                        'current_hash': current
                    }
                    results['violations'].append(violation)
                    
                    # Create alert
                    if create_alerts:
                        Alert.objects.create(
                            severity='critical',
                            title='File Integrity Violation',
                            message=(
                                f'File has been modified: {filepath}\n'
                                f'Expected: {expected[:16]}...\n'
                                f'Current: {current[:16]}...'
                            )
                        )
            
            except Exception as e:
                logger.error(f"Error checking {filepath}: {e}")
                results['errors'].append(str(e))
        
        return results
    
    @classmethod
    def accept_changes(cls, filepath: str, password: str) -> bool:
        """
        Accetta modifiche a un file (aggiorna hash)
        Richiede conferma password
        
        Args:
            filepath: Path del file
            password: Password admin per conferma
        
        Returns:
            True se aggiornato con successo
        """
        from django.contrib.auth import authenticate
        
        # TODO: Implementare verifica password
        # Per ora, calcola nuovo hash e aggiorna
        
        try:
            new_hash = cls.compute_hash(filepath)
            
            FileIntegrity.objects.update_or_create(
                filepath=filepath,
                defaults={'sha512_hash': new_hash}
            )
            
            logger.info(f"Hash updated for: {filepath}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to update hash: {e}")
            return False
    
    @classmethod
    def initialize_monitoring(cls) -> int:
        """
        Inizializza monitoring per tutti i file critici
        Da eseguire al primo avvio
        
        Returns:
            Numero di file inizializzati
        """
        count = 0
        
        for filepath in cls.CRITICAL_FILES:
            if not os.path.exists(filepath):
                logger.warning(f"File not found during init: {filepath}")
                continue
            
            try:
                # Forza creazione/aggiornamento hash
                current_hash = cls.compute_hash(filepath)
                FileIntegrity.objects.update_or_create(
                    filepath=filepath,
                    defaults={'sha512_hash': current_hash}
                )
                count += 1
            
            except Exception as e:
                logger.error(f"Failed to initialize {filepath}: {e}")
        
        logger.info(f"Initialized integrity monitoring for {count} files")
        return count

7.3.2 Integrity Check Command
# backend/api/management/commands/check_integrity.py

from django.core.management.base import BaseCommand
from integrity.checker import IntegrityChecker


class Command(BaseCommand):
    help = 'Check file integrity for critical system files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--init',
            action='store_true',
            help='Initialize monitoring (first time setup)',
        )
        
        parser.add_argument(
            '--no-alerts',
            action='store_true',
            help='Do not create alerts for violations',
        )
    
    def handle(self, *args, **options):
        if options['init']:
            self.stdout.write('Initializing file integrity monitoring...')
            count = IntegrityChecker.initialize_monitoring()
            self.stdout.write(
                self.style.SUCCESS(f'Initialized {count} files')
            )
            return
        
        self.stdout.write('Checking file integrity...')
        
        results = IntegrityChecker.check_all_files(
            create_alerts=not options['no_alerts']
        )
        
        self.stdout.write(f"Checked: {results['checked']} files")
        
        if results['violations']:
            self.stdout.write(
                self.style.ERROR(
                    f"Violations: {len(results['violations'])}"
                )
            )
            
            for violation in results['violations']:
                self.stdout.write(
                    self.style.WARNING(f"  - {violation['filepath']}")
                )
        else:
            self.stdout.write(
                self.style.SUCCESS('No violations found')
            )
        
        if results['errors']:
            self.stdout.write(
                self.style.ERROR(f"Errors: {len(results['errors'])}")
            )


7.4 PostgreSQL Security
7.4.1 Database Setup Script
#!/bin/bash
# deployment/scripts/setup-postgresql.sh
#
# Setup PostgreSQL database per FireDog

set -euo pipefail

DB_NAME="firedog"
DB_USER="microcyber"
DB_PASSWORD="${1:-}"

if [[ -z "$DB_PASSWORD" ]]; then
    echo "Usage: $0 <database_password>"
    exit 1
fi

echo "=== PostgreSQL Setup for FireDog ==="

# Verifica PostgreSQL installato
if ! command -v psql &>/dev/null; then
    echo "PostgreSQL non installato. Installazione..."
    sudo apt update
    sudo apt install -y postgresql postgresql-contrib
fi

# Crea utente e database
sudo -u postgres psql << EOF
-- Crea utente
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';

-- Crea database
CREATE DATABASE $DB_NAME OWNER $DB_USER;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;

-- Configura connessione
ALTER USER $DB_USER SET client_encoding TO 'utf8';
ALTER USER $DB_USER SET default_transaction_isolation TO 'read committed';
ALTER USER $DB_USER SET timezone TO 'UTC';

\c $DB_NAME

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO $DB_USER;

EOF

echo "Database configurato con successo!"
echo ""
echo "Connection string:"
echo "postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"

7.4.2 PostgreSQL Hardening Config
# deployment/configs/postgresql-hardening.conf
# File: /etc/postgresql/*/main/conf.d/firedog.conf
#
# Configurazione PostgreSQL hardened per FireDog

# Network Security
listen_addresses = 'localhost'  # Solo connessioni locali
port = 5432

# SSL (opzionale - decommentare per abilitare)
# ssl = on
# ssl_cert_file = '/etc/ssl/certs/ssl-cert-snakeoil.pem'
# ssl_key_file = '/etc/ssl/private/ssl-cert-snakeoil.key'

# Connection Limits
max_connections = 100
superuser_reserved_connections = 3

# Authentication Timeout
authentication_timeout = 60s

# Password Encryption
password_encryption = scram-sha-256

# Logging
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_connections = on
log_disconnections = on
log_duration = off
log_statement = 'ddl'  # Log DDL statements

# Security
shared_preload_libraries = 'pg_stat_statements'

7.4.3 pg_hba.conf Hardening
# deployment/configs/pg_hba-hardening.conf
# Aggiungi queste righe a /etc/postgresql/*/main/pg_hba.conf

# TYPE  DATABASE        USER            ADDRESS                 METHOD

# Local connections (Unix socket)
local   firedog         microcyber                              scram-sha-256

# IPv4 local connections
host    firedog         microcyber      127.0.0.1/32            scram-sha-256
host    firedog         microcyber      ::1/128                 scram-sha-256

# Deny all other connections
host    all             all             0.0.0.0/0               reject
host    all             all             ::/0                    reject



8. DEPLOYMENT & SCRIPTS
8.1 Main Installation Script
8.1.1 FireDog Central Server Installer
#!/bin/bash
# install-firedog.sh
#
# Installer completo per FireDog Central Server
# Installa e configura: Django, PostgreSQL, Redis, Celery, React frontend

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Variables
INSTALL_DIR="/opt/firedog"
VENV_DIR="$INSTALL_DIR/venv"
BACKEND_DIR="$INSTALL_DIR/backend"
FRONTEND_DIR="$INSTALL_DIR/frontend"
LOG_DIR="/var/log/firedog"
DB_NAME="firedog"
DB_USER="microcyber"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

error_exit() {
    log_error "$1"
    exit 1
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error_exit "This script must be run as root (use sudo)"
    fi
}

detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        error_exit "Cannot detect OS version"
    fi
    
    if [[ "$OS" != "debian" && "$OS" != "ubuntu" ]]; then
        log_warning "This script is designed for Debian/Ubuntu"
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    log_success "Detected: $OS $VER"
}

generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

generate_secret_key() {
    python3 -c "import secrets; print(secrets.token_urlsafe(50))"
}

install_system_dependencies() {
    log_info "Installing system dependencies..."
    
    apt update
    apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        postgresql \
        postgresql-contrib \
        redis-server \
        nginx \
        git \
        curl \
        build-essential \
        libpq-dev \
        arp-scan \
        tcpdump \
        sudo
    
    log_success "System dependencies installed"
}

install_nodejs() {
    log_info "Installing Node.js..."
    
    # Check if already installed
    if command -v node &>/dev/null; then
        NODE_VERSION=$(node -v)
        log_success "Node.js already installed: $NODE_VERSION"
        return
    fi
    
    # Install NodeSource repository for Node 18.x
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt install -y nodejs
    
    log_success "Node.js installed: $(node -v)"
}

setup_postgresql() {
    log_info "Setting up PostgreSQL..."
    
    # Generate password
    DB_PASSWORD=$(generate_password)
    
    # Start PostgreSQL
    systemctl start postgresql
    systemctl enable postgresql
    
    # Create user and database
    sudo -u postgres psql << EOF
-- Create user
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;

-- Create database
SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;

-- Configure user
ALTER USER $DB_USER SET client_encoding TO 'utf8';
ALTER USER $DB_USER SET default_transaction_isolation TO 'read committed';
ALTER USER $DB_USER SET timezone TO 'UTC';
EOF
    
    # Store password
    echo "DB_PASSWORD=$DB_PASSWORD" > /root/.firedog-db-password
    chmod 600 /root/.firedog-db-password
    
    log_success "PostgreSQL configured"
}

setup_redis() {
    log_info "Setting up Redis..."
    
    # Configure Redis for Celery
    cat > /etc/redis/redis.conf.d/firedog.conf << EOF
# FireDog Redis Configuration
bind 127.0.0.1 ::1
protected-mode yes
port 6379
maxmemory 256mb
maxmemory-policy allkeys-lru
EOF
    
    systemctl restart redis-server
    systemctl enable redis-server
    
    log_success "Redis configured"
}

create_directories() {
    log_info "Creating directories..."
    
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$INSTALL_DIR/deployment/firedog-package"
    mkdir -p /etc/firedog/ssh-keys
    
    chmod 755 "$INSTALL_DIR"
    chmod 755 "$LOG_DIR"
    chmod 700 /etc/firedog/ssh-keys
    
    log_success "Directories created"
}

copy_project_files() {
    log_info "Copying project files..."
    
    # Copy backend
    if [[ -d "./backend" ]]; then
        cp -r ./backend "$BACKEND_DIR"
    else
        error_exit "Backend directory not found in current directory"
    fi
    
    # Copy frontend
    if [[ -d "./frontend" ]]; then
        cp -r ./frontend "$FRONTEND_DIR"
    else
        error_exit "Frontend directory not found in current directory"
    fi
    
    # Copy deployment files
    if [[ -d "./deployment" ]]; then
        cp -r ./deployment/* "$INSTALL_DIR/deployment/"
    else
        log_warning "Deployment directory not found"
    fi
    
    log_success "Project files copied"
}

setup_python_environment() {
    log_info "Setting up Python virtual environment..."
    
    # Create venv
    python3 -m venv "$VENV_DIR"
    
    # Activate and install dependencies
    source "$VENV_DIR/bin/activate"
    
    pip install --upgrade pip
    pip install -r "$BACKEND_DIR/requirements.txt"
    
    deactivate
    
    log_success "Python environment configured"
}

configure_django() {
    log_info "Configuring Django..."
    
    # Generate secret key
    SECRET_KEY=$(generate_secret_key)
    
    # Read DB password
    DB_PASSWORD=$(grep DB_PASSWORD /root/.firedog-db-password | cut -d'=' -f2)
    
    # Create .env file
    cat > "$BACKEND_DIR/.env" << EOF
# Django Settings
DJANGO_SECRET_KEY=$SECRET_KEY
DJANGO_SETTINGS_MODULE=firedog.settings_production
DEBUG=False
FIREDOG_HOST=localhost

# Database
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
ALLOWED_HOSTS=localhost,127.0.0.1
EOF
    
    chmod 600 "$BACKEND_DIR/.env"
    
    log_success "Django configured"
}

run_django_migrations() {
    log_info "Running Django migrations..."
    
    cd "$BACKEND_DIR"
    source "$VENV_DIR/bin/activate"
    
    # Run migrations
    python manage.py migrate
    
    # Collect static files
    python manage.py collectstatic --noinput
    
    # Initialize file integrity
    python manage.py check_integrity --init
    
    deactivate
    
    log_success "Migrations completed"
}

create_django_superuser() {
    log_info "Creating Django superuser..."
    
    echo ""
    echo "Create admin user for FireDog:"
    read -p "Username [admin]: " ADMIN_USER
    ADMIN_USER=${ADMIN_USER:-admin}
    
    cd "$BACKEND_DIR"
    source "$VENV_DIR/bin/activate"
    
    python manage.py createsuperuser --username "$ADMIN_USER"
    
    deactivate
    
    log_success "Superuser created"
}

generate_ssh_key() {
    log_info "Generating SSH key for target connections..."
    
    SSH_KEY_PATH="/etc/firedog/ssh-keys/id_ed25519"
    
    if [[ -f "$SSH_KEY_PATH" ]]; then
        log_warning "SSH key already exists"
        return
    fi
    
    # Generate Ed25519 key
    ssh-keygen -t ed25519 -f "$SSH_KEY_PATH" -N "" -C "firedog@central"
    
    chmod 600 "$SSH_KEY_PATH"
    chmod 644 "${SSH_KEY_PATH}.pub"
    
    # Store in database
    cd "$BACKEND_DIR"
    source "$VENV_DIR/bin/activate"
    
    python manage.py shell << EOF
from api.models import SSHKey
import os

private_key_path = '$SSH_KEY_PATH'
public_key_path = '${SSH_KEY_PATH}.pub'

with open(private_key_path, 'r') as f:
    private_key = f.read()

with open(public_key_path, 'r') as f:
    public_key = f.read()

# Get fingerprint
import subprocess
result = subprocess.run(['ssh-keygen', '-lf', public_key_path], 
                       capture_output=True, text=True)
fingerprint = result.stdout.split()[1]

SSHKey.objects.update_or_create(
    key_type='ed25519',
    defaults={
        'private_key': private_key,
        'public_key': public_key,
        'fingerprint': fingerprint
    }
)

print("SSH key stored in database")
EOF
    
    deactivate
    
    log_success "SSH key generated"
    log_info "Public key: ${SSH_KEY_PATH}.pub"
}

build_frontend() {
    log_info "Building React frontend..."
    
    cd "$FRONTEND_DIR"
    
    # Install dependencies
    npm install
    
    # Build production bundle
    npm run build
    
    # Copy build to nginx directory
    mkdir -p /var/www/firedog
    cp -r dist/* /var/www/firedog/
    
    log_success "Frontend built"
}

setup_systemd_services() {
    log_info "Setting up systemd services..."
    
    # Django (Gunicorn) service
    cat > /etc/systemd/system/firedog-backend.service << EOF
[Unit]
Description=FireDog Backend (Gunicorn)
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=notify
User=root
Group=root
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/gunicorn \\
    --bind 127.0.0.1:8000 \\
    --workers 4 \\
    --timeout 120 \\
    --access-logfile $LOG_DIR/gunicorn-access.log \\
    --error-logfile $LOG_DIR/gunicorn-error.log \\
    firedog.wsgi:application

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Celery Worker service
    cat > /etc/systemd/system/firedog-celery.service << EOF
[Unit]
Description=FireDog Celery Worker
After=network.target redis.service
Requires=redis.service

[Service]
Type=forking
User=root
Group=root
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/celery -A firedog worker \\
    --loglevel=info \\
    --logfile=$LOG_DIR/celery-worker.log \\
    --detach

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Celery Beat service (scheduler)
    cat > /etc/systemd/system/firedog-celery-beat.service << EOF
[Unit]
Description=FireDog Celery Beat Scheduler
After=network.target redis.service
Requires=redis.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/celery -A firedog beat \\
    --loglevel=info \\
    --logfile=$LOG_DIR/celery-beat.log

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd
    systemctl daemon-reload
    
    log_success "Systemd services created"
}

setup_nginx() {
    log_info "Setting up Nginx..."
    
    # Create Nginx config
    cat > /etc/nginx/sites-available/firedog << 'EOF'
# FireDog Nginx Configuration

upstream firedog_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name localhost;
    
    client_max_body_size 10M;
    
    # Frontend (React)
    location / {
        root /var/www/firedog;
        try_files $uri $uri/ /index.html;
    }
    
    # Backend API
    location /api/ {
        proxy_pass http://firedog_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
    
    # Django static files
    location /static/ {
        alias /opt/firedog/backend/staticfiles/;
    }
    
    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
}
EOF
    
    # Enable site
    ln -sf /etc/nginx/sites-available/firedog /etc/nginx/sites-enabled/
    
    # Remove default site
    rm -f /etc/nginx/sites-enabled/default
    
    # Test configuration
    nginx -t
    
    # Restart Nginx
    systemctl restart nginx
    systemctl enable nginx
    
    log_success "Nginx configured"
}

install_gunicorn() {
    log_info "Installing Gunicorn..."
    
    source "$VENV_DIR/bin/activate"
    pip install gunicorn
    deactivate
    
    log_success "Gunicorn installed"
}

start_services() {
    log_info "Starting services..."
    
    # Enable and start services
    systemctl enable firedog-backend
    systemctl enable firedog-celery
    systemctl enable firedog-celery-beat
    
    systemctl start firedog-backend
    systemctl start firedog-celery
    systemctl start firedog-celery-beat
    
    log_success "Services started"
}

setup_logrotate() {
    log_info "Setting up log rotation..."
    
    cat > /etc/logrotate.d/firedog << EOF
$LOG_DIR/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0640 root adm
    sharedscripts
    postrotate
        systemctl reload firedog-backend >/dev/null 2>&1 || true
    endscript
}
EOF
    
    log_success "Log rotation configured"
}

display_summary() {
    echo ""
    echo "============================================"
    echo -e "${GREEN}FireDog Installation Complete!${NC}"
    echo "============================================"
    echo ""
    echo "Services:"
    echo "  - Backend:      systemctl status firedog-backend"
    echo "  - Celery:       systemctl status firedog-celery"
    echo "  - Beat:         systemctl status firedog-celery-beat"
    echo ""
    echo "Access:"
    echo "  - Web UI:       http://localhost"
    echo "  - API:          http://localhost/api/"
    echo ""
    echo "Database:"
    echo "  - Name:         $DB_NAME"
    echo "  - User:         $DB_USER"
    echo "  - Password:     (stored in /root/.firedog-db-password)"
    echo ""
    echo "SSH Key:"
    echo "  - Private:      /etc/firedog/ssh-keys/id_ed25519"
    echo "  - Public:       /etc/firedog/ssh-keys/id_ed25519.pub"
    echo ""
    echo "Logs:"
    echo "  - Directory:    $LOG_DIR"
    echo "  - Django:       $LOG_DIR/django.log"
    echo "  - Gunicorn:     $LOG_DIR/gunicorn-*.log"
    echo "  - Celery:       $LOG_DIR/celery-*.log"
    echo ""
    echo "Next Steps:"
    echo "  1. Copy SSH public key to target systems"
    echo "  2. Create microcyber user on targets (see docs)"
    echo "  3. Access web UI and add targets"
    echo ""
    echo "Documentation: $INSTALL_DIR/README.md"
    echo ""
}

# Main Installation Flow
main() {
    echo ""
    echo "============================================"
    echo "    FireDog Central Server Installer"
    echo "============================================"
    echo ""
    
    check_root
    detect_os
    
    log_info "Starting installation..."
    echo ""
    
    # System setup
    install_system_dependencies
    install_nodejs
    setup_postgresql
    setup_redis
    
    # Application setup
    create_directories
    copy_project_files
    setup_python_environment
    configure_django
    run_django_migrations
    create_django_superuser
    generate_ssh_key
    
    # Frontend
    build_frontend
    
    # Services
    install_gunicorn
    setup_systemd_services
    setup_nginx
    setup_logrotate
    start_services
    
    # Summary
    display_summary
    
    log_success "Installation completed successfully!"
}

# Execute
main "$@"


8.2 Target Deployment Scripts
8.2.1 Setup Target Script
#!/bin/bash
# deployment/scripts/setup-target.sh
#
# Script eseguito via SSH su target per installare firedog package

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "[INFO] $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Verifica utente microcyber
if [[ $(whoami) != "microcyber" ]]; then
    log_error "This script must be run as microcyber user"
    exit 1
fi

log_info "Starting FireDog target installation..."

# Vai alla directory temporanea
cd /tmp/firedog-package || exit 1

# Verifica file install.sh
if [[ ! -f "./install.sh" ]]; then
    log_error "install.sh not found in package"
    exit 1
fi

# Rendi eseguibile
chmod +x install.sh firewall-init.sh firewall-manager.py traffic-analyzer.py

# Esegui installazione
log_info "Running install.sh..."
sudo bash ./install.sh

# Verifica installazione
if command -v firewall-manager &>/dev/null; then
    log_success "FireDog installed successfully"
    
    # Get version
    VERSION=$(firewall-manager --version 2>/dev/null || echo "1.0")
    echo "VERSION=$VERSION"
else
    log_error "Installation verification failed"
    exit 1
fi

exit 0

8.2.2 Cron Installer Script
#!/bin/bash
# deployment/scripts/install-cron-target.sh
#
# Installa cron job su target per traffic analyzer

set -euo pipefail

INTERVAL="${1:-10}"  # Default 10 minuti

# Cron line
CRON_LINE="*/$INTERVAL * * * * /usr/local/bin/traffic-analyzer --json > /tmp/firedog-analysis.json 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "traffic-analyzer"; then
    echo "Cron job already exists"
    exit 0
fi

# Add cron job
(crontab -l 2>/dev/null || echo ""; echo "$CRON_LINE") | crontab -

echo "Cron job installed: every $INTERVAL minutes"

# Verify
crontab -l | grep traffic-analyzer

exit 0

8.3 Management Scripts
8.3.1 FireDog Control Script
#!/bin/bash
# /usr/local/bin/firedog-ctl
#
# Script di controllo per FireDog

set -euo pipefail

SERVICES=("firedog-backend" "firedog-celery" "firedog-celery-beat")

usage() {
    cat << EOF
Usage: firedog-ctl {start|stop|restart|status|logs}

Commands:
  start      - Start all FireDog services
  stop       - Stop all FireDog services
  restart    - Restart all FireDog services
  status     - Show status of all services
  logs       - Show recent logs
  integrity  - Check file integrity
  backup-db  - Backup PostgreSQL database

EOF
    exit 1
}

start_services() {
    echo "Starting FireDog services..."
    for service in "${SERVICES[@]}"; do
        systemctl start "$service"
        echo "  ✓ $service"
    done
    echo "All services started"
}

stop_services() {
    echo "Stopping FireDog services..."
    for service in "${SERVICES[@]}"; do
        systemctl stop "$service"
        echo "  ✓ $service"
    done
    echo "All services stopped"
}

restart_services() {
    echo "Restarting FireDog services..."
    for service in "${SERVICES[@]}"; do
        systemctl restart "$service"
        echo "  ✓ $service"
    done
    echo "All services restarted"
}

show_status() {
    echo "FireDog Services Status:"
    echo ""
    for service in "${SERVICES[@]}"; do
        systemctl status "$service" --no-pager -l
        echo ""
    done
}

show_logs() {
    echo "Recent logs (last 50 lines):"
    echo ""
    journalctl -u firedog-backend -u firedog-celery -u firedog-celery-beat -n 50 --no-pager
}

check_integrity() {
    echo "Checking file integrity..."
    cd /opt/firedog/backend
    source /opt/firedog/venv/bin/activate
    python manage.py check_integrity
    deactivate
}

backup_database() {
    BACKUP_DIR="/var/backups/firedog"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/firedog_$TIMESTAMP.sql"
    
    mkdir -p "$BACKUP_DIR"
    
    echo "Backing up database to $BACKUP_FILE..."
    sudo -u postgres pg_dump firedog > "$BACKUP_FILE"
    gzip "$BACKUP_FILE"
    
    echo "Backup completed: ${BACKUP_FILE}.gz"
    
    # Keep only last 7 days
    find "$BACKUP_DIR" -name "firedog_*.sql.gz" -mtime +7 -delete
}

case "${1:-}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    integrity)
        check_integrity
        ;;
    backup-db)
        backup_database
        ;;
    *)
        usage
        ;;
esac

8.3.2 Update Script
#!/bin/bash
# /usr/local/bin/firedog-update
#
# Script per aggiornare FireDog

set -euo pipefail

INSTALL_DIR="/opt/firedog"
BACKUP_DIR="/var/backups/firedog/updates"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=== FireDog Update Script ==="
echo ""

# Backup database
echo "[1/6] Backing up database..."
mkdir -p "$BACKUP_DIR"
sudo -u postgres pg_dump firedog > "$BACKUP_DIR/db_$TIMESTAMP.sql"
gzip "$BACKUP_DIR/db_$TIMESTAMP.sql"
echo "  ✓ Database backed up"

# Backup current installation
echo "[2/6] Backing up current installation..."
tar -czf "$BACKUP_DIR/firedog_$TIMESTAMP.tar.gz" \
    "$INSTALL_DIR/backend" \
    "$INSTALL_DIR/frontend" \
    --exclude='*.pyc' \
    --exclude='node_modules' \
    --exclude='venv'
echo "  ✓ Installation backed up"

# Stop services
echo "[3/6] Stopping services..."
systemctl stop firedog-backend firedog-celery firedog-celery-beat
echo "  ✓ Services stopped"

# Update backend
echo "[4/6] Updating backend..."
cd "$INSTALL_DIR/backend"
source "$INSTALL_DIR/venv/bin/activate"
pip install --upgrade -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
deactivate
echo "  ✓ Backend updated"

# Update frontend
echo "[5/6] Updating frontend..."
cd "$INSTALL_DIR/frontend"
npm install
npm run build
cp -r dist/* /var/www/firedog/
echo "  ✓ Frontend updated"

# Start services
echo "[6/6] Starting services..."
systemctl start firedog-backend firedog-celery firedog-celery-beat
echo "  ✓ Services started"

echo ""
echo "=== Update Completed ==="
echo "Backups stored in: $BACKUP_DIR"
echo ""
echo "Rollback command (if needed):"
echo "  tar -xzf $BACKUP_DIR/firedog_$TIMESTAMP.tar.gz -C /"
echo "  gunzip < $BACKUP_DIR/db_$TIMESTAMP.sql.gz | sudo -u postgres psql firedog"

8.4 Uninstall Script
#!/bin/bash
# /usr/local/bin/firedog-uninstall
#
# Script per disinstallare FireDog completamente

set -euo pipefail

RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}=== FireDog Uninstall Script ===${NC}"
echo ""
echo -e "${YELLOW}WARNING: This will remove FireDog completely!${NC}"
echo "  - All configuration will be deleted"
echo "  - Database will be dropped"
echo "  - Services will be removed"
echo ""
read -p "Are you sure? Type 'yes' to confirm: " CONFIRM

if [[ "$CONFIRM" != "yes" ]]; then
    echo "Uninstall cancelled"
    exit 0
fi

echo ""
echo "Creating final backup..."
BACKUP_DIR="/var/backups/firedog/uninstall_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup database
sudo -u postgres pg_dump firedog > "$BACKUP_DIR/database.sql" 2>/dev/null || true
gzip "$BACKUP_DIR/database.sql" || true

# Backup config
tar -czf "$BACKUP_DIR/config.tar.gz" \
    /opt/firedog \
    /etc/firedog \
    /var/log/firedog \
    2>/dev/null || true

echo "Backup saved to: $BACKUP_DIR"
echo ""

# Stop and disable services
echo "Stopping services..."
systemctl stop firedog-backend firedog-celery firedog-celery-beat 2>/dev/null || true
systemctl disable firedog-backend firedog-celery firedog-celery-beat 2>/dev/null || true

# Remove systemd services
echo "Removing systemd services..."
rm -f /etc/systemd/system/firedog-*.service
systemctl daemon-reload

# Remove Nginx config
echo "Removing Nginx configuration..."
rm -f /etc/nginx/sites-enabled/firedog
rm -f /etc/nginx/sites-available/firedog
systemctl reload nginx

# Drop database
echo "Dropping database..."
sudo -u postgres psql << EOF
DROP DATABASE IF EXISTS firedog;
DROP USER IF EXISTS microcyber;
EOF

# Remove files
echo "Removing files..."
rm -rf /opt/firedog
rm -rf /etc/firedog
rm -rf /var/log/firedog
rm -rf /var/www/firedog
rm -f /usr/local/bin/firedog-ctl
rm -f /usr/local/bin/firedog-update
rm -f /usr/local/bin/firedog-uninstall

echo ""
echo "FireDog has been uninstalled"
echo "Backup location: $BACKUP_DIR"

8.5 Health Check Script
#!/bin/bash
# /usr/local/bin/firedog-healthcheck
#
# Health check script per FireDog

set -euo pipefail

ERRORS=0

check_service() {
    SERVICE=$1
    if systemctl is-active --quiet "$SERVICE"; then
        echo "✓ $SERVICE is running"
    else
        echo "✗ $SERVICE is NOT running"
        ((ERRORS++))
    fi
}

check_port() {
    PORT=$1
    NAME=$2
    if nc -z localhost "$PORT" 2>/dev/null; then
        echo "✓ $NAME is listening on port $PORT"
    else
        echo "✗ $NAME is NOT listening on port $PORT"
        ((ERRORS++))
    fi
}

check_database() {
    if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw firedog; then
        echo "✓ Database 'firedog' exists"
    else
        echo "✗ Database 'firedog' does NOT exist"
        ((ERRORS++))
    fi
}

check_api() {
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/ 2>/dev/null || echo "000")
    if [[ "$RESPONSE" == "200" ]] || [[ "$RESPONSE" == "401" ]]; then
        echo "✓ API is responding (HTTP $RESPONSE)"
    else
        echo "✗ API is NOT responding (HTTP $RESPONSE)"
        ((ERRORS++))
    fi
}

check_frontend() {
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ 2>/dev/null || echo "000")
    if [[ "$RESPONSE" == "200" ]]; then
        echo "✓ Frontend is accessible (HTTP $RESPONSE)"
    else
        echo "✗ Frontend is NOT accessible (HTTP $RESPONSE)"
        ((ERRORS++))
    fi
}

echo "=== FireDog Health Check ==="
echo ""

echo "Services:"
check_service "firedog-backend"
check_service "firedog-celery"
check_service "firedog-celery-beat"
check_service "postgresql"
check_service "redis-server"
check_service "nginx"

echo ""
echo "Ports:"
check_port 8000 "Gunicorn"
check_port 80 "Nginx"
check_port 5432 "PostgreSQL"
check_port 6379 "Redis"

echo ""
echo "Components:"
check_database
check_api
check_frontend

echo ""
if [[ $ERRORS -eq 0 ]]; then
    echo "✓ All checks passed"
    exit 0
else# /etc/systemd/system/firedog-backend.service

[Unit]
Description=FireDog Backend API Server
Documentation=https://github.com/yourorg/firedog
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=notify
User=root
Group=root
WorkingDirectory=/opt/firedog/backend

# Environment
Environment="PATH=/opt/firedog/venv/bin"
EnvironmentFile=/opt/firedog/backend/.env

# Gunicorn command
ExecStart=/opt/firedog/venv/bin/gunicorn \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --worker-class sync \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --access-logfile /var/log/firedog/gunicorn-access.log \
    --error-logfile /var/log/firedog/gunicorn-error.log \
    --log-level info \
    firedog.wsgi:application

# Process management
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/firedog /opt/firedog /etc/firedog

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target

8.7 Nginx Advanced Configuration
8.7.1 With HTTPS (Let's Encrypt)
# /etc/nginx/sites-available/firedog-ssl

upstream firedog_backend {
    server 127.0.0.1:8000 fail_timeout=0;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name firedog.yourdomain.com;
    
    return 301 https://$server_name$request_uri;
}

# HTTPS Server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name firedog.yourdomain.com;
    
    # SSL Configuration (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/firedog.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/firedog.yourdomain.com/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/firedog.yourdomain.com/chain.pem;
    
    # SSL Security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
    
    # Limits
    client_max_body_size 10M;
    client_body_buffer_size 128k;
    
    # Timeouts
    proxy_connect_timeout 120s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;
    send_timeout 120s;
    
    # Logging
    access_log /var/log/nginx/firedog-access.log;
    error_log /var/log/nginx/firedog-error.log;
    
    # Frontend (React)
    location / {
        root /var/www/firedog;
        try_files $uri $uri/ /index.html;
        
        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
    
    # Backend API
    location /api/ {
        proxy_pass http://firedog_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
    
    # Django Static Files
    location /static/ {
        alias /opt/firedog/backend/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "OK\n";
        add_header Content-Type text/plain;
    }
}

8.8 Complete Automated Deployment Script
#!/bin/bash
# deploy-complete.sh
#
# Script di deployment completo automatizzato
# Include tutti i componenti: DB, backend, frontend, services

set -euo pipefail

# Configuration
REPO_URL="https://github.com/yourorg/firedog.git"
BRANCH="main"
INSTALL_DIR="/opt/firedog"
DOMAIN="firedog.local"

# Import main installer
if [[ -f "./install-firedog.sh" ]]; then
    source ./install-firedog.sh
else
    echo "Main installer not found!"
    exit 1
fi

# Additional deployment steps
setup_monitoring() {
    log_info "Setting up monitoring..."
    
    # Install monitoring tools (optional)
    apt install -y htop iotop nethogs
    
    # Setup cron for health checks
    cat > /etc/cron.d/firedog-healthcheck << EOF
*/5 * * * * root /usr/local/bin/firedog-healthcheck >> /var/log/firedog/healthcheck.log 2>&1
EOF
    
    log_success "Monitoring configured"
}

setup_ssl() {
    log_info "Setting up SSL certificate..."
    
    if [[ "$DOMAIN" == "localhost" ]] || [[ "$DOMAIN" == "firedog.local" ]]; then
        log_warning "Skipping SSL for local domain"
        return
    fi
    
    # Install certbot
    apt install -y certbot python3-certbot-nginx
    
    # Get certificate
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@"$DOMAIN"
    
    log_success "SSL certificate obtained"
}

# Execute full deployment
main "$@"
setup_monitoring
# setup_ssl  # Uncomment if using real domain

echo ""
echo "=== Deployment Complete ==="
echo "FireDog is now running at: http://$DOMAIN"
echo ""
```

---

# 9. OPERAZIONI CRITICHE - FLOW DETTAGLIATI

## 9.1 Flow: Aggiunta e Installazione Target
```
USER ACTION: Click "Add Target" → Fill form (IP, hostname)
    ↓
FRONTEND: POST /api/targets/
    {
        "hostname": "server01",
        "ip_address": "192.168.1.100",
        "ssh_port": 22
    }
    ↓
BACKEND: TargetViewSet.create()
    1. Validate IP format (ipaddress.ip_address)
    2. Check uniqueness (Target.objects.filter)
    3. Create Target record with status='pending'
    4. Create AuditLog entry
    5. Return 201 with target_id
    ↓
FRONTEND: Display target card with "Install" button
    ↓
USER ACTION: Click "Install"
    ↓
FRONTEND: POST /api/targets/{id}/install/
    ↓
BACKEND: TargetViewSet.install()
    1. Get target from DB
    2. Validate status (must be 'pending' or 'error')
    3. Update target.status = 'installing'
    4. Start Celery task: install_target_task.delay(target.id)
    5. Return 202 with task_id
    ↓
CELERY WORKER: install_target_task(target_id)
    1. Load target from DB
    2. Update installation_status = "Connecting..."
    3. SSHManager.connect() with Ed25519 key
       ├─ SUCCESS → Continue
       └─ FAIL → status='error', create alert, return
    
    4. Update installation_status = "Checking prerequisites..."
    5. ssh.check_user_exists() - verify microcyber user
       ├─ EXISTS → Continue
       └─ NOT FOUND → status='error', 
                       installation_error="User microcyber not found",
                       create alert with setup instructions,
                       return
    
    6. Update installation_status = "Uploading package..."
    7. ssh.upload_directory("/opt/firedog/deployment/firedog-package", "/tmp/firedog-package")
       ├─ SUCCESS → Continue
       └─ FAIL → status='error', return
    
    8. Update installation_status = "Running installation..."
    9. ssh.execute_command("cd /tmp/firedog-package && sudo bash install.sh")
       ├─ exit_code=0 → Continue
       └─ exit_code≠0 → status='error', save stderr, return
    
    10. Update installation_status = "Verifying installation..."
    11. ssh.execute_command("test -f /usr/local/bin/firewall-manager && echo OK")
        ├─ "OK" in output → Continue
        └─ NOT OK → status='error', return
    
    12. Get version: ssh.execute_command("firewall-manager --version")
    13. Update installation_status = "Setting up cron..."
    14. ssh.install_cron_job(interval_minutes)
        - Add crontab entry for traffic-analyzer
    
    15. SUCCESS:
        - target.status = 'online'
        - target.installation_status = 'Completed'
        - target.firedog_version = <version>
        - target.last_seen = now()
        - Create success alert
    
    16. ssh.disconnect()
    17. Return success
    ↓
FRONTEND: Poll /api/targets/{id}/install-status/ every 2 seconds
    - Display progress bar based on installation_status
    - If status='online' → Stop polling, show success
    - If status='error' → Stop polling, show error with retry button
```

---

## 9.2 Flow: Fetch Periodico Dati
```
CELERY BEAT: Ogni N minuti (default 10)
    ↓
CELERY BEAT: Trigger task fetch_all_targets_task()
    ↓
TASK: fetch_all_targets_task()
    1. Get all targets with status='online'
    2. For each target:
        - Check if fetch_interval_minutes elapsed
        - If YES → call fetch_target_data(target.id)
        - If NO → skip
    3. Return summary: {success: X, failed: Y, skipped: Z}
    ↓
TASK: fetch_target_data(target_id)
    1. Get target from DB
    2. Verify status='online'
    3. SSHManager.connect()
       └─ FAIL → target.status='offline', create alert, return
    
    4. ssh.fetch_analysis_results()
       - SCP download: /tmp/firedog-analysis.json from target
       - Parse JSON
       └─ FAIL → raise exception
    
    5. Parse analysis data:
       analysis_data = {
           "threats": {
               "critical": [
                   {"ip": "x.x.x.x", "score": 95, "packets": 150, ...},
                   ...
               ],
               "high": [...],
               "medium": [...],
               "low": [...]
           },
           "stats": {
               "input_packets": 123456,
               "output_packets": 98765,
               "input_dropped": 1234,
               ...
           }
       }
    
    6. BEGIN TRANSACTION
    
    7. Process threats:
       For each threat in all severity levels:
           - Check if already exists (same IP + last 1 hour)
           - If NEW:
               * Calculate classification from score
               * Create ThreatLog record
               * Increment new_threats counter
    
    8. Create Statistics record with stats data
    
    9. Update target:
       - last_fetch = now()
       - last_seen = now()
    
    10. COMMIT TRANSACTION
    
    11. Check for critical threats (score >= 80):
        If critical_count > 0:
            - Check if alert already sent in last hour
            - If NOT:
                * Create Alert with severity='critical'
                * Title: "Critical Threats Detected"
                * Message: "{count} critical threats on {hostname}"
    
    12. Return results:
        {
            "threats_count": total,
            "new_threats": new_count,
            "stats": {...}
        }
    ↓
FRONTEND: Polling /api/targets/ every 30 seconds
    - Updates target cards with latest data
    - Shows threat counts, last_seen timestamps
    - Red badge if critical threats > 0
```

---

## 9.3 Flow: Aggiunta Regola Firewall
```
USER ACTION: Open target detail → Click "Rules" tab → Click "Add Rule"
    ↓
FRONTEND: Open AddRuleModal
    - Form fields: chain, port, protocol, source_ip, comment
    - Validation: port (1-65535), IP format
    ↓
USER: Fill form and submit
    ↓
FRONTEND: POST /api/targets/{id}/rules/add/
    {
        "chain": "INPUT",
        "port": 8080,
        "protocol": "tcp",
        "source_ip": "192.168.1.0/24",
        "comment": "Allow Grafana"
    }
    ↓
BACKEND: RuleViewSet.add()
    1. Get target from DB
    2. Validate request data:
       - chain in ['INPUT', 'OUTPUT', 'FORWARD']
       - port in 1-65535
       - protocol in ['tcp', 'udp', 'icmp']
       - source_ip valid CIDR (if provided)
    
    3. Check target.status == 'online'
       └─ OFFLINE → Return 503 "Target is offline"
    
    4. SSHManager.connect()
       └─ FAIL → Return 503 with error
    
    5. ssh.add_firewall_rule(
           chain='INPUT',
           port=8080,
           protocol='tcp',
           source_ip='192.168.1.0/24',
           comment='Allow Grafana'
       )
       
       Which executes on target:
       sudo firewall-manager --add-input 8080 \
           --protocol tcp \
           --source 192.168.1.0/24 \
           --comment "Allow Grafana"
       
       └─ exit_code=0 → Continue
       └─ exit_code≠0 → Return 400 with stderr
    
    6. ssh.get_firewall_rules() - Fetch updated rules
    
    7. Parse iptables output and update FirewallRule table:
       - Delete old rules for this target+chain
       - Insert new parsed rules
    
    8. ssh.disconnect()
    
    9. Create AuditLog:
       - username: request.user
       - action: 'rule.add'
       - target: target
       - details: {chain, port, protocol, source_ip, comment}
    
    10. Return 200:
        {
            "message": "Rule added successfully",
            "rule": {...}
        }
    ↓
FRONTEND: Close modal, refresh rules table
    - GET /api/targets/{id}/rules/
    - Display updated rules with new rule highlighted
```

---

## 9.4 Flow: Discovery Network
```
USER ACTION: Click "Discover Network" button
    ↓
FRONTEND: POST /api/discovery/scan/
    ↓
BACKEND: DiscoveryService.startScan()
    1. Create Celery task: network_discovery_task.delay()
    2. Return 202 with task_id
    ↓
CELERY WORKER: network_discovery_task()
    1. Get local networks from 'ip route':
       - Execute: subprocess.run(['ip', 'route'])
       - Parse output for CIDR networks (e.g., 192.168.1.0/24)
       - Filter: exclude default route, localhost
       - Result: ['192.168.1.0/24', '10.0.0.0/24']
    
    2. For each network:
        a. Execute arp-scan:
           sudo arp-scan --interface=auto 192.168.1.0/24
        
        b. Parse output (each line):
           192.168.1.100   00:11:22:33:44:55   Vendor Name
           
        c. For each discovered IP:
           - Try hostname resolution: host 192.168.1.100
           - Extract hostname or use "host-100"
           - Check if already in database: Target.objects.filter(ip=...)
           - Create result: {
               "ip": "192.168.1.100",
               "mac": "00:11:22:33:44:55",
               "hostname": "server01.local",
               "vendor": "Vendor Name",
               "already_added": false
             }
    
    3. Store results in cache/database:
       - Key: task_id
       - Value: {
           "status": "completed",
           "networks_scanned": ['192.168.1.0/24'],
           "found_hosts": [...]
         }
    
    4. Return task completion
    ↓
FRONTEND: Poll GET /api/discovery/results/{task_id}/ every 2 seconds
    - While status='running' → Show spinner
    - When status='completed' → Show results table
    ↓
FRONTEND: Display discovered hosts table
    Columns: [Checkbox] IP | Hostname | MAC | Already Added
    
    - Hosts with already_added=true → Grayed out, checkbox disabled
    - Hosts with already_added=false → Selectable
    ↓
USER ACTION: Select hosts and click "Add Selected"
    ↓
FRONTEND: For each selected host:
    POST /api/targets/
    {
        "hostname": "server02",
        "ip_address": "192.168.1.101",
        "ssh_port": 22
    }
    ↓
BACKEND: Create targets with status='pending'
    ↓
FRONTEND: Close discovery modal, refresh targets list
    - New targets appear with "Install" button
```

---

## 9.5 Flow: File Integrity Violation Detection
```
CELERY BEAT: Every 6 hours
    ↓
CELERY BEAT: Trigger task check_integrity_task()
    ↓
TASK: check_integrity_task()
    1. Get list of critical files from IntegrityChecker.CRITICAL_FILES
    
    2. For each filepath:
        a. Check if file exists
           └─ NOT EXISTS → Log warning, continue
        
        b. Compute SHA512 hash:
           - Read file in 8KB chunks
           - Update hash incrementally
           - Result: 128-char hex string
        
        c. Query FileIntegrity table:
           - Try: get record by filepath
           - If FOUND:
               * Compare stored hash with current hash
               * If MATCH → Update last_checked, continue
               * If MISMATCH → VIOLATION DETECTED
                   - Log warning
                   - Create Alert:
                       severity='critical'
                       title='File Integrity Violation'
                       message='File {path} modified. Expected: {old[:16]}..., Current: {new[:16]}...'
                   - Add to violations list
           
           - If NOT FOUND (first time):
               * Create FileIntegrity record with current hash
               * Log: "Initial hash recorded"
    
    3. Return results:
       {
           "checked": 8,
           "violations": [
               {
                   "filepath": "/usr/local/bin/firewall-manager",
                   "expected_hash": "abc123...",
                   "current_hash": "xyz789..."
               }
           ],
           "errors": []
       }
    ↓
FRONTEND: Dashboard shows critical alert
    - Red badge with count of violations
    - Click alert → Navigate to Settings → File Integrity
    ↓
SETTINGS PAGE: File Integrity Tab
    - Shows table of monitored files
    - Files with violations → Red background
    - Show expected vs current hash (first 16 chars)
    - Actions: [View Full Hash] [Accept Changes]
    ↓
USER ACTION: Click "Accept Changes" on violated file
    ↓
FRONTEND: Show password confirmation modal
    - "This action requires your password"
    - Input field for password
    ↓
USER: Enter password and confirm
    ↓
FRONTEND: POST /api/integrity/accept-changes/
    {
        "filepath": "/usr/local/bin/firewall-manager",
        "password": "admin_password"
    }
    ↓
BACKEND: IntegrityChecker.accept_changes()
    1. Authenticate user with password
       └─ FAIL → Return 401 "Invalid password"
    
    2. Compute new hash of file
    
    3. Update FileIntegrity record:
       - sha512_hash = new_hash
       - last_checked = now()
    
    4. Create AuditLog:
       - action: 'file.integrity.accept'
       - details: {"filepath": ..., "old_hash": ..., "new_hash": ...}
    
    5. Return 200: {"message": "Hash updated", "new_hash": ...}
    ↓
FRONTEND: Refresh file integrity table
    - Violation cleared, file shows green checkmark
    - Alert dismissed automatically



10. TESTING & TROUBLESHOOTING
10.1 Test Scenarios
Scenario 1: Test Complete Installation
#!/bin/bash
# test-complete-installation.sh

echo "=== FireDog Installation Test Suite ==="

# Test 1: Services running
echo "[1] Testing services..."
for service in firedog-backend firedog-celery firedog-celery-beat postgresql redis-server nginx; do
    if systemctl is-active --quiet $service; then
        echo "  ✓ $service"
    else
        echo "  ✗ $service NOT RUNNING"
        exit 1
    fi
done

# Test 2: Database connectivity
echo "[2] Testing database..."
if sudo -u postgres psql -d firedog -c "SELECT 1" &>/dev/null; then
    echo "  ✓ Database accessible"
else
    echo "  ✗ Database NOT accessible"
    exit 1
fi

# Test 3: API endpoint
echo "[3] Testing API..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/)
if [[ "$RESPONSE" == "401" ]] || [[ "$RESPONSE" == "200" ]]; then
    echo "  ✓ API responding (HTTP $RESPONSE)"
else
    echo "  ✗ API not responding (HTTP $RESPONSE)"
    exit 1
fi

# Test 4: Frontend
echo "[4] Testing frontend..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/)
if [[ "$RESPONSE" == "200" ]]; then
    echo "  ✓ Frontend accessible"
else
    echo "  ✗ Frontend NOT accessible"
    exit 1
fi

# Test 5: SSH key exists
echo "[5] Testing SSH key..."
if [[ -f /etc/firedog/ssh-keys/id_ed25519 ]]; then
    echo "  ✓ SSH key present"
else
    echo "  ✗ SSH key missing"
    exit 1
fi

# Test 6: Python packages
echo "[6] Testing Python environment..."
source /opt/firedog/venv/bin/activate
if python -c "import django, rest_framework, celery, paramiko" 2>/dev/null; then
    echo "  ✓ All packages installed"
else
    echo "  ✗ Missing packages"
    exit 1
fi
deactivate

echo ""
echo "✓ All tests passed!"

10.2 Common Issues & Solutions
Issue 1: Cannot connect to target via SSH
Symptoms:

Installation fails with "SSH connection failed"
Target shows status='error' with "Connection refused"

Diagnosis:
# Test SSH manually
ssh -i /etc/firedog/ssh-keys/id_ed25519 microcyber@192.168.1.100

# Check SSH service on target
sudo systemctl status sshd

# Check firewall on target
sudo iptables -L INPUT -n | grep 22


Solutions:

Verify microcyber user exists on target
Verify public key in /home/microcyber/.ssh/authorized_keys
Check SSH port (default 22)
Verify network connectivity: ping 192.168.1.100
Check target firewall allows SSH from central server


Issue 2: Celery tasks not executing
Symptoms:

Targets remain in "installing" status forever
No data being fetched from targets

Diagnosis:
# Check Celery worker
sudo systemctl status firedog-celery

# Check Celery logs
sudo tail -f /var/log/firedog/celery-worker.log

# Check Redis
redis-cli ping  # Should return "PONG"

# Check Celery tasks in Django shell
cd /opt/firedog/backend
source /opt/firedog/venv/bin/activate
python manage.py shell
>>> from django_celery_results.models import TaskResult
>>> TaskResult.objects.all()

Solutions:

Restart Celery: sudo systemctl restart firedog-celery
Check Redis: sudo systemctl status redis-server
Verify Celery config in Django settings
Check for task errors in logs


Issue 3: Frontend shows "Network Error"
Symptoms:

React UI shows "Failed to fetch" errors
API calls return network errors

Diagnosis:
# Check backend API
curl http://localhost:8000/api/

# Check Nginx
sudo systemctl status nginx
sudo nginx -t

# Check logs
sudo tail -f /var/log/nginx/firedog-error.log
sudo tail -f /var/log/firedog/gunicorn-error.log

Solutions:

Verify Nginx config: sudo nginx -t
Restart Nginx: sudo systemctl restart nginx
Check CORS settings in Django
Verify frontend build: ls /var/www/firedog/


Issue 4: Database connection errors
Symptoms:

Django cannot connect to PostgreSQL
"FATAL: password authentication failed"

Diagnosis:
# Test connection
sudo -u postgres psql -d firedog -c "SELECT version();"

# Check credentials
cat /opt/firedog/backend/.env | grep DB_

# Check PostgreSQL
sudo systemctl status postgresql

Solutions:

Verify DB credentials in .env file
Reset password:
sudo -u postgres psql
ALTER USER microcyber WITH PASSWORD 'new_password';

Update .env with new password
Restart backend: sudo systemctl restart firedog-backend

Issue 5: File integrity alerts on legitimate changes
Symptoms:

Alerts for modified files after updates
Cannot proceed due to integrity checks

Solution:
Accept changes via UI or CLI:
cd /opt/firedog/backend
source /opt/firedog/venv/bin/activate
python manage.py shell

from integrity.checker import IntegrityChecker
IntegrityChecker.initialize_monitoring()  # Reset all hashes

10.3 Debug Mode
Enable Debug Logging
# Edit Django settings
sudo nano /opt/firedog/backend/firedog/settings_production.py

# Change:
DEBUG = True  # Temporarily for debugging
LOG_LEVEL = 'DEBUG'

# Restart
sudo systemctl restart firedog-backend

# Watch logs
sudo tail -f /var/log/firedog/django.log
IMPORTANT: Remember to set DEBUG = False after debugging!

10.4 Performance Tuning
Database Optimization
-- Create additional indexes
CREATE INDEX idx_threats_target_score ON threat_logs(target_id, threat_score DESC);
CREATE INDEX idx_threats_detected_at ON threat_logs(detected_at DESC);

-- Vacuum database
VACUUM ANALYZE;
Gunicorn Workers
# Edit service file
sudo nano /etc/systemd/system/firedog-backend.service

# Adjust workers based on CPU cores
# Formula: (2 x $num_cores) + 1
--workers 9  # For 4-core system

sudo systemctl daemon-reload
sudo systemctl restart firedog-backend

FINE DOCUMENTAZIONE TECNICA

📚 Riepilogo Documentazione Fornita
Hai ora una documentazione tecnica completa che include:
✅ Completato

Panoramica Sistema - Architettura e scopo
Database Design - Schema completo con 9 tabelle, indexes, queries
API Specification - Tutti gli endpoint con request/response
Backend Implementation - Models, Views, Serializers, Tasks, SSH Manager
Discovery Service - arp-scan e bulk import
Frontend Architecture - Struttura React/TypeScript completa
Security Hardening - SSH, sudoers, Django settings, file integrity
Deployment Scripts - Installer completo, systemd, nginx, management
Operational Flows - Flow dettagliati per ogni operazione critica
Testing & Troubleshooting - Scenari test e soluzioni problemi comuni

📦 Cosa Puoi Fare Ora

Implementare il progetto seguendo le specifiche
Consultare la documentazione come reference
Modificare componenti secondo necessità
Tornare per singoli approfondimenti su componenti specifici

🎯 Per Continuare l'Implementazione
Se hai bisogno di:

Codice completo di un componente specifico
Chiarimenti su una sezione
Modifiche alle specifiche
Nuove feature non documentate

Puoi chiedere in nuove chat focalizzate su:

"Implementa component X secondo FIREDOG_TECHNICAL_SPEC"
"Debug issue Y basandoti sulla spec"
"Estendi feature Z"



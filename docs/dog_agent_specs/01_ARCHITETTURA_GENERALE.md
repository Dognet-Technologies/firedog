# 01 - ARCHITETTURA GENERALE

## 1.1 Overview Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                    FIREDOG ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐          ┌──────────────────┐
│   Web Frontend   │          │   Admin Panel    │
│   (React TS)     │◄────────►│   (React TS)     │
└────────┬─────────┘          └────────┬─────────┘
         │                              │
         │ HTTPS REST API              │
         │ (JWT Auth)                  │
         │                              │
┌────────▼──────────────────────────────▼─────────┐
│         Django Backend (Port 8000)              │
│  ┌──────────────────────────────────────────┐  │
│  │  Django REST Framework + Django Channels │  │
│  └──────────────────────────────────────────┘  │
│                                                  │
│  Apps:                                          │
│  ├─ targets/      (Target management)          │
│  ├─ rules/        (Firewall rules)             │
│  ├─ threats/      (Threat detection)           │
│  ├─ dashboards/   (Dashboard widgets)          │
│  ├─ integrity/    (File integrity)             │
│  ├─ discovery/    (Network discovery)          │
│  ├─ audit/        (Audit logging)              │
│  └─ agent_manager/ (NEW - Agent management)    │
│                                                  │
│  ┌──────────────┐      ┌────────────────────┐  │
│  │  PostgreSQL  │      │  Redis (Celery +   │  │
│  │  Database    │      │  Django Channels)  │  │
│  └──────────────┘      └────────────────────┘  │
└──────────────────┬───────────────────┬──────────┘
                   │                   │
                   │ WSS (WebSocket    │ Celery Tasks
                   │  Secure)          │
                   │                   │
┌──────────────────▼───────────────────▼──────────┐
│              Nginx Reverse Proxy                │
│              (SSL Termination)                  │
└──────────────────┬──────────────────────────────┘
                   │
                   │ Internet / VPN
                   │
┌──────────────────▼──────────────────────────────┐
│              Target Machine                     │
│  ┌──────────────────────────────────────────┐  │
│  │         Dog Agent (Python Service)       │  │
│  │         systemd: dog-agent.service       │  │
│  └──────────────────────────────────────────┘  │
│                                                  │
│  ├─ Firewall Manager (iptables wrapper)        │
│  ├─ Threat Detector (local analysis)           │
│  ├─ Log Collector (ulogd2 integration)         │
│  └─ File Integrity Monitor (SHA512)            │
└──────────────────────────────────────────────────┘
```

## 1.2 Flusso Pairing

```
USER (Web UI)          SERVER (Django)           AGENT (Target)
     │                      │                         │
     │ 1. Crea Target       │                         │
     │ (ip, hostname, mac)  │                         │
     ├──────────────────────►                         │
     │                      │ Genera identity_hash    │
     │                      │ status='unpaired'       │
     │                      │                         │
     │ 2. Click             │                         │
     │ "Collega Agent"      │                         │
     ├──────────────────────►                         │
     │                      │ Crea PairingSession     │
     │                      │ status='waiting'        │
     │                      │ expires_at=now()+3min   │
     │                      │                         │
     │◄─────────────────────┤                         │
     │ "In attesa..."       │                         │
     │ Progress: Fase 1     │                         │
     │                      │                         │
     │                      │◄────────────────────────┤
     │                      │ 3. WebSocket Connect    │
     │                      │ {"type": "pair_request" │
     │                      │  "api_key": "xxx",      │
     │                      │  "ip": "192.168.0.15",  │
     │                      │  "hostname": "web01",   │
     │                      │  "mac": "AA:BB:..."}    │
     │                      │                         │
     │                      │ 4. Verify API Key       │
     │                      │ FASE 1 ✓                │
     │◄─────────────────────┤                         │
     │ Progress: Fase 1 ✓   │                         │
     │                      │                         │
     │                      │ 5. Compute Hash         │
     │                      │ identity_text =         │
     │                      │ "192.168.0.15web01AA:BB"│
     │                      │ hash = SHA512(text)     │
     │                      │                         │
     │                      │ 6. Compare with Target  │
     │                      │ FASE 2 ✓                │
     │◄─────────────────────┤                         │
     │ Progress: Fase 2 ✓   │                         │
     │ "Pairing Success!"   │                         │
     │                      │                         │
     │                      │ 7. Update Target        │
     │                      │ status='online'         │
     │                      │ Create AgentConnection  │
     │                      │                         │
     │                      ├─────────────────────────►
     │                      │ {"type":"pair_success", │
     │                      │  "target_id": 123}      │
```

## 1.3 Flusso Heartbeat

```
AGENT                  SERVER                 CELERY
  │                      │                      │
  │ Every 30 sec         │                      │
  ├──────────────────────►                      │
  │ {"type":"heartbeat", │                      │
  │  "timestamp":"...",  │                      │
  │  "system_stats":{}}  │                      │
  │                      │                      │
  │                      │ Update               │
  │                      │ last_heartbeat       │
  │                      │ is_online=True       │
  │                      │                      │
  │◄─────────────────────┤                      │
  │ {"type":"heartbeat_  │                      │
  │  ack"}               │                      │
  │                      │                      │
  │                      │  Every 2 min         │
  │                      │◄─────────────────────┤
  │                      │  check_agent_health  │
  │                      │                      │
  │                      │  For each agent:     │
  │                      │  if last_heartbeat   │
  │                      │  > 2 min ago:        │
  │                      │    status='offline'  │
  │                      │    create_alert()    │
```

## 1.4 Flusso Threat Detection

```
AGENT                         SERVER
  │                             │
  │ 1. Analyze traffic          │
  │ (local threat detector)     │
  │                             │
  │ 2. Calculate scores         │
  │ score >= 75? (threshold)    │
  │                             │
  │ YES: Apply block            │
  │ (based on config)           │
  │                             │
  │ 3. Send threat_log          │
  ├─────────────────────────────►
  │ {"type":"threat_log",       │
  │  "threats":[...]}           │
  │                             │
  │                             │ 4. Save ThreatLog
  │                             │ classification=CRITICAL
  │                             │
  │                             │ 5. Check score >= 80
  │                             │ Create Alert
  │                             │
  │◄────────────────────────────┤
  │ {"type":"threat_ack"}       │
```

## 1.5 Flusso Command Execution

```
USER              SERVER                 AGENT
  │                 │                      │
  │ Add Rule        │                      │
  ├─────────────────►                      │
  │ POST /api/      │                      │
  │ targets/{id}/   │                      │
  │ rules/add/      │                      │
  │                 │                      │
  │                 │ Create Command       │
  │                 │ command_id=uuid      │
  │                 │                      │
  │                 ├──────────────────────►
  │                 │ {"type":"command",   │
  │                 │  "command_id":"uuid",│
  │                 │  "action":"add_rule",│
  │                 │  "payload":{...}}    │
  │                 │                      │
  │                 │                      │ Execute
  │                 │                      │ iptables
  │                 │                      │
  │                 │◄─────────────────────┤
  │                 │ {"type":"command_    │
  │                 │  response",          │
  │                 │  "command_id":"uuid",│
  │                 │  "status":"success"} │
  │                 │                      │
  │◄────────────────┤                      │
  │ Response 200    │                      │
```

## 1.6 Componenti Chiave

### Backend Django

**App: agent_manager**
- Models: AgentAPIKey, PairingSession, AgentConnection, AgentCommand, AgentHeartbeat
- Views: REST API per gestione agent
- Consumer: WebSocket per comunicazione real-time
- Tasks: Celery per operazioni periodiche (health check, cleanup)

### Agent Python

**Componenti principali:**
- `dog_agent.py`: Main loop
- `config_manager.py`: Gestione configurazione
- `websocket_client.py`: Client WebSocket
- `threat_detector.py`: Rilevamento minacce locale
- `firewall_manager.py`: Wrapper iptables
- `system_monitor.py`: Statistiche sistema
- `integrity_monitor.py`: Controllo integrità file

### Communication Protocol

**WebSocket over TLS 1.3**
- Server: wss://firedog.example.com/ws/agent/
- Autenticazione: API key + identity hash
- Formato messaggi: JSON
- Timeout pairing: 3 minuti
- Heartbeat interval: 30 secondi

## 1.7 Security Layers

```
┌─────────────────────────────────────────┐
│     Layer 1: TLS 1.3 Encryption         │
│     (SSL certificate verification)       │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│     Layer 2: API Key Authentication     │
│     (SHA512 hashed, global key)         │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│     Layer 3: Identity Verification      │
│     (SHA512 hash of ip+hostname+mac)    │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│     Layer 4: Command Authorization      │
│     (Per-target permission checks)      │
└─────────────────────────────────────────┘
```

## 1.8 Data Flow

### Inbound (Agent → Server)
1. **Pairing Request**: API key + system info → Verification → Connection established
2. **Heartbeat**: System stats → Update database → Health check
3. **Threat Log**: Detected threats → Save ThreatLog → Create alerts if critical
4. **Command Response**: Execution result → Update AgentCommand status

### Outbound (Server → Agent)
1. **Pairing Status**: Phase verification results → UI update
2. **Configuration**: Updated settings → Agent reconfiguration
3. **Commands**: Firewall operations → Agent execution → Response
4. **Heartbeat ACK**: Confirmation → Keep connection alive

## 1.9 Failure Scenarios

### Agent Disconnection
1. Server: Mark is_online=False after 2 minutes no heartbeat
2. Target status: Change to 'offline'
3. Alert: Create "Agent Offline" alert
4. Reconnection: Agent auto-reconnects every 30 seconds

### Pairing Timeout
1. PairingSession expires after 3 minutes
2. Target status: Reset to 'unpaired'
3. User: Must restart pairing process

### Command Failure
1. Agent: Send error response
2. Server: Mark command as 'failed' with error message
3. User: Can retry command manually

### Network Partition
1. Agent: Continues local threat detection
2. Server: Marks agent offline, queues commands
3. Reconnection: Agent syncs queued commands

## 1.10 Performance Considerations

### Database
- Indexes on: status, last_heartbeat, is_online, command_id
- Retention: Heartbeat history 24h, old pairing sessions 7 days
- Connection pooling: pgBouncer recommended for >50 agents

### WebSocket
- Max connections: Limited by Nginx (default 512)
- Memory per connection: ~5-10MB
- Scaling: Use Redis channels for multi-server setup

### Agent
- CPU usage: <5% idle, <15% during analysis
- Memory: ~50-100MB
- Disk I/O: Minimal (log rotation enabled)

## 1.11 Monitoring Points

### Server
- WebSocket active connections count
- Agent health check execution time
- Database query performance
- Celery task queue length
- Alert creation rate

### Agent
- Heartbeat success rate
- Command execution time
- Threat detection frequency
- System resource usage
- WebSocket reconnection attempts

---

**File 01 Completato**

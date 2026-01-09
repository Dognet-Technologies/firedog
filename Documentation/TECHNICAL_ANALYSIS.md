# FIREDOG - ANALISI TECNICA APPROFONDITA
## Documentazione Algoritmica e Architetturale per Ottimizzazione

**Autore**: Senior Developer Analysis
**Data**: 2026-01-09
**Progetto**: FireDog - Centralized Multi-Target Firewall Management System
**Obiettivo**: Identificare "motori" algoritmici core per ottimizzazione performance

---

## EXECUTIVE SUMMARY

FireDog è un sistema distribuito di gestione firewall che opera su architettura **hub-and-spoke**:
- **Hub**: Server centrale Django (PostgreSQL + Celery + Redis)
- **Spokes**: Target remoti con firewall iptables + traffic analyzer
- **Comunicazione**: SSH/SCP per orchestrazione, PCAP per analisi traffico

Le macro aree algoritmiche chiave identificate sono:
1. **Threat Analysis & Scoring** - Motore di scoring ML-like
2. **Target Management** - Orchestrazione distribuita SSH
3. **Rule Engine** - Generazione iptables da modello ORM
4. **Discovery & Enumeration** - Network scanning ARP-based
5. **Integrity Monitoring** - Hash-based file integrity
6. **Task Orchestration** - Celery distributed task queue
7. **Authentication & Authorization** - RBAC permission system
8. **Data Persistence** - Indexed relational model

---

## MACRO AREA 1: THREAT ANALYSIS & SCORING

### 1.1 Descrizione Funzionale

Il **Traffic Analyzer** è il motore di intelligence del sistema. Analizza file PCAP (Packet Capture) generati da ulogd2 sui target e calcola uno **threat score** (0-100) per ogni IP sorgente basandosi su pattern comportamentali.

**File chiave**: `/firedog-package/traffic-analyzer.py`

### 1.2 Flusso dei Dati

```
[Target iptables] → [ulogd2] → [PCAP files]
                                     ↓
                            [tcpdump parsing]
                                     ↓
                            [TrafficAnalyzer]
                                     ↓
              ┌──────────────────────┴──────────────────────┐
              ↓                                             ↓
    [IP Statistics Dict]                          [Threat Scoring]
    - packets count                                - Volume score
    - ports scanned                                - Port scan score
    - protocols used                               - Attack ports score
    - TCP flags                                    - SYN flood score
                                                   - Protocol diversity score
                                     ↓
                            [Classification]
                            - Critical (≥80)
                            - High (≥60)
                            - Medium (≥40)
                            - Low (≥20)
                                     ↓
                          [Report Generation]
                          [JSON Export]
```

### 1.3 Algoritmo di Scoring (calculate_threat_score)

**Location**: `traffic-analyzer.py:187-227`

```python
def calculate_threat_score(ip: str) -> int:
    score = 0

    # 1. VOLUME ANALYSIS - O(1)
    if packets > 1000:   score += 40
    elif packets > 500:  score += 30
    elif packets > 100:  score += 20
    elif packets > 50:   score += 10

    # 2. PORT SCANNING DETECTION - O(1)
    num_ports = len(unique_ports)
    if num_ports > 50:   score += 30
    elif num_ports > 20: score += 20
    elif num_ports > 10: score += 10

    # 3. ATTACK PORTS INTERSECTION - O(min(n,m))
    attack_hits = ports ∩ ATTACK_PORTS  # Set intersection
    score += len(attack_hits) * 5

    # 4. SYN FLOOD DETECTION - O(1)
    if 'S' in tcp_flags AND packets > 100:
        score += 15

    # 5. PROTOCOL DIVERSITY - O(1)
    if len(protocols) > 2:
        score += 10

    # Normalization
    return min(100, score)
```

**Complessità Totale**: **O(min(n,m))** dove:
- `n` = numero porte uniche scanned
- `m` = dimensione set ATTACK_PORTS (fisso, = 12)

Quindi in pratica: **O(1)** per IP (costante bounded).

### 1.4 Motore Sottostante: Scoring Euristico Lineare

**Caratteristiche**:
- **Modello**: Somma pesata di feature binarie/categoriche
- **Pesi fissi**: Hardcoded (non machine learning)
- **Feature extraction**: 5 dimensioni (volume, ports, attack_ports, flags, protocols)
- **Threshold-based classification**: 4 livelli di severity

**Limiti Algoritmici**:
1. **Assenza di apprendimento**: Pesi statici non si adattano a nuovi pattern
2. **Feature correlation ignorata**: Le feature sono trattate come indipendenti
3. **Time-series analysis assente**: Ignora comportamento temporale
4. **False positive rate**: Può penalizzare scanner legittimi (es. Nessus, Qualys)
5. **IP reputation assente**: Non usa database reputazione esterni

### 1.5 Metriche di Performance

**Operazioni per analisi PCAP**:
```
N = numero pacchetti nel PCAP
U = numero IP unici
P = media porte per IP

- Parsing PCAP:          O(N)       [tcpdump subprocess]
- IP stats aggregation:  O(N)       [dict updates]
- Scoring per IP:        O(U)       [U iterazioni di O(1)]
- Sorting top IPs:       O(U log U) [sorted()]
- Report generation:     O(U)

TOTALE: O(N + U log U)
```

**Benchmark stimato** (PCAP 10,000 pacchetti, 500 IP unici):
- Parsing: ~2-3 secondi (tcpdump I/O bound)
- Analysis: ~0.1 secondi (CPU bound)
- **Totale**: ~2-3 secondi

### 1.6 Opportunità di Ottimizzazione

#### A. Algoritmica
1. **Machine Learning Scoring**:
   - Sostituire scoring lineare con Random Forest o Gradient Boosting
   - Feature engineering: rate temporale, geolocation, ASN reputation
   - Training su dataset labeled (benign/malicious traffic)
   - **Miglioramento atteso**: Riduzione FP del 30-40%

2. **Streaming Analysis**:
   - Passare da batch processing (intero PCAP) a streaming
   - Libreria: `pyshark` o `scapy` con sliding window
   - **Miglioramento atteso**: Analisi real-time vs post-facto

3. **Time-Series Anomaly Detection**:
   - Algoritmo: Isolation Forest o Autoencoder
   - Detects: Variazioni pattern temporali (spike improvvisi)
   - **Miglioramento atteso**: Detection di slow scans/low-and-slow attacks

#### B. Performance
1. **Parsing Optimization**:
   - Sostituire `tcpdump` subprocess con parsing nativo Python (`dpkt` o `scapy`)
   - **Miglioramento atteso**: 40-50% riduzione tempo parsing

2. **Parallel Processing**:
   - Multi-processing per analizzare multipli PCAP in parallelo
   - `multiprocessing.Pool` o Celery task
   - **Miglioramento atteso**: Linear speedup con CPU cores

3. **Caching IP Reputation**:
   - Redis cache per IP già scored
   - TTL 24h per IP con score stabile
   - **Miglioramento atteso**: 60-70% riduzione re-computation

#### C. Entropia e Information Gain
- **Shannon Entropy sui pattern porte**: Misurare randomness scanning
  ```
  H(X) = -Σ p(xi) log₂ p(xi)
  ```
  Dove X = distribuzione porte scanned
  - **Entropy alta** (vicino a log₂ 65535) → Random scan
  - **Entropy bassa** → Targeted attack

---

## MACRO AREA 2: TARGET MANAGEMENT

### 2.1 Descrizione Funzionale

Sistema di orchestrazione per gestione ciclo di vita target remoti:
- Registrazione target
- Installazione pacchetto firedog via SSH
- Health monitoring periodico
- Sincronizzazione configurazioni

**File chiave**:
- `/backend/targets/models.py`
- `/backend/targets/tasks.py`
- `/backend/core/ssh_manager.py` (non letto, ma referenziato)

### 2.2 Flusso Installazione Target

```
[API Request: POST /api/targets/{id}/install/]
              ↓
[Target.status = 'installing']
              ↓
[Celery Task: install_firedog_on_target.delay()]
              ↓
      ┌───────┴────────┐
      ↓                ↓
[SSH Connect]  [Retry Logic: max 3 attempts]
      ↓
[Step 1: Check user exists]
      ↓
[Step 2: SSH Hardening]
  - Disable PasswordAuthentication
  - Enable PubkeyAuthentication
  - Backup sshd_config
  - Restart sshd
      ↓
[Step 3: Configure sudoers]
  - Create /etc/sudoers.d/microcyber
  - NOPASSWD for iptables, firewall-manager
      ↓
[Step 4: Upload firedog-package via SCP]
  - Source: /opt/firedog/firedog-package/
  - Dest: /tmp/firedog-package/
      ↓
[Step 5: Execute install.sh]
  - Timeout: 300 seconds
  - Install dependencies
  - Setup systemd service
      ↓
[Step 6: Verify installation]
  - Check /usr/local/bin/firewall-manager
  - Get version
      ↓
[Step 7: Update target status]
  - status = 'online'
  - firedog_version = extracted
  - last_seen = now()
```

### 2.3 Algoritmo di Health Monitoring

**Location**: `targets/tasks.py:357-393`

```python
@shared_task
def check_targets_health():
    targets = Target.objects.filter(status='online')

    for target in targets:  # O(T) where T = num targets
        try:
            ssh = SSHManager(target.ip_address, ...)
            ssh.connect()                    # O(1) - TCP handshake
            exit_code, _, _ = ssh.execute_command('echo "OK"')  # O(1)
            ssh.disconnect()

            if exit_code == 0:
                target.mark_online()         # O(1) - DB update
            else:
                target.mark_offline()
        except:
            target.mark_offline()
```

**Complessità**: **O(T)** sequenziale, dove T = numero target.

**Tempo esecuzione** (T=100 target, RTT=50ms):
- Seriale: 100 × 50ms = **5 secondi**
- Con connection timeout: può arrivare a **100 × timeout** (es. 10s = 16.7 minuti)

### 2.4 Motore Sottostante: Sequential SSH Orchestration

**Caratteristiche**:
- **Pattern**: Synchronous remote command execution
- **Library**: Paramiko (SSH2 protocol)
- **Connection pooling**: Assente (ogni operazione crea nuova connessione)
- **Retry logic**: Celery built-in (max_retries=3)
- **Error handling**: Try-catch con rollback (es. restore sshd_config)

### 2.5 Metriche di Performance

**Operazioni installazione target**:
```
1. SSH Connect:           O(1)    ~100-500ms   [Network I/O]
2. Check user:            O(1)    ~50ms        [Remote exec]
3. SSH Hardening:         O(1)    ~200ms       [File ops]
4. Sudoers config:        O(1)    ~100ms       [File ops]
5. SCP upload (10MB):     O(N)    ~2-5s        [Network I/O, N=file size]
6. Install script:        O(1)    ~10-30s      [apt install, systemd]
7. Verify:                O(1)    ~50ms

TOTALE: ~15-40 secondi per target
```

**Collo di bottiglia**:
1. **SCP upload** (I/O bound)
2. **install.sh apt install** (CPU bound remote)

### 2.6 Opportunità di Ottimizzazione

#### A. Parallelizzazione
1. **Async SSH Operations**:
   - Libreria: `asyncssh` invece di `paramiko`
   - Permette N connessioni concorrenti
   - **Miglioramento**: 100 target in 5s invece di 16.7min

2. **Bulk Health Checks**:
   - Celery chord: fan-out task per ogni target, aggregate results
   - **Miglioramento**: Linear speedup con worker count

#### B. Connection Pooling
1. **Persistent SSH Connections**:
   - Mantenere connessioni SSH aperte in pool Redis
   - SSH ControlMaster multiplexing
   - **Miglioramento**: Riduzione latency 80-90% su operazioni ripetute

#### C. Algoritmica
1. **Adaptive Timeout**:
   - Timeout dinamico basato su RTT storico del target
   - Formula: `timeout = avg_rtt × 3 + std_dev × 2`
   - **Miglioramento**: Riduzione wait time per target offline

2. **Circuit Breaker Pattern**:
   - Se target fail consecutivi > soglia, skip per N minuti
   - **Miglioramento**: Evita retry storm su target permanentemente offline

3. **Package Diff Upload**:
   - Invece di upload completo, calcola diff con versione remote
   - Usa rsync invece di SCP
   - **Miglioramento**: Riduzione bandwidth 70-90% su re-deploy

---

## MACRO AREA 3: RULE ENGINE

### 3.1 Descrizione Funzionale

Il **Rule Engine** traduce regole firewall da modello ORM Django a comandi iptables eseguibili sui target.

**File chiave**: `/backend/rules/models.py`

### 3.2 Flusso Generazione Regola

```
[Django Model: FirewallRule]
  - target: FK → Target
  - chain: ENUM(INPUT, OUTPUT, FORWARD)
  - protocol: ENUM(tcp, udp, icmp, all)
  - port: Integer(1-65535)
  - source_ip: IPAddress
  - dest_ip: IPAddress
  - action: ENUM(ACCEPT, DROP, REJECT)
  - comment: String
              ↓
[Method: to_iptables_command()]
              ↓
      ┌───────┴────────┐
      ↓                ↓
[Build Command]   [Add Modifiers]
  - iptables         - conntrack
  - -A/-I CHAIN      - comment
  - -p protocol
  - --dport/sport
  - -s/-d IP
  - -j ACTION
              ↓
[Output: String Command]
"iptables -A INPUT -p tcp --dport 80 -m conntrack --ctstate NEW -j ACCEPT -m comment --comment 'Allow HTTP'"
              ↓
[SSH Execute on Target]
```

### 3.3 Algoritmo di Generazione

**Location**: `rules/models.py:147-189`

```python
def to_iptables_command(self) -> str:
    cmd_parts = ['iptables']

    # Chain insertion - O(1)
    if self.rule_number:
        cmd_parts.extend(['-I', self.chain, str(self.rule_number)])
    else:
        cmd_parts.extend(['-A', self.chain])

    # Protocol - O(1)
    if self.protocol != 'all':
        cmd_parts.extend(['-p', self.protocol])

    # Port - O(1)
    if self.port:
        flag = '--dport' if self.chain in ['INPUT', 'OUTPUT'] else '--dport'
        cmd_parts.extend([flag, str(self.port)])

    # IPs - O(1)
    if self.source_ip:
        cmd_parts.extend(['-s', self.source_ip])
    if self.dest_ip:
        cmd_parts.extend(['-d', self.dest_ip])

    # Connection tracking - O(1)
    if self.action == 'ACCEPT' and self.protocol in ['tcp', 'udp']:
        cmd_parts.extend(['-m', 'conntrack', '--ctstate', 'NEW'])

    # Action - O(1)
    cmd_parts.extend(['-j', self.action])

    # Comment - O(1)
    if self.comment:
        cmd_parts.extend(['-m', 'comment', '--comment', self.comment[:256]])

    return ' '.join(cmd_parts)  # O(K) where K = num parts (~20)
```

**Complessità**: **O(1)** (costante bounded).

### 3.4 Motore Sottostante: Template-Based Command Generation

**Caratteristiche**:
- **Pattern**: String builder/accumulator
- **Validazione**: Django validators (MinValueValidator, MaxValueValidator, validate_ipv46_address)
- **Escape**: Nessuno (potenziale injection se comment non sanitizzato)
- **State tracking**: `is_synced` flag per tracking sincronizzazione

### 3.5 Indici Database

```python
# Meta indexes - rules/models.py:113-119
indexes = [
    Index(fields=['target', 'chain']),        # O(log R)
    Index(fields=['target', 'is_custom']),    # O(log R)
    Index(fields=['is_synced']),              # O(log R)
]
ordering = ['target', 'chain', 'rule_number']
```

**Query performance**:
- `SELECT rules WHERE target_id = X AND chain = 'INPUT'`: **O(log R + K)** dove K = result size
- Full table scan senza index: **O(R)** dove R = totale regole

### 3.6 Opportunità di Ottimizzazione

#### A. Sicurezza
1. **Command Injection Protection**:
   - Sanitizzare `comment` field con whitelist chars
   - Usare `shlex.quote()` per escape bash
   - **Impatto**: Elimina rischio injection

2. **Validation Enhancement**:
   - Validare CIDR notation in `source_ip`/`dest_ip`
   - Regex validation per port ranges (es. "80:443")

#### B. Performance
1. **Bulk Rule Application**:
   - Generare script iptables completo invece di singoli comandi
   - Applicare atomically con `iptables-restore`
   - **Miglioramento**: Riduzione SSH roundtrips da N a 1

2. **Rule Compilation**:
   - Pre-generare e cachare comandi iptables in field DB
   - `generated_command = models.TextField(editable=False)`
   - Rigenera solo on save()
   - **Miglioramento**: Riduzione CPU su query ripetute

#### C. Algoritmica
1. **Rule Conflict Detection**:
   - Algoritmo: Build directed graph di regole
   - Detect: Cicli (conflitti) usando Tarjan's SCC
   - **Complessità**: O(R + E) dove E = edges (dipendenze)
   - **Beneficio**: Prevenzione configurazioni invalid

2. **Rule Optimization**:
   - Merge regole adiacenti identiche
   - Collapse range porte in sintassi compatta
   - **Esempio**:
     ```
     -A INPUT -p tcp --dport 80 -j ACCEPT
     -A INPUT -p tcp --dport 443 -j ACCEPT
     →
     -A INPUT -p tcp -m multiport --dports 80,443 -j ACCEPT
     ```

3. **Priority Queue per Rule Ordering**:
   - Invece di `rule_number` sequenziale, usa heap/priority queue
   - Auto-reorder su insertion per garantire ordine ottimale
   - **Miglioramento**: Evita renumbering manuale

---

## MACRO AREA 4: DISCOVERY & ENUMERATION

### 4.1 Descrizione Funzionale

Sistema di **network discovery** per identificare host attivi sulla rete locale usando ARP scanning.

**File chiave**: `/backend/discovery/tasks.py`

### 4.2 Flusso Discovery

```
[Celery Task: discover_network_task]
              ↓
[Step 1: Get Local Networks]
  - Execute: ip route
  - Parse: CIDR networks (e.g., 192.168.1.0/24)
  - Filter: Skip default, localhost, link-local
              ↓
[Step 2: For each network]
  ┌─────────┴─────────┐
  ↓                   ↓
[Execute arp-scan] [Parse Output]
  sudo arp-scan -l    IP + MAC + Vendor
  ↓
[Step 3: For each discovered host]
  - Resolve hostname (host command)
  - Check if already Target
  - Get/Create DiscoveredHost
  - Update stats: last_seen, scan_count
              ↓
[Step 4: Mark unseen hosts as offline]
  - DiscoveredHost.filter(is_alive=True).exclude(id__in=discovered)
  - Set is_alive=False
```

### 4.3 Algoritmo ARP Scan

**Location**: `discovery/tasks.py:176-241`

```python
def scan_network_arp(network: str) -> List[Dict]:
    # Execute arp-scan - O(N) where N = hosts in network
    result = subprocess.run(
        ['sudo', 'arp-scan', '-l'],
        timeout=60
    )

    hosts = []
    for line in result.stdout.split('\n'):  # O(M) where M = output lines
        # Regex parsing - O(L) where L = line length
        match = re.match(r'^(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:]{17})\s+(.*)', line)

        if match:
            ip = match.group(1)
            mac = match.group(2).upper()
            vendor = match.group(3).strip()

            hostname = resolve_hostname(ip)  # O(1) - DNS query with 2s timeout

            hosts.append({'ip': ip, 'mac': mac, 'vendor': vendor, 'hostname': hostname})

    return hosts
```

**Complessità totale**:
- ARP scan: **O(H)** dove H = numero host sulla rete
- Parsing: **O(M)** dove M = linee output (~H)
- Hostname resolution: **O(H × T)** dove T = timeout DNS (2s)
- **TOTALE**: **O(H × T)** = può essere lento per reti grandi

### 4.4 Motore Sottostante: Subprocess-Based Network Enumeration

**Caratteristiche**:
- **Tool**: `arp-scan` (ARP-based, Layer 2)
- **Permissions**: Richiede sudo (raw sockets)
- **Alternative**: `nmap -sn` (ICMP ping sweep, Layer 3)
- **Database**: PostgreSQL con index su `ip_address`, `is_alive`

### 4.5 Metriche Performance

**Benchmark** (rete /24 con 50 host attivi):
```
1. ip route parsing:     ~10ms
2. arp-scan execution:   ~5-10s    [ARP request/reply roundtrips]
3. Output parsing:       ~50ms     [regex su 50 righe]
4. Hostname resolution:  ~100s     [50 × 2s timeout, serialized]
5. DB updates:           ~500ms    [50 get_or_create + updates]

TOTALE: ~110-115 secondi per rete /24
```

**Bottleneck**: Hostname resolution (**87% del tempo totale**).

### 4.6 Opportunità di Ottimizzazione

#### A. Parallelizzazione
1. **Async Hostname Resolution**:
   - Usare `asyncio` + `aiodns` per DNS queries parallele
   - **Miglioramento**: Da 50 × 2s = 100s → 2s (single round)
   - **Speedup**: **50x**

2. **Multi-Network Scanning**:
   - Celery group per scansionare N reti in parallelo
   - **Miglioramento**: Linear speedup con worker count

#### B. Algoritmica
1. **Incremental Scanning**:
   - Scannerizzare solo IP range con alta probabilità di essere attivi
   - Usare storia `last_seen` per prioritizzare range
   - **Miglioramento**: Riduzione scansione su reti sparse

2. **Adaptive Timeout**:
   - Ridurre timeout DNS a 500ms (default 2s è eccessivo)
   - Skip hostname resolution per IP già noti con hostname
   - **Miglioramento**: Riduzione tempo 60-70%

#### C. Alternative Tools
1. **Masscan**:
   - Alternative a arp-scan: `masscan` (più veloce)
   - **Benchmark**: Può scansionare /16 in pochi secondi
   - **Trade-off**: Meno accurato su Layer 2

2. **Passive Discovery**:
   - Invece di active scanning, monitor ARP table del router
   - Parse `/proc/net/arp` sui target
   - **Beneficio**: Zero network overhead

---

## MACRO AREA 5: INTEGRITY MONITORING

### 5.1 Descrizione Funzionale

Sistema di **File Integrity Monitoring (FIM)** che rileva modifiche non autorizzate a file critici usando hash SHA-512.

**File chiave**: `/backend/integrity/tasks.py`

### 5.2 Flusso Integrity Check

```
[Celery Task: check_all_integrity]
              ↓
[Load all FileIntegrity records from DB]
              ↓
[For each file_integrity]
  ┌──────────┴────────────┐
  ↓                       ↓
[Check file exists]  [File missing?]
  ↓ Yes                   ↓ No
[Read file content]  [mark_missing()]
  ↓
[Calculate SHA-512 hash]
  ↓
[Compare with stored hash]
  ┌──────────┴────────────┐
  ↓ Different             ↓ Same
[mark_modified()]    [mark_ok()]
  - Update hash          - Update last_check
  - Alert                - is_modified = False
```

### 5.3 Algoritmo Hash-Based Integrity

**Location**: `integrity/tasks.py:7-26`

```python
@shared_task
def check_all_integrity():
    files = FileIntegrity.objects.all()  # O(F) DB query

    for file_integrity in files:  # O(F) iteration
        if not os.path.exists(file_integrity.file_path):  # O(1) syscall
            file_integrity.mark_missing()
            continue

        # Read entire file - O(S) where S = file size
        with open(file_integrity.file_path, 'rb') as f:
            file_bytes = f.read()

        # SHA-512 hashing - O(S)
        current_hash = hashlib.sha512(file_bytes).hexdigest()

        # Comparison - O(1) (128-char string)
        if current_hash != file_integrity.sha512_hash:
            file_integrity.mark_modified(current_hash)  # O(1) DB update
        else:
            file_integrity.mark_ok()  # O(1) DB update
```

**Complessità totale**: **O(F × S)** dove:
- F = numero file monitorati
- S = dimensione media file

### 5.4 Motore Sottostante: Cryptographic Hash Integrity

**Caratteristiche**:
- **Hash function**: SHA-512 (512-bit digest, collision-resistant)
- **Alternative**: SHA-256 (faster, 256-bit), BLAKE2 (fastest)
- **Storage**: Hash esadecimale (128 caratteri per SHA-512)
- **Change detection**: Byte-level (anche 1 byte modificato → hash diverso)

### 5.5 Metriche Performance

**Benchmark** (100 file, media 1MB ciascuno):
```
1. DB query:         ~10ms       [SELECT * FROM file_integrity]
2. For 100 files:
   - File exists:    ~1ms × 100  = 100ms
   - File read:      ~3ms × 100  = 300ms  [I/O bound]
   - SHA-512 hash:   ~8ms × 100  = 800ms  [CPU bound]
   - Hash compare:   ~0.1ms × 100 = 10ms
   - DB update:      ~5ms × 100  = 500ms

TOTALE: ~1.7 secondi per 100 file (100MB totali)
```

**Throughput**: ~58 MB/s (limitato da I/O disk).

### 5.6 Opportunità di Ottimizzazione

#### A. Algoritmica
1. **Incremental Hashing**:
   - Invece di hash completo, usa **chunk-based hashing**
   - Dividi file in blocchi (es. 64KB)
   - Hash solo blocchi modificati (traccia mtime per block)
   - **Miglioramento**: 10-100x speedup su file grandi parzialmente modificati

2. **Faster Hash Function**:
   - Sostituire SHA-512 con **BLAKE2b**
   - **Benchmark**: BLAKE2 è 2-3x più veloce di SHA-512
   - **Security**: BLAKE2 è cryptographically secure
   - **Miglioramento**: 50-60% riduzione tempo hashing

#### B. Performance
1. **Parallel Hashing**:
   - Usare `multiprocessing.Pool` per hash files in parallelo
   - **Speedup**: Linear con CPU cores (es. 8 core → 8x)

2. **Memoization**:
   - Cachare hash basato su (file_path, mtime, size)
   - Se mtime non cambiato → skip re-hash
   - **Miglioramento**: 90-95% skip su file non modificati

3. **Selective Monitoring**:
   - Prioritizzare file critici (es. `/etc/passwd`, binari SUID)
   - Skip file volatili (logs, tmp)
   - **Miglioramento**: Riduzione F di 70-80%

#### C. Change Detection Enhancement
1. **Binary Diff**:
   - Su file modified, calcola binary diff (bsdiff, xdelta)
   - Store patch invece di solo "modified" flag
   - **Beneficio**: Forensic analysis (cosa è cambiato esattamente)

2. **Entropy Analysis**:
   - Calcola Shannon entropy del file
   - **Entropy alta improvvisa** → possibile encryption (malware)
   - Formula: `H = -Σ p(byte) log₂ p(byte)` per ogni byte value 0-255

---

## MACRO AREA 6: TASK ORCHESTRATION

### 6.1 Descrizione Funzionale

Sistema di **task scheduling asincrono** basato su Celery per:
- Background jobs (installazione target, discovery)
- Periodic tasks (health checks, integrity monitoring)
- Distributed task execution

**Stack**: Celery + Redis (broker) + PostgreSQL (result backend)

### 6.2 Architettura Celery

```
[Django Views]
      ↓ task.delay()
[Celery Beat Scheduler]  ← periodic tasks
      ↓ publish
[Redis Broker]
      ↓ consume
[Celery Workers] (N instances)
  - Worker 1
  - Worker 2
  - ...
  - Worker N
      ↓ execute
[Task Functions]
  - install_firedog_on_target
  - discover_network_task
  - check_all_integrity
  - check_targets_health
      ↓ result
[PostgreSQL Result Backend]
      ↓ fetch
[Django Views via AsyncResult]
```

### 6.3 Task Patterns Identificati

#### Pattern 1: Long-Running Installation
```python
@shared_task(bind=True, max_retries=3)
def install_firedog_on_target(self, target_id, user_id):
    # Durata: 15-40 secondi
    # Retry: Su SSH failure con exponential backoff
    # State tracking: Target.status field
```

**Caratteristiche**:
- **Idempotenza**: Partially (usa `force_reinstall` flag)
- **State machine**: `pending → installing → online/error`
- **Rollback**: Su errore, restore sshd_config backup

#### Pattern 2: Periodic Discovery
```python
@shared_task
def discover_network_task():
    # Scheduled: Ogni N minuti (Celery Beat)
    # Durata: ~2 minuti per rete /24
    # Side effects: DB inserts/updates DiscoveredHost
```

**Caratteristiche**:
- **Idempotenza**: Sì (get_or_create pattern)
- **Concurrency control**: Nessuna (possibile duplicate scan)

#### Pattern 3: Health Monitoring
```python
@shared_task
def check_targets_health():
    # Scheduled: Ogni 5 minuti
    # Durata: O(T × timeout) worst case
    # Concurrency: Sequential
```

**Caratteristiche**:
- **Idempotenza**: Sì (state update)
- **Timeout risk**: Alto su molti target offline

### 6.4 Metriche Task Queue

**Throughput** (configurazione tipica: 4 workers):
- Max task rate: ~240 task/min (1 task/sec per worker)
- Latency: Time-to-start = queue_depth / (workers × task_rate)
- Backpressure: Redis memory limit

**Esempi**:
- 100 target installation queue → ~25 minuti (4 workers parallel)
- 10 reti discovery → ~5 minuti (4 workers, 2min/task)

### 6.5 Opportunità di Ottimizzazione

#### A. Concurrency Control
1. **Task Deduplication**:
   - Usare Celery `task_id` deterministic
   - Pattern: `task_id = f"discover-{network_cidr}"`
   - **Beneficio**: Evita duplicate scans

2. **Rate Limiting**:
   - Celery `rate_limit` per task type
   - Esempio: `@shared_task(rate_limit='10/m')`
   - **Beneficio**: Evita overwhelm di target remoti

#### B. Task Prioritization
1. **Priority Queues**:
   - Celery con multiple queues: `high`, `normal`, `low`
   - Installation → high, discovery → low
   - **Beneficio**: SLA guarantees per task criticality

2. **Deadline Scheduling**:
   - Celery `expires` parameter
   - Auto-discard task se non eseguito entro deadline
   - **Beneficio**: Evita stale task execution

#### C. Performance
1. **Prefetch Multiplier Tuning**:
   - Celery worker `prefetch_multiplier = 1`
   - Evita worker blocking su long task mentre altri idle
   - **Beneficio**: Better load balancing

2. **Result Backend Optimization**:
   - Usare Redis invece di PostgreSQL per results
   - **Miglioramento**: 10-50x latency riduzione su result fetch

3. **Task Batching**:
   - Invece di N task per N target, 1 task con chunking
   - Esempio: `check_targets_health(target_ids=[1,2,3,...,100])`
   - **Miglioramento**: Riduzione overhead task creation

---

## MACRO AREA 7: AUTHENTICATION & AUTHORIZATION

### 7.1 Descrizione Funzionale

Sistema **RBAC (Role-Based Access Control)** con 2 ruoli:
- **Admin**: Full CRUD su tutte le risorse
- **Reporter**: Read-only access

**File chiave**: `/backend/accounts/permissions.py`

### 7.2 Permission Flow

```
[HTTP Request] → [Django Middleware]
                        ↓
                [JWT Authentication]
                  - Extract token
                  - Verify signature
                  - Load user
                        ↓
                [Permission Check]
                  - IsAuthenticated?
                  - IsAdminUser?
                  - IsReporterOrAdmin?
                  - IsAdminOrReadOnly?
                        ↓
        ┌───────────────┴───────────────┐
        ↓ Granted                       ↓ Denied
[Execute View]                    [403 Forbidden]
```

### 7.3 Algoritmo Permission Check

**Location**: `accounts/permissions.py`

```python
class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        # O(1) - attribute access
        if not request.user or not request.user.is_authenticated:
            return False

        # O(1) - superuser flag
        if request.user.is_superuser:
            return True

        # O(1) with DB index - group membership check
        return request.user.groups.filter(name='Admin').exists()
```

**Complessità**: **O(1)** (con index su `auth_user_groups`).

### 7.4 Motore Sottostante: Django Groups + JWT

**Caratteristiche**:
- **Auth mechanism**: JWT (JSON Web Token) con SimpleJWT
- **Token lifespan**: Access token (15min), Refresh token (24h)
- **Group storage**: Many-to-Many table `auth_user_groups`
- **Permission granularity**: View-level (no object-level)

### 7.5 Schema Database

```sql
-- auth_user
id | username | password | is_superuser | is_staff | is_active

-- auth_group
id | name  ('Admin', 'Reporter')

-- auth_user_groups (Many-to-Many)
id | user_id | group_id

-- Index:
CREATE INDEX idx_user_groups ON auth_user_groups(user_id, group_id);
```

**Query per permission check**:
```sql
SELECT EXISTS(
    SELECT 1 FROM auth_user_groups
    JOIN auth_group ON auth_user_groups.group_id = auth_group.id
    WHERE auth_user_groups.user_id = ?
    AND auth_group.name = 'Admin'
);
```

**Performance**: O(1) con index, ~1ms.

### 7.6 Opportunità di Ottimizzazione

#### A. Caching
1. **Permission Caching**:
   - Cachare group membership in Redis
   - TTL = token lifespan (15min)
   - **Miglioramento**: Riduzione DB queries 99%

2. **Token Blacklisting Optimization**:
   - Se usato logout, implementare bloom filter per blacklist
   - **Miglioramento**: O(1) check vs O(log N) DB query

#### B. Granularità
1. **Object-Level Permissions**:
   - Implementare `has_object_permission()`
   - Esempio: Reporter può vedere solo target del suo team
   - **Pattern**: Django Guardian library

2. **Attribute-Based Access Control (ABAC)**:
   - Oltre al ruolo, check attributi (es. IP source, time)
   - **Use case**: Restrict admin access to office IP range

#### C. Audit
1. **Permission Denial Logging**:
   - Log ogni 403 Forbidden in AuditLog
   - **Beneficio**: Security monitoring, intrusion detection

---

## MACRO AREA 8: DATA PERSISTENCE

### 8.1 Descrizione Funzionale

Schema relazionale PostgreSQL con **11 app Django**, **20+ modelli**.

### 8.2 Schema ER Principale

```
Target (1) ────┬──── (N) FirewallRule
               ├──── (N) ThreatLog
               ├──── (N) WhitelistEntry
               ├──── (N) BlockedIP
               ├──── (N) FirewallStats
               ├──── (N) Alert
               └──── (M) TargetGroup (Many-to-Many)
                            │
                            └──── (N) GroupRuleTemplate

ThreatLog:
  - source_ip (indexed)
  - threat_score (indexed)
  - severity (indexed)
  - is_resolved (indexed)
  - detected_at (indexed)

FirewallRule:
  - target + chain (composite index)
  - is_synced (indexed)

DiscoveredHost:
  - ip_address (indexed)
  - is_alive (indexed)
```

### 8.3 Index Strategy

#### Indici Identificati:
1. **ThreatLog** (threats/models.py:113-120):
   ```python
   indexes = [
       Index(fields=['target', 'detected_at']),      # Time-series query
       Index(fields=['target', 'threat_score']),     # Top threats per target
       Index(fields=['source_ip', 'detected_at']),   # IP history
       Index(fields=['severity', 'is_resolved']),    # Unresolved threats
   ]
   ```

2. **FirewallRule** (rules/models.py:116-119):
   ```python
   indexes = [
       Index(fields=['target', 'chain']),
       Index(fields=['target', 'is_custom']),
       Index(fields=['is_synced']),
   ]
   ```

### 8.4 Query Patterns e Performance

#### Query 1: Recent Threats per Target
```python
ThreatLog.objects.filter(
    target=target_obj,
    is_resolved=False
).order_by('-threat_score')[:20]
```

**Execution Plan**:
- Index scan su `(target, threat_score)`: O(log N + K)
- K = 20 (LIMIT)

**Performance**: ~2ms su 1M records.

#### Query 2: Top Attackers Global
```python
ThreatLog.objects.values('source_ip').annotate(
    count=Count('id')
).order_by('-count')[:10]
```

**Execution Plan**:
- Sequential scan: O(N)
- GROUP BY + aggregation: O(N)
- Sort: O(U log U) dove U = unique IPs

**Performance**: ~200ms su 1M records (SLOW su grandi dataset).

**Ottimizzazione**:
- Materializzare view con Celery periodic task
- Aggiornare ogni 5 minuti invece di real-time

### 8.5 Storage Footprint

**Stima** (10 target, 1 anno dati):
```
ThreatLog:       ~100K record/anno × 500 bytes = 50 MB
FirewallRule:    ~500 regole × 300 bytes       = 150 KB
DiscoveredHost:  ~1000 host × 400 bytes        = 400 KB
FirewallStats:   ~10 target × 365 day × 1KB   = 3.6 MB
AuditLog:        ~50K eventi × 600 bytes       = 30 MB

TOTALE: ~84 MB/anno
```

Con 100 target: ~840 MB/anno (manageable).

### 8.6 Opportunità di Ottimizzazione

#### A. Partitioning
1. **Time-Series Partitioning**:
   - Partition `ThreatLog` per mese (PostgreSQL declarative partitioning)
   - **Beneficio**: Query su time range più veloci (skip partitions)

2. **Archiving**:
   - Muovere threat resolved + age > 6 mesi su cold storage
   - **Beneficio**: Riduzione DB size 60-70%

#### B. Materialized Views
1. **Threat Statistics**:
   ```sql
   CREATE MATERIALIZED VIEW threat_stats_by_ip AS
   SELECT source_ip, COUNT(*) as count, MAX(threat_score) as max_score
   FROM threats_threatlog
   GROUP BY source_ip;

   CREATE INDEX ON threat_stats_by_ip(count DESC);
   ```
   - Refresh ogni 5 minuti
   - **Miglioramento**: Query da 200ms → 2ms

#### C. Denormalization
1. **Target Stats Caching**:
   - Aggiungere a Target: `threat_count`, `last_threat_at`, `max_threat_score`
   - Aggiornare via Django signals
   - **Beneficio**: Dashboard queries più veloci

---

## CONCLUSIONI E ROADMAP OTTIMIZZAZIONE

### Priorità 1: Quick Wins (ROI alto, effort basso)
1. **Hostname resolution async** (Discovery): 50x speedup
2. **BLAKE2 hash** (Integrity): 2-3x speedup
3. **Permission caching** (Auth): 99% DB query reduction
4. **Bulk iptables apply** (Rules): N→1 SSH roundtrips

### Priorità 2: Algorithmic Improvements
1. **ML-based threat scoring**: Riduzione FP 30-40%
2. **Incremental file hashing**: 10-100x speedup su file grandi
3. **Async SSH operations**: Linear speedup con target count
4. **Task priority queues**: SLA guarantees

### Priorità 3: Scalabilità Long-Term
1. **Time-series partitioning**: Support 1000+ target
2. **Materialized views**: Sub-second dashboard queries
3. **Streaming threat analysis**: Real-time detection
4. **Circuit breaker pattern**: Resilienza su target offline

### Metriche Chiave da Monitorare
- **Threat Detection Latency**: PCAP generation → Alert (target: <5min)
- **Installation Throughput**: Target/hour (target: >100)
- **Discovery Completeness**: % host trovati vs ground truth (target: >95%)
- **False Positive Rate**: Threat incorrectly classified (target: <5%)

---

**Fine Analisi Tecnica**

Prossimi passi:
1. Benchmark baseline su ambiente production-like
2. Implementare ottimizzazioni Priorità 1
3. A/B testing su algoritmo threat scoring
4. Load testing su 100+ target simultanei

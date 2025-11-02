┌─────────────────────────────────────────┐
│   FireDog Central (localhost Django)   │
│   - PostgreSQL DB (user: microcyber)   │
│   - React/TypeScript Frontend          │
│   - JWT Auth (30min token)             │
│   - SSH Key Management (Ed25519)       │
└──────────────┬──────────────────────────┘
               │ SSH (chiave ellittica)
               │
    ┌──────────┴──────────┬───────────────┐
    │                     │               │
┌───▼────┐          ┌─────▼───┐     ┌────▼────┐
│Target 1│          │Target 2 │     │Target N │
│firedog │          │firedog  │     │firedog  │
│        │          │         │     │         │
│cron →  │          │cron →   │     │cron →   │
│analyzer│          │analyzer │     │analyzer │
└────────┘          └─────────┘     └─────────┘
```

---

## 📁 Struttura Progetto Proposta
```
firedog/
├── backend/                    # Django backend
│   ├── firedog/               # Progetto Django
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── api/                   # App principale
│   │   ├── models.py          # Target, ThreatLog, Rule, etc.
│   │   ├── serializers.py     
│   │   ├── views.py           # API endpoints
│   │   ├── tasks.py           # Celery/background tasks
│   │   └── ssh_manager.py     # Gestione SSH/SCP
│   ├── authentication/        # JWT auth
│   │   ├── views.py
│   │   └── serializers.py
│   ├── discovery/             # Network discovery
│   │   ├── arpscan.py
│   │   └── bulk_import.py
│   ├── integrity/             # File integrity checker
│   │   ├── hasher.py
│   │   └── models.py
│   └── requirements.txt
│
├── frontend/                  # React/TypeScript
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard/     # Main dashboard
│   │   │   ├── TargetList/    # Lista target
│   │   │   ├── ThreatView/    # Visualizzazione minacce
│   │   │   ├── RuleManager/   # Gestione regole iptables
│   │   │   ├── Settings/      # Configurazione
│   │   │   └── Alerts/        # Alert center
│   │   ├── services/          # API client
│   │   ├── types/             # TypeScript types
│   │   └── App.tsx
│   ├── package.json
│   └── tsconfig.json
│
├── deployment/
│   ├── firedog-package/       # Pacchetto da copiare sui target
│   │   ├── firewall-init.sh
│   │   ├── firewall-manager.py
│   │   ├── traffic-analyzer.py
│   │   ├── install.sh
│   │   └── ... (tutti i file attuali)
│   ├── scripts/
│   │   ├── setup-target.sh    # Script setup target
│   │   ├── cron-installer.sh  # Installa cron su target
│   │   └── integrity-check.sh
│   └── configs/
│       ├── microcyber-sshd.conf    # Config SSH hardened
│       └── microcyber-sudoers      # Sudoers blindato
│
├── install-firedog.sh         # Installer locale
├── systemd/
│   └── firedog.service
└── README.md
# CODICE COMPLETO - Dog Agent Implementation

Questo file contiene tutto il codice necessario per l'implementazione.
Riferirsi alla documentazione completa originale per dettagli su ogni sezione.

## NOTA IMPORTANTE

Il codice completo è stato fornito nella risposta precedente e include:

1. **Backend Django (agent_manager app)**:
   - models.py (completo con tutti i 5 models)
   - serializers.py (tutti i serializers)
   - views.py (tutti i ViewSets REST API)
   - consumers.py (WebSocket consumer completo)
   - routing.py
   - tasks.py (tutti i Celery tasks)

2. **Agent Python**:
   - dog_agent.py (main loop completo)
   - config_manager.py
   - websocket_client.py
   - threat_detector.py
   - firewall_manager.py
   - system_monitor.py
   - integrity_monitor.py

3. **Package Debian**:
   - DEBIAN/control
   - DEBIAN/postinst, prerm, postrm
   - systemd/dog-agent.service
   - build-deb.sh

4. **Configuration Files**:
   - agent.conf (JSON format)
   - requirements.txt
   - nginx.conf

## Istruzioni per ClaudeCode

1. Copia i file Python da questa documentazione
2. Crea la struttura directory appropriata
3. Implementa seguendo l'ordine:
   - Database migrations
   - Backend models
   - REST API views
   - WebSocket consumer
   - Celery tasks
   - Agent Python scripts
   - Package .deb

## File da Creare

### Backend Django

firedog_backend/agent_manager/
├── __init__.py
├── apps.py
├── models.py          # 5 models: AgentAPIKey, PairingSession, AgentConnection, AgentCommand, AgentHeartbeat
├── serializers.py     # 5 serializers corrispondenti
├── views.py           # 4 ViewSets: AgentAPIKeyViewSet, PairingSessionViewSet, AgentConnectionViewSet, AgentCommandViewSet
├── consumers.py       # AgentConsumer (WebSocket)
├── routing.py         # WebSocket URL patterns
├── tasks.py           # 5 Celery tasks
├── admin.py
├── migrations/
│   └── 0001_initial.py
└── tests/
    ├── test_models.py
    ├── test_views.py
    ├── test_consumers.py
    └── test_tasks.py

### Agent Python

/opt/sentinelsuite/firedog/
├── dog_agent.py       # Main agent (classe DogAgent)
├── config_manager.py  # Gestione configurazione JSON
├── websocket_client.py # Client WebSocket
├── firewall_manager.py # Wrapper iptables
├── threat_detector.py  # Analisi minacce locale
├── system_monitor.py   # Statistiche sistema
├── integrity_monitor.py # File integrity SHA512
├── utils.py
└── requirements.txt

### Package Debian

dog-agent_1.0.0_amd64/
├── DEBIAN/
│   ├── control
│   ├── postinst
│   ├── prerm
│   └── postrm
├── opt/sentinelsuite/firedog/  # Agent files
├── etc/dog-agent/
│   └── agent.conf.example
├── etc/systemd/system/
│   └── dog-agent.service
└── usr/share/doc/dog-agent/
    └── README.md

## Codice Completo

**RIFERIMENTO**: Tutto il codice è stato fornito nella documentazione completa nella risposta precedente.
Ogni file include:
- Header con imports
- Docstrings complete
- Type hints dove appropriato
- Error handling
- Logging
- Security best practices (OWASP/NIST compliant)

## Testing

Dopo implementazione, eseguire:

```bash
# Backend tests
cd firedog_backend
python manage.py test agent_manager --verbosity=2

# Agent tests  
cd /opt/sentinelsuite/firedog
python -m pytest tests/ -v

# Integration test
# 1. Start server components
# 2. Create target in UI
# 3. Start pairing
# 4. Install and start agent
# 5. Verify pairing success
# 6. Execute test commands
# 7. Check threat detection
```

## Deployment Checklist

- [ ] Database migrations executed
- [ ] API key generated
- [ ] Nginx configured for WebSocket
- [ ] SSL certificates installed
- [ ] Celery worker and beat running
- [ ] Agent .deb package built
- [ ] Agent installed on test target
- [ ] Pairing process tested
- [ ] Command execution tested
- [ ] Threat detection tested
- [ ] Logs verified
- [ ] Security audit completed


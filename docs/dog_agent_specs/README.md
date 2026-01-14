# FireDog Dog Agent - Documentazione Completa Implementazione

## Indice Documentazione

Questa cartella contiene tutta la documentazione necessaria per implementare il Dog Agent per FireDog.

### File Principali

1. **01_ARCHITETTURA_GENERALE.md** - Panoramica sistema, diagrammi di flusso
2. **02_DATABASE_SCHEMA.md** - Schema database completo, migrations
3. **03_BACKEND_DJANGO.md** - Implementazione backend Django completa
4. **04_WEBSOCKET_PROTOCOL.md** - Protocollo WebSocket dettagliato
5. **05_AGENT_PYTHON.md** - Codice completo agent Python
6. **06_PACKAGE_DEBIAN.md** - Creazione package .deb
7. **07_SECURITY.md** - Specifiche sicurezza OWASP/NIST
8. **08_DEPLOYMENT.md** - Guide deployment server e agent
9. **09_TESTING.md** - Procedure di testing
10. **10_MIGRATION_PLAN.md** - Piano di migrazione da SSH

### Cartelle

- **backend/** - Codice backend Django completo
- **agent/** - Codice agent Python completo
- **debian/** - File per package .deb
- **deployment/** - Script e configurazioni deployment
- **tests/** - Test suite completa

## Come Usare Questa Documentazione

### Per ClaudeCode

Fornisci l'intera cartella zippata a ClaudeCode con l'istruzione:

```
Implementa il sistema Dog Agent seguendo le specifiche nella documentazione.
Inizia con:
1. Backend Django (file 03_BACKEND_DJANGO.md)
2. Agent Python (file 05_AGENT_PYTHON.md)
3. Package Debian (file 06_PACKAGE_DEBIAN.md)
```

### Ordine di Implementazione Consigliato

1. **Database**: Esegui migrations (02_DATABASE_SCHEMA.md)
2. **Backend API**: Implementa REST endpoints (03_BACKEND_DJANGO.md)
3. **WebSocket**: Implementa consumer (03_BACKEND_DJANGO.md sezione 3.5)
4. **Agent**: Implementa agent Python (05_AGENT_PYTHON.md)
5. **Package**: Crea .deb package (06_PACKAGE_DEBIAN.md)
6. **Testing**: Esegui test suite (09_TESTING.md)
7. **Deploy**: Deployment produzione (08_DEPLOYMENT.md)

## Requisiti Tecnici

### Server
- OS: Debian 11/12 o Ubuntu 20.04/22.04
- Python 3.9+
- Django 4.2+
- PostgreSQL 13+
- Redis 6+
- Nginx 1.18+

### Agent (Target Machine)
- OS: Debian 11/12 o Ubuntu 20.04/22.04
- Python 3.9+
- iptables 1.8+
- ulogd2
- Root access

## Contatti e Supporto

Per domande sull'implementazione, riferirsi ai file di documentazione specifici.

## Note Importanti

- ⚠️ **Rimuovere completamente SSH**: Non mantenere retrocompatibilità
- ⚠️ **API Key unica globale**: Una sola API key per tutti gli agent
- ⚠️ **Identity hash**: SHA512 senza delimitatori (ip+hostname+mac)
- ⚠️ **Timeout pairing**: 3 minuti
- ⚠️ **Threshold default**: 75 per threat score
- ⚠️ **Heartbeat interval**: 30 secondi default

## Versione

- **Versione Documentazione**: 1.0.0
- **Data**: 2025-01-13
- **Autore**: Simone (FireDog Team)

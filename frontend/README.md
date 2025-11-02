# FireDog Frontend

Frontend React + TypeScript per FireDog - Sistema di Gestione Firewall Centralizzato.

## 🚀 Quick Start

```bash
cd frontend
npm install
npm start
```

Apri http://localhost:3000

## 📁 Struttura

- `src/components/` - Componenti riutilizzabili
- `src/pages/` - Pagine principali  
- `src/services/` - API client
- `src/contexts/` - React contexts
- `src/types/` - TypeScript types

## 🎨 Pagine

- ✅ Login - Autenticazione JWT
- ✅ Dashboard - Overview e statistiche
- ✅ Targets - Gestione target remoti

## 🔧 Tecnologie

- React 18 + TypeScript
- React Router
- Axios  
- Recharts

## 📝 Configurazione

File `.env`:
```
REACT_APP_API_URL=http://localhost:8000/api
```

## 🚢 Build Produzione

```bash
npm run build
```

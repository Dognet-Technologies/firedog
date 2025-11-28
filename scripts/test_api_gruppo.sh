#!/bin/bash
# Script per testare l'API targets e verificare che i campi gruppo vengano restituiti

echo "=========================================="
echo "TEST API TARGETS - Verifica campo GRUPPO"
echo "=========================================="
echo ""

# Colori per output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# URL dell'API (modifica se necessario)
API_URL="http://localhost:8000/api/targets/"

echo "🔍 Tentativo di connessione all'API..."
echo "URL: $API_URL"
echo ""

# Test connessione (senza autenticazione - per vedere se il server risponde)
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL" 2>/dev/null)

if [ "$RESPONSE" == "000" ]; then
    echo -e "${RED}❌ ERRORE: Backend non raggiungibile${NC}"
    echo "   Assicurati che daphne sia in esecuzione:"
    echo "   cd /home/simone/Repos/Progetti/firedog/backend"
    echo "   source venv/bin/activate"
    echo "   daphne -b 0.0.0.0 -p 8000 firedog.asgi:application"
    exit 1
fi

echo -e "${GREEN}✅ Backend raggiungibile (HTTP $RESPONSE)${NC}"
echo ""

# Richiesta con credenziali (modifica username/password se necessario)
echo "🔐 Test con autenticazione..."
echo ""

# Prima ottieni il token (modifica le credenziali se necessario)
echo "Ottieni token di autenticazione..."
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/token/ \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"admin"}' 2>/dev/null)

TOKEN=$(echo $TOKEN_RESPONSE | grep -o '"access":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo -e "${YELLOW}⚠️  Autenticazione fallita - prova senza token${NC}"
    echo ""
    echo "📡 GET $API_URL (senza autenticazione)"
    RESULT=$(curl -s "$API_URL" | head -c 1000)
else
    echo -e "${GREEN}✅ Token ottenuto${NC}"
    echo ""
    echo "📡 GET $API_URL (con autenticazione)"
    RESULT=$(curl -s -H "Authorization: Bearer $TOKEN" "$API_URL")
fi

echo ""
echo "📋 Risposta API (primi 1000 caratteri):"
echo "----------------------------------------"
echo "$RESULT" | head -c 1000
echo ""
echo "----------------------------------------"
echo ""

# Verifica se i campi gruppo sono presenti
if echo "$RESULT" | grep -q "gruppo"; then
    echo -e "${GREEN}✅ Campo 'gruppo' PRESENTE nella risposta API${NC}"
else
    echo -e "${RED}❌ Campo 'gruppo' ASSENTE nella risposta API${NC}"
    echo ""
    echo "🔧 Possibili cause:"
    echo "   1. Le migrazioni non sono state applicate al database"
    echo "   2. Il serializer non include il campo gruppo"
    echo "   3. Il backend non è stato riavviato dopo le modifiche"
fi

if echo "$RESULT" | grep -q "gruppo_display"; then
    echo -e "${GREEN}✅ Campo 'gruppo_display' PRESENTE nella risposta API${NC}"
else
    echo -e "${RED}❌ Campo 'gruppo_display' ASSENTE nella risposta API${NC}"
fi

echo ""
echo "=========================================="
echo "FINE TEST"
echo "=========================================="

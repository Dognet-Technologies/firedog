#!/bin/bash
# Script per setup database PostgreSQL per FireDog
# Eseguire con: sudo bash setup-database.sh

set -e

echo "=== FireDog Database Setup ==="
echo ""

# Colori per output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verifica se PostgreSQL è installato
if ! command -v psql &> /dev/null; then
    echo -e "${RED}PostgreSQL non installato!${NC}"
    echo "Installazione PostgreSQL..."
    apt-get update
    apt-get install -y postgresql postgresql-contrib
    systemctl start postgresql
    systemctl enable postgresql
    echo -e "${GREEN}PostgreSQL installato con successo${NC}"
fi

# Configurazione database
DB_NAME="firedog"
DB_USER="microcyber"
DB_PASSWORD="changeme123"

echo ""
echo -e "${YELLOW}Creazione database e utente...${NC}"

# Crea utente e database
sudo -u postgres psql << EOF
-- Crea utente se non esiste
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '${DB_USER}') THEN
        CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
    END IF;
END
\$\$;

-- Crea database se non esiste
SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\gexec

-- Grant privilegi
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};

-- Connetti al database firedog e grant schema permissions
\c ${DB_NAME}
GRANT ALL ON SCHEMA public TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DB_USER};
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database '${DB_NAME}' creato${NC}"
    echo -e "${GREEN}✓ Utente '${DB_USER}' creato${NC}"
else
    echo -e "${RED}✗ Errore nella creazione del database${NC}"
    exit 1
fi

# Test connessione
echo ""
echo -e "${YELLOW}Test connessione database...${NC}"
PGPASSWORD=${DB_PASSWORD} psql -h localhost -U ${DB_USER} -d ${DB_NAME} -c "SELECT version();" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Connessione database riuscita${NC}"
else
    echo -e "${RED}✗ Impossibile connettersi al database${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}=== Setup Database Completato ===${NC}"
echo ""
echo "Database: ${DB_NAME}"
echo "Utente: ${DB_USER}"
echo "Password: ${DB_PASSWORD}"
echo ""
echo -e "${YELLOW}IMPORTANTE: Cambia la password in produzione!${NC}"
echo ""

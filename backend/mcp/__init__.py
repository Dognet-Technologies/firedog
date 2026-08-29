"""
Server MCP (Model Context Protocol) embedded nel backend FireDog.

Implementa il contratto cross-prodotto Dognet Technologies
(sentinelcore: docs/11-mcp-contract.md): JSON-RPC 2.0 su POST /api/mcp,
autenticazione Bearer con API key per-utente. Tool read-only (phase 1) +
tool di scrittura per regole firewall e IP bloccati, riservati al ruolo
Admin (phase 2).
"""

__version__ = "1.1.0"

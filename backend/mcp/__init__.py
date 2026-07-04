"""
Server MCP (Model Context Protocol) embedded nel backend FireDog.

Implementa il contratto cross-prodotto Dognet Technologies
(sentinelcore: docs/11-mcp-contract.md): JSON-RPC 2.0 su POST /api/mcp,
autenticazione Bearer con API key per-utente, tool read-only (phase 1).
"""

__version__ = "1.0.0"

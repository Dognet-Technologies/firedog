"""
Dispatcher JSON-RPC 2.0 per l'endpoint MCP (contratto §2/§5).

Separazione errori (contratto §5):
- errori di protocollo/uso (metodo sconosciuto, parametri invalidi) →
  errore JSON-RPC (-32601 / -32602 / -32600);
- errori di esecuzione del tool (DB, downstream) → risultato tools/call
  con isError: true e messaggio generico; la causa è loggata server-side.
"""

import json
import logging

from . import __version__
from .tools import ToolParamError, ToolPermissionError, call_tool, public_tool_list

logger = logging.getLogger(__name__)

JSONRPC_VERSION = "2.0"
DEFAULT_PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "firedog-mcp"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602


class JsonRpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _error_response(request_id, code, message):
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _success_response(request_id, result):
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def _handle_initialize(params, user):
    return {
        "protocolVersion": params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": SERVER_NAME, "version": __version__},
    }


def _handle_tools_call(params, user):
    name = params.get("name")
    if not name or not isinstance(name, str):
        raise JsonRpcError(INVALID_PARAMS, "Parametro 'name' mancante o non valido.")
    arguments = params.get("arguments") or {}

    try:
        payload = call_tool(name, arguments, user)
    except ToolParamError as exc:
        raise JsonRpcError(INVALID_PARAMS, str(exc))
    except ToolPermissionError as exc:
        # Non è un errore di protocollo: il tool esiste, i parametri sono
        # validi, ma il ruolo dell'utente non basta (contratto §5).
        return {
            "content": [{"type": "text", "text": str(exc)}],
            "isError": True,
        }
    except Exception:
        # Errore di esecuzione: dettaglio nei log, messaggio generico al client
        logger.exception("Errore di esecuzione del tool MCP '%s'", name)
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Errore interno durante l'esecuzione del tool.",
                }
            ],
            "isError": True,
        }

    return {
        "content": [
            {"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}
        ],
        "isError": False,
    }


def dispatch_single(message, user):
    """
    Gestisce un singolo messaggio JSON-RPC.
    Ritorna il dict di risposta, oppure None se è una notifica (nessun id).
    """
    if not isinstance(message, dict):
        return _error_response(None, INVALID_REQUEST, "Richiesta non valida.")

    request_id = message.get("id")
    is_notification = "id" not in message
    method = message.get("method")

    if message.get("jsonrpc") != JSONRPC_VERSION or not isinstance(method, str):
        if is_notification:
            return None
        return _error_response(
            request_id, INVALID_REQUEST, "Richiesta JSON-RPC non valida."
        )

    params = message.get("params") or {}
    if not isinstance(params, dict):
        if is_notification:
            return None
        return _error_response(
            request_id, INVALID_PARAMS, "params deve essere un oggetto."
        )

    if method.startswith("notifications/"):
        # es. notifications/initialized: nessuna risposta
        return None

    try:
        if method == "initialize":
            result = _handle_initialize(params, user)
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": public_tool_list()}
        elif method == "tools/call":
            result = _handle_tools_call(params, user)
        else:
            raise JsonRpcError(METHOD_NOT_FOUND, f"Metodo non trovato: {method}.")
    except JsonRpcError as exc:
        if is_notification:
            return None
        return _error_response(request_id, exc.code, exc.message)

    if is_notification:
        return None
    return _success_response(request_id, result)


def dispatch(body_bytes, user):
    """
    Gestisce il body raw della richiesta (singola o batch).

    Ritorna (payload, http_status): payload None con status 202 quando la
    richiesta è composta solo da notifiche (contratto §2, batching).
    """
    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _error_response(None, PARSE_ERROR, "JSON non valido."), 200

    if isinstance(data, list):
        if not data:
            return _error_response(None, INVALID_REQUEST, "Batch vuoto."), 200
        responses = [
            r for r in (dispatch_single(m, user) for m in data) if r is not None
        ]
        if not responses:
            return None, 202
        return responses, 200

    response = dispatch_single(data, user)
    if response is None:
        return None, 202
    return response, 200

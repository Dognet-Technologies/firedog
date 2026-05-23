"""GeoIP lookup helper.

Wrapper sopra geoip2 con un Reader globale lazy-loaded così non leggiamo
il file mmdb ad ogni chiamata. Path configurabile via env GEOIP_DB_PATH
o default a /opt/sentinelsuite/firedog/geoip/dbip-country-lite.mmdb.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import geoip2.database
import geoip2.errors

logger = logging.getLogger("firedog.geoip")

DEFAULT_DB_PATH = Path("/opt/sentinelsuite/firedog/geoip/dbip-country-lite.mmdb")

_reader: Optional[geoip2.database.Reader] = None
_reader_path: Optional[Path] = None
_reader_failed: bool = False


def _get_reader() -> Optional[geoip2.database.Reader]:
    """Apre il Reader una volta sola. Restituisce None se il DB manca."""
    global _reader, _reader_path, _reader_failed
    if _reader is not None:
        return _reader
    if _reader_failed:
        return None
    db_path = Path(os.environ.get("GEOIP_DB_PATH", str(DEFAULT_DB_PATH)))
    if not db_path.exists():
        logger.warning("GeoIP DB non trovato in %s — country_code resterà vuoto", db_path)
        _reader_failed = True
        return None
    try:
        _reader = geoip2.database.Reader(str(db_path))
        _reader_path = db_path
        logger.info("GeoIP DB caricato da %s", db_path)
        return _reader
    except Exception as e:
        logger.error("Impossibile aprire GeoIP DB %s: %s", db_path, e)
        _reader_failed = True
        return None


def lookup_country(ip: str) -> tuple[str, str]:
    """Ritorna (country_code, country_name) per un IP, o ("", "") se non risolto."""
    reader = _get_reader()
    if reader is None:
        return ("", "")
    try:
        r = reader.country(ip)
        return (r.country.iso_code or "", r.country.name or "")
    except geoip2.errors.AddressNotFoundError:
        return ("", "")
    except Exception as e:
        logger.debug("GeoIP lookup fallito per %s: %s", ip, e)
        return ("", "")

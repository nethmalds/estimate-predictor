"""Production-grade three-file logging setup.

Log file routing
----------------
logs/app.log      — services.*, application.*, app.*, core.*  (app code)
logs/infra.log    — uvicorn.*, httpx, sqlalchemy.*, alembic    (framework noise)
logs/payloads.log — "payload" logger                            (large data dumps)

All three use RotatingFileHandler (10 MB / 5 backups).
Relative paths are resolved from the backend root (the directory that contains
this package tree), so the server can be launched from any working directory.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# backend/core/logging/logger.py → .parents[2] == backend/
_BACKEND_ROOT: Path = Path(__file__).resolve().parents[2]

_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_BACKUPS = 5

# Logger-name prefixes that belong in infra.log only
_INFRA_PREFIXES = ("uvicorn", "httpx", "sqlalchemy", "alembic", "starlette")

_PAYLOAD_NAME = "payload"

# ---------------------------------------------------------------------------
# Module-level state  (all mutations protected by _LOCK)
# ---------------------------------------------------------------------------
_LOCK = threading.Lock()
_payload_logger: logging.Logger | None = None
_initialized: bool = False


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve(path: str) -> Path:
    """Return an absolute Path.  Relative paths are anchored to _BACKEND_ROOT."""
    p = Path(path)
    return p if p.is_absolute() else _BACKEND_ROOT / p


def _make_handler(path: Path, level: int) -> RotatingFileHandler:
    path.parent.mkdir(parents=True, exist_ok=True)
    h = RotatingFileHandler(
        path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUPS,
        encoding="utf-8",
        delay=True,   # defer file open until first write — avoids Windows lock conflicts on --reload
    )
    h.setLevel(level)
    h.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))
    return h


def _drop_rotating(logger: logging.Logger) -> None:
    """Close and remove every RotatingFileHandler from *logger*.

    Prevents handler accumulation when uvicorn reloads or setup_logging is
    called more than once in the same process.
    """
    for h in list(logger.handlers):
        if isinstance(h, RotatingFileHandler):
            try:
                h.close()
            except Exception:  # noqa: BLE001
                pass
            logger.removeHandler(h)


class _AppOnlyFilter(logging.Filter):
    """Pass only app-level records; block infra-namespace and payload records."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        name = record.name
        if name == _PAYLOAD_NAME or name.startswith(_PAYLOAD_NAME + "."):
            return False
        return not any(
            name == p or name.startswith(p + ".") for p in _INFRA_PREFIXES
        )


# ---------------------------------------------------------------------------
# Core setup  (runs while _LOCK is held)
# ---------------------------------------------------------------------------

def _configure(
    level: str,
    app_path: Path | None,
    infra_path: Path | None,
    payload_path: Path | None,
) -> None:
    """Wire up all three log destinations.  Must be called while holding _LOCK."""
    global _payload_logger, _initialized  # noqa: PLW0603

    log_level = getattr(logging, level.upper(), logging.INFO)
    fmt = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    # ── 1. Root logger  ────────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Tear down any previous handlers (handles re-entry on --reload)
    for h in list(root.handlers):
        try:
            h.close()
        except Exception:  # noqa: BLE001
            pass
    root.handlers.clear()

    # stdout — app-level lines only, at the configured level
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(log_level)
    sh.setFormatter(fmt)
    sh.addFilter(_AppOnlyFilter())
    root.addHandler(sh)

    # app.log — app-level lines only
    if app_path:
        ah = _make_handler(app_path, log_level)
        ah.addFilter(_AppOnlyFilter())
        root.addHandler(ah)

    # ── 2. Infra loggers  ──────────────────────────────────────────────────
    if infra_path:
        ih = _make_handler(infra_path, logging.DEBUG)
        for prefix in _INFRA_PREFIXES:
            lg = logging.getLogger(prefix)
            _drop_rotating(lg)       # prevent duplication across reloads
            lg.addHandler(ih)
            lg.propagate = False     # never bubble up to root / app.log
            lg.setLevel(logging.DEBUG)

    # ── 3. Payload logger  ─────────────────────────────────────────────────
    _payload_logger = logging.getLogger(_PAYLOAD_NAME)
    _drop_rotating(_payload_logger)
    _payload_logger.propagate = False   # never leak into app.log / stdout
    _payload_logger.setLevel(logging.DEBUG)

    if payload_path:
        ph = _make_handler(payload_path, logging.DEBUG)
        _payload_logger.addHandler(ph)
        # Write a startup marker so the file is never empty after init
        _payload_logger.debug(
            "STEP=__logging_init__ | %s",
            json.dumps({"app": str(app_path), "infra": str(infra_path), "payload": str(payload_path)}),
        )

    _initialized = True

    logging.getLogger("core.logging.logger").info(
        "logging_ready level=%s app=%s infra=%s payload=%s",
        level,
        app_path,
        infra_path,
        payload_path,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_logging(
    level: str | None = None,
    log_file: str | None = None,
    log_file_infra: str | None = None,
    log_file_payload: str | None = None,
) -> None:
    """Configure (or reconfigure) the three-file logging system.

    Thread-safe and idempotent — safe to call multiple times or from multiple
    threads.  Relative paths are resolved from the backend root directory.

    Parameters
    ----------
    level:            Root log level (e.g. ``"INFO"``, ``"DEBUG"``).
    log_file:         Path for ``app.log``   (services / application / app).
    log_file_infra:   Path for ``infra.log`` (uvicorn / httpx / sqlalchemy).
    log_file_payload: Path for ``payloads.log`` (pipeline step data dumps).
    """
    with _LOCK:
        _configure(
            level or "INFO",
            _resolve(log_file) if log_file else None,
            _resolve(log_file_infra) if log_file_infra else None,
            _resolve(log_file_payload) if log_file_payload else None,
        )


def ensure_logging() -> None:
    """Initialise logging from settings exactly once.  No-op when already done.

    Uses double-checked locking so concurrent callers never run ``_configure``
    twice and never block each other after the first successful init.
    """
    if _initialized:
        return
    with _LOCK:
        if _initialized:          # second check inside the lock
            return
        try:
            from core.config.settings import settings  # noqa: PLC0415
        except Exception:  # noqa: BLE001
            # Settings unavailable (e.g. early import in unit tests).
            # Fall back to a basic stdout handler so nothing is lost.
            logging.basicConfig(
                level=logging.INFO,
                format=_FMT,
                datefmt=_DATE_FMT,
                stream=sys.stdout,
            )
            return
        _configure(
            settings.log_level,
            _resolve(settings.log_file) if settings.log_file else None,
            _resolve(settings.log_file_infra) if settings.log_file_infra else None,
            _resolve(settings.log_file_payload) if settings.log_file_payload else None,
        )


def get_logger(name: str) -> logging.Logger:
    """Return a named app logger.  Triggers lazy initialisation on the first call."""
    ensure_logging()
    return logging.getLogger(name)


def get_payload_logger() -> logging.Logger:
    """Return the dedicated payload logger (writes to ``payloads.log`` only)."""
    if _payload_logger is None:
        ensure_logging()
    return _payload_logger or logging.getLogger(_PAYLOAD_NAME)


def log_payload(step_name: str, output: Any) -> None:
    """Serialise *output* as compact JSON and write one DEBUG line to payloads.log.

    This is the canonical way for pipeline stages to record their full output
    without polluting app.log or stdout.
    """
    pl = get_payload_logger()
    if not pl.isEnabledFor(logging.DEBUG):
        return
    try:
        body = json.dumps(output, default=str, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        body = repr(output)
    pl.debug("STEP=%s | %s", step_name, body)

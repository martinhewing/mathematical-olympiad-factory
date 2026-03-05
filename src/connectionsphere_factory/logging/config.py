"""
connectionsphere_factory/logging/config.py

Structured logging with structlog.
Development: coloured console output.
Production:  JSON lines (journald / log shipper readable).
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(log_level: str = "INFO", json_format: bool = False) -> None:
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        format = "%(message)s",
        stream = sys.stdout,
        level  = numeric_level,
        force  = True,
    )
    logging.getLogger().setLevel(numeric_level)

    for name in ("httpx", "httpcore", "urllib3", "asyncio", "anthropic"):
        logging.getLogger(name).setLevel(logging.WARNING)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors            = shared_processors,
        wrapper_class         = structlog.stdlib.BoundLogger,
        logger_factory        = structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use = False,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_request_context(**kwargs: Any) -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()

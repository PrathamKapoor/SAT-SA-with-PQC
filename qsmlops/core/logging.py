"""Structured logging for the platform.

Logs go to stderr (or a file) as JSON-per-line in production profiles and as
concise human-readable lines in development. Log fields are stable so future
telemetry/observability integration can index them without parsing prose.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from typing import IO

_RECORD_ATTRS = ("event", "service", "actor", "resource", "level_name", "code")


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        extra = {
            name: getattr(record, name)
            for name in _RECORD_ATTRS
            if isinstance(getattr(record, name, None), str)
        }
        doc = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%S%z", time.gmtime(record.created)
            )
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **extra,
        }
        if record.exc_info:
            doc["exception"] = self.formatException(record.exc_info)
        return json.dumps(doc, separators=(",", ":"), ensure_ascii=False)


def configure_logging(
    level: str = "INFO",
    *,
    json_format: bool = True,
    stream: IO[str] | None = None,
) -> logging.Logger:
    """Configure the root ``qsmlops`` logger and return it.

    Idempotent: calling again replaces handlers (safe for tests and for
    reconfiguring when the active environment profile changes).
    """
    logger = logging.getLogger("qsmlops")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    if json_format:
        handler.setFormatter(_JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Child logger under the ``qsmlops`` namespace."""
    if name == "qsmlops" or name.startswith("qsmlops."):
        return logging.getLogger(name)
    return logging.getLogger(f"qsmlops.{name}")

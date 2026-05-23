"""Structured JSON logging."""
from __future__ import annotations

import logging
import sys

from pythonjsonlogger import jsonlogger


def configure(level: str = "INFO") -> None:
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    ))
    root.addHandler(handler)
    root.setLevel(level)

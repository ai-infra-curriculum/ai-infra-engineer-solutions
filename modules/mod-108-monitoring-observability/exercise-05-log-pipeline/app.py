"""Structured JSON logger compatible with the Vector pipeline."""
from __future__ import annotations

import logging
import time

from pythonjsonlogger import jsonlogger


class TraceJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["service"] = "iris-api"
        log_record["timestamp"] = time.time()
        log_record.setdefault("trace_id", getattr(record, "trace_id", ""))
        log_record.setdefault("span_id", getattr(record, "span_id", ""))


def configure():
    h = logging.StreamHandler()
    h.setFormatter(TraceJsonFormatter())
    root = logging.getLogger()
    root.handlers = [h]
    root.setLevel(logging.INFO)


def main():
    configure()
    log = logging.getLogger("predict")
    for i in range(100):
        log.info("prediction made", extra={
            "model_version": "v3", "latency_ms": 40 + i % 20, "user_id": i % 7,
        })
        time.sleep(0.05)
    log.error("downstream timeout", extra={"upstream": "feature-store"})


if __name__ == "__main__":
    main()

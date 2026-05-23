"""Append-only audit log of promotions. Stored as JSONL in S3 or local file."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path


LOG = Path(os.environ.get("AUDIT_LOG", "audit.jsonl"))


def log_event(event: dict):
    event["ts"] = time.time()
    with LOG.open("a") as f:
        f.write(json.dumps(event) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["log", "tail"])
    p.add_argument("--name")
    p.add_argument("--version")
    p.add_argument("--to")
    p.add_argument("--actor")
    p.add_argument("--reason", default="")
    args = p.parse_args()

    if args.action == "log":
        log_event(dict(name=args.name, version=args.version, to=args.to,
                        actor=args.actor, reason=args.reason))
    else:
        for line in LOG.read_text().splitlines()[-20:]:
            print(line)


if __name__ == "__main__":
    main()

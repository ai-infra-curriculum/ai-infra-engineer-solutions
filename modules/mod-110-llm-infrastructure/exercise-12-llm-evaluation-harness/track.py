"""Append scoring results to history; alert on regression."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


HISTORY = Path("history.jsonl")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--score", type=float, required=True)
    p.add_argument("--prompt-version", required=True)
    args = p.parse_args()

    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "prompt_version": args.prompt_version,
        "score": args.score,
    }
    with HISTORY.open("a") as f:
        f.write(json.dumps(entry) + "\n")

    # Regression check vs rolling avg of last 7 entries
    history = [json.loads(l) for l in HISTORY.read_text().splitlines()]
    if len(history) > 7:
        recent = history[-8:-1]
        avg = sum(h["score"] for h in recent) / len(recent)
        if args.score < avg - 0.05:
            print(f"⚠ REGRESSION: {args.score:.3f} < recent avg {avg:.3f}")


if __name__ == "__main__":
    main()

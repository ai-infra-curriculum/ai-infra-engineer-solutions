"""Quarterly compliance report aggregating audit results across all models."""
from __future__ import annotations

import json
import sys
from collections import Counter


def main():
    """Reads audit results JSON (one per model) from stdin, prints a summary."""
    audits = [json.loads(line) for line in sys.stdin if line.strip()]
    counts = Counter(a["verdict"] for a in audits)
    total = len(audits)

    print("# Reproducibility Compliance Report")
    print()
    print(f"Models audited: {total}")
    for verdict in ("REPRODUCIBLE", "PARTIAL", "NOT_REPRODUCIBLE"):
        print(f"  {verdict}: {counts[verdict]} ({counts[verdict]/total*100:.0f}%)")
    print()
    print("## Failing models")
    for a in audits:
        if a["verdict"] != "REPRODUCIBLE":
            failed = [k for k, v in a["checks"].items() if not v]
            print(f"- {a['model']} v{a['version']}: missing {', '.join(failed)}")


if __name__ == "__main__":
    main()

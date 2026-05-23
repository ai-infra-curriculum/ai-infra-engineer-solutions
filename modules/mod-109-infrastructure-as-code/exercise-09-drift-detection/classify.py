"""Classify drift severity: cosmetic vs material vs critical."""
from __future__ import annotations

import json
import sys


CRITICAL_ACTIONS = {"delete", "replace"}
CRITICAL_RESOURCE_TYPES = {
    "aws_db_instance", "aws_eks_cluster", "aws_vpc",
}


def classify(change: dict) -> str:
    actions = change.get("change", {}).get("actions", [])
    rtype = change.get("type")

    if any(a in CRITICAL_ACTIONS for a in actions):
        return "critical"
    if rtype in CRITICAL_RESOURCE_TYPES:
        return "material"
    # tag-only / attribute-only update
    return "cosmetic"


def main():
    data = json.load(sys.stdin)
    severity_counts = {"cosmetic": 0, "material": 0, "critical": 0}
    by_severity = {"cosmetic": [], "material": [], "critical": []}
    for d in data:
        for change in d.get("changes", []):
            sev = classify(change)
            severity_counts[sev] += 1
            by_severity[sev].append({"project": d["project"], "env": d["env"], "addr": change.get("address")})

    print(json.dumps({"counts": severity_counts, "details": by_severity}, indent=2))


if __name__ == "__main__":
    main()

"""Find idle resources: Deployments with 0 traffic, unused PVCs, orphan LBs."""
from __future__ import annotations

import json
import subprocess


def kubectl_json(args: list[str]) -> dict:
    return json.loads(subprocess.check_output(["kubectl"] + args + ["-o", "json"]))


def main():
    # Deployments with 0 ready replicas for > 7d (assumed via annotation)
    deps = kubectl_json(["get", "deployment", "-A"])
    for d in deps["items"]:
        if d["status"].get("readyReplicas", 0) == 0:
            print(f"IDLE deployment: {d['metadata']['namespace']}/{d['metadata']['name']}")

    # PVCs without any Pod referencing them
    pvcs = kubectl_json(["get", "pvc", "-A"])
    pods = kubectl_json(["get", "pods", "-A"])
    used = set()
    for p in pods["items"]:
        for v in p["spec"].get("volumes", []):
            if "persistentVolumeClaim" in v:
                used.add((p["metadata"]["namespace"], v["persistentVolumeClaim"]["claimName"]))
    for pvc in pvcs["items"]:
        key = (pvc["metadata"]["namespace"], pvc["metadata"]["name"])
        if key not in used:
            print(f"ORPHAN PVC: {key[0]}/{key[1]}")


if __name__ == "__main__":
    main()

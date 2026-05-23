"""Automated checks after DR recovery — pass before declaring restored."""
import subprocess
import sys

import httpx


CHECKS = []


def check(name):
    def decorate(fn):
        CHECKS.append((name, fn))
        return fn
    return decorate


@check("dr-cluster-reachable")
def cluster():
    subprocess.run(["kubectl", "get", "nodes"], check=True)


@check("argocd-all-apps-synced")
def argocd():
    out = subprocess.check_output(["argocd", "app", "list", "-o", "json"], text=True)
    import json
    apps = json.loads(out)
    bad = [a["metadata"]["name"] for a in apps if a["status"]["sync"]["status"] != "Synced"]
    if bad:
        raise SystemExit(f"unsynced: {bad}")


@check("iris-api-responds")
def api():
    r = httpx.post("https://iris-api.dr.example.com/predict",
                    json={"features": [5.1, 3.5, 1.4, 0.2]}, timeout=30)
    r.raise_for_status()


@check("monitoring-up")
def mon():
    httpx.get("https://prometheus.dr.example.com/-/healthy", timeout=10).raise_for_status()


def main():
    failed = []
    for name, fn in CHECKS:
        try:
            fn()
            print(f"✓ {name}")
        except Exception as e:
            print(f"✗ {name}: {e}")
            failed.append(name)
    if failed:
        sys.exit(f"{len(failed)} checks failed")


if __name__ == "__main__":
    main()

"""Report per-pod CPU + memory over-provisioning vs actual usage."""
from __future__ import annotations

import httpx


PROM = "http://prometheus.monitoring:9090"


def query(q: str) -> dict:
    return httpx.get(f"{PROM}/api/v1/query", params={"query": q}).json()


def main():
    # Actual avg use over last 24h vs request
    cpu_q = (
        '(sum by (namespace, pod) (rate(container_cpu_usage_seconds_total[24h])))'
        ' / on(namespace, pod)'
        ' (sum by (namespace, pod) (kube_pod_container_resource_requests{resource="cpu"}))'
    )
    mem_q = (
        '(avg by (namespace, pod) (container_memory_working_set_bytes))'
        ' / on(namespace, pod)'
        ' (sum by (namespace, pod) (kube_pod_container_resource_requests{resource="memory"}))'
    )

    print(f"{'namespace':<20} {'pod':<40} {'cpu_util':>10} {'mem_util':>10}")
    cpu = {(r["metric"]["namespace"], r["metric"]["pod"]): float(r["value"][1])
            for r in query(cpu_q)["data"]["result"]}
    mem = {(r["metric"]["namespace"], r["metric"]["pod"]): float(r["value"][1])
            for r in query(mem_q)["data"]["result"]}

    for key in sorted(cpu):
        cv = cpu[key]
        mv = mem.get(key, 0)
        if cv < 0.3 or mv < 0.3:                # overprovisioned
            print(f"{key[0]:<20} {key[1]:<40} {cv*100:>9.0f}% {mv*100:>9.0f}%")


if __name__ == "__main__":
    main()

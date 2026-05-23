# Cost vs Coverage — Trade-off Matrix

Sample numbers from a mid-size cluster (200 services, 800 pods).

| Technique | Before | After | Savings | Coverage loss |
|---|---|---|---|---|
| Cardinality reduction (relabel + allowlist) | 4.1M series | 1.2M series | 70% on Prom | Lost per-pod-IP, per-uid grouping. Replaced with pod-prefix label. |
| Trace tail sampling (100% errors + slow, 1% baseline) | 50M spans/day | 5M spans/day | 90% on Tempo | None for diagnosis; lost statistical sampling of healthy traffic baseline (use metrics instead). |
| Metric retention tiering (1m → 1h after 24h) | 90d at 1m | 24h at 1m + 90d at 1h | 60% on Prom storage | Cannot answer per-pod-per-second queries beyond 24h. |
| Log retention by level (7d INFO / 30d WARN / 90d ERROR) | 30d all | tiered | 65% on Loki | Cannot scan INFO logs > 7d (rarely needed). |
| S3 lifecycle (IA at 30d, Glacier at 90d) | STANDARD always | tiered | ~70% on long-term storage | Restore latency 1-12h for Glacier (acceptable for compliance archives). |

## Combined result

- **Total observability cost before:** $42K/month
- **Total after:** $16K/month
- **Reduction:** 62%
- **Coverage loss:** ~3% (limited to long-tail historical detail)
- **Critical signals preserved:** all alerts, all SLO budgets, all error traces, all WARN/ERROR logs

## What we deliberately did NOT cut

- Per-service RPS (essential for capacity planning)
- Histograms for latency SLI (any reduction breaks the SLO calc)
- Trace sampling rate during incidents (auto-bumped via runtime config)
- Recent (24h) high-fidelity data (essential for debugging)

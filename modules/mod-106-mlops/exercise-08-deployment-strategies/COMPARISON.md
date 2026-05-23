# Strategy Comparison (measured on iris-api, 6 replicas)

| Strategy | Rollout time | Blast radius if v0.6 is broken | Complexity | Best for |
|---|---|---|---|---|
| Rolling | ~90s | up to 25% of pods serving bad version simultaneously | low | low-risk minor updates |
| Blue-Green | ~5min | full traffic flip if you don't catch it before switch | medium | major version changes; easy rollback |
| Canary (Argo) | ~30-45min | <10% of traffic until analysis passes | high | risky model updates with auto-revert on regression |
| Shadow | indefinite | 0% — candidate never serves real users | medium | breaking model changes; latency/accuracy validation pre-launch |

## When to use each

- **Rolling**: routine deploys (default).
- **Blue-Green**: schema breaking changes; needs full v0.6 fleet ready before cutover.
- **Canary**: model accuracy might regress; want automated rollback.
- **Shadow**: new model architecture; want production traffic to validate without risk.

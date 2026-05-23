# Multi-Tenant LLM Platform — Solution

Reference for [learning exercise-07](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-110-llm-infrastructure/exercises/exercise-07-multi-tenant-llm-platform/README.md).

## Architecture

```
┌──── ingress ────┐
│ auth middleware │  ←  per-tenant API key → tenant_id
│ rate limiter    │  ←  per-tenant RPM cap
│ token meter     │  ←  per-tenant monthly token budget
│ router          │  ←  request → vLLM upstream (by model)
└────────┬────────┘
         ▼
  vLLM upstream (shared, multi-adapter)
```

## Files

- `gateway.py` — FastAPI ingress with auth + rate limit + metering
- `tenants.yaml` — tenant definitions
- `usage_store.py` — Redis-backed per-tenant counters
- `quota_check.py` — token budget enforcement

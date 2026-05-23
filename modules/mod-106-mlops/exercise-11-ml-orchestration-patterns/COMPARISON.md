# Orchestration Pattern Trade-offs

| Pattern | Code per model | Visibility | Failure isolation | Best when |
|---|---|---|---|---|
| DAG-per-model | linear | high (1 DAG view per model) | excellent | few models, very different shape |
| Parametric DAG | O(1) | medium (1 DAG handles all) | shared failure path | many similar models |
| Event-driven | O(1) per source | low (chains across systems) | per-event | irregular data arrival |
| Continuous training | O(1) | medium | depends on gate | drift-sensitive models |

## Hybrid recommendation

Most mature platforms run a mix:
- Parametric DAG for the bulk of similar models (recs, ltv, churn).
- DAG-per-model for the 2-3 with bespoke pipelines (fraud, abuse).
- Event-driven for sources with irregular cadence (vendor partner feeds).
- Continuous training for the model with the highest business cost-of-drift.

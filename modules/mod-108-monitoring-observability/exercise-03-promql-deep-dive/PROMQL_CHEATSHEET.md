# PromQL Cheatsheet — 25 worked queries

Reference for [learning exercise-03](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-108-monitoring-observability/exercises/exercise-03-promql-deep-dive/README.md).

Each query is annotated with what it tells you and when to reach for it.

## Counters and rates (1-5)

```promql
# 1. Total HTTP requests in the last hour
sum(increase(http_requests_total[1h]))
# → coarse volume sanity check; useful for "did anything happen?"

# 2. Per-second rate, grouped by method + status, last 5m
sum by (method, status) (rate(http_requests_total[5m]))
# → live RPS panel; status=~"5.." subset = error budget burn

# 3. Top 5 services by traffic, last 10m
topk(5, sum by (service) (rate(http_requests_total[10m])))
# → who is loud right now

# 4. irate vs rate
# rate = average over window (smooth)
# irate = last two samples (jagged but responsive)
irate(http_requests_total[5m])    # for alerting on spikes
rate(http_requests_total[5m])     # for dashboards

# 5. Per-pod CPU usage rate
sum by (pod) (rate(container_cpu_usage_seconds_total{pod=~".+"}[2m]))
```

## Histograms and quantiles (6-10)

```promql
# 6. p50 latency, iris-api, last 5m
histogram_quantile(0.50,
  sum by (le) (rate(http_request_duration_seconds_bucket{job="iris-api"}[5m])))

# 7. p95 latency by URL path
histogram_quantile(0.95,
  sum by (le, path) (rate(http_request_duration_seconds_bucket{job="iris-api"}[5m])))

# 8. Latency spread (tail risk indicator)
histogram_quantile(0.95, ...) - histogram_quantile(0.50, ...)

# 9. Requests slower than 500ms in last 10m
sum(increase(http_request_duration_seconds_bucket{le="+Inf"}[10m]))
  -
sum(increase(http_request_duration_seconds_bucket{le="0.5"}[10m]))

# 10. SLI: fraction of requests under 200ms
sum(rate(http_request_duration_seconds_bucket{le="0.2"}[5m]))
  /
sum(rate(http_request_duration_seconds_count[5m]))
```

## Aggregations and operators (11-15)

```promql
# 11. Per-pod average request rate
sum(rate(http_requests_total[5m])) / count(up{job="iris-api"} == 1)

# 12. Container memory as % of limit
container_memory_working_set_bytes
  /
container_spec_memory_limit_bytes * 100

# 13. Top 3 namespaces by CPU
topk(3, sum by (namespace) (rate(container_cpu_usage_seconds_total[5m])))

# 14. Predict_linear: disk fill in 4h
predict_linear(node_filesystem_avail_bytes[1h], 4 * 3600) < 0
# → alert when projected to hit 0 in 4h

# 15. Deployment fully Ready
sum(kube_deployment_status_replicas_ready{deployment="iris-api"})
  /
sum(kube_deployment_spec_replicas{deployment="iris-api"}) == 1
```

## Subqueries and recording rules (16-20)

```promql
# 16. Max p95 over any 5m window in past hour (subquery)
max_over_time(
  histogram_quantile(0.95,
    sum by (le) (rate(http_request_duration_seconds_bucket[5m])))[1h:5m])

# 17. Nested aggregation
avg_over_time(
  (avg_over_time(rate(http_requests_total[1m])[1h:1m]))[15m:1m])

# 18-19. Recording rules
# in rules.yml:
# groups:
#   - name: api
#     rules:
#       - record: path:http_requests:rate1m
#         expr: sum by (path) (rate(http_requests_total[1m]))
#       - record: cluster:http_errors:ratio
#         expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# 20. Slow ad-hoc query made fast by #18
sum by (path) (rate(http_requests_total[1m]))            # ad-hoc: scan all
path:http_requests:rate1m                                # recording: pre-aggregated, ~100x faster
```

## Joins, label_replace, advanced (21-25)

```promql
# 21. Join HPA target with current CPU
kube_horizontalpodautoscaler_status_current_metrics_average_value
  * on(horizontalpodautoscaler) group_left(targetref_name)
kube_horizontalpodautoscaler_info

# 22. Rewrite labels with label_replace (e.g., extract service from pod name)
label_replace(up, "service", "$1", "pod", "(.*)-[a-z0-9]{5}-[a-z0-9]{5}")

# 23. count_over_time: how many distinct samples seen in window
count_over_time(up[5m])

# 24. absent: alert when a metric stops being produced
absent(up{job="iris-api"})

# 25. resets() for counter resets (pod restart detector)
changes(kube_pod_container_status_restarts_total[1h]) > 0
```

## Final tips

- Always filter early (`{job=...}`) — saves cardinality cost.
- Don't take `rate()` of an already-aggregated counter; aggregate the rates instead.
- Histograms: `histogram_quantile()` AFTER `sum by (le)`, not before — otherwise you get nonsense.

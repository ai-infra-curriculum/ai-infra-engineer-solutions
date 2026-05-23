# "What upstreams produced this column?"

Marquez exposes a REST API + a CLI. To trace upstream lineage for
`features.recs_v1.user_purchase_count_30d`:

```bash
curl http://marquez:5000/api/v1/lineage \
  -G --data-urlencode "nodeId=dataset:warehouse:features.recs_v1" \
  --data-urlencode "depth=10" \
  --data-urlencode "direction=upstream" | jq .
```

In the UI: open the dataset, click "Lineage" — the graph shows every Airflow
task and dbt model that contributed.

## Column-level (with dbt + OpenLineage)

```sql
-- In dbt, with `dbt-osmosis` or column-level lineage extension:
SELECT * FROM marquez.column_lineage
WHERE downstream_dataset = 'features.recs_v1'
  AND downstream_column  = 'user_purchase_count_30d';
```

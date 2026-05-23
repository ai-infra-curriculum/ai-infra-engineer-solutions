# ETL → ELT Migration with dbt — Solution

Reference for [learning exercise-10](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-105-data-pipelines/exercises/exercise-10-etl-to-elt-migration/README.md).

## Layout

```
exercise-10-etl-to-elt-migration/
├── README.md
├── dbt_project.yml, profiles.yml
├── models/
│   ├── sources.yml
│   ├── staging/stg_trips.sql, stg_zones.sql
│   ├── intermediate/int_trips_enriched.sql
│   └── marts/agg_trips_daily.sql
├── tests/assert_positive_fare.sql
└── airflow_dag.py            # invokes dbt build
```

Run locally against DuckDB:

```bash
pip install dbt-duckdb
dbt deps && dbt build
dbt docs generate && dbt docs serve
```

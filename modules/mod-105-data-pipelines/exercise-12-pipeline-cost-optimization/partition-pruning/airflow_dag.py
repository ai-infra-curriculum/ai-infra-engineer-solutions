"""Airflow DAG that scans only yesterday's partition — not the whole table."""
from datetime import datetime

from airflow.decorators import dag, task


@dag(dag_id="daily_aggregate", start_date=datetime(2026, 1, 1),
     schedule="0 4 * * *", catchup=False)
def daily_agg():
    @task
    def run(execution_date=None):
        day = execution_date.strftime("%Y-%m-%d")
        # Partition predicate prunes ~95% of scanned bytes.
        sql = f"""
            INSERT INTO marts.daily_revenue
            SELECT day, borough, SUM(total_amount) AS revenue
            FROM curated.trips_enriched
            WHERE day = '{day}'        -- <- enables pruning
            GROUP BY day, borough
        """
        print(sql)
    run()


daily_agg()

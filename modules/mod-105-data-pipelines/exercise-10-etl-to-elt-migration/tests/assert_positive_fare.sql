-- Singular test: every aggregate row must have positive average fare.
SELECT day, pu_borough, avg_fare
FROM {{ ref('agg_trips_daily') }}
WHERE avg_fare <= 0

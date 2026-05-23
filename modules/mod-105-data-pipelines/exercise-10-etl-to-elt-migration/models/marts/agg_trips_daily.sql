SELECT
  DATE_TRUNC('day', pickup_ts)     AS day,
  pu_borough,
  COUNT(*)                          AS trips,
  AVG(fare_amount)                  AS avg_fare,
  SUM(total_amount)                 AS revenue
FROM {{ ref('int_trips_enriched') }}
GROUP BY 1, 2

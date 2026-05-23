{{ config(materialized='view') }}

SELECT
  trip_id,
  user_id,
  pickup_ts,
  dropoff_ts,
  pu_location_id,
  do_location_id,
  fare_amount,
  total_amount
FROM {{ source('raw', 'trips') }}
WHERE fare_amount > 0
  AND pickup_ts IS NOT NULL

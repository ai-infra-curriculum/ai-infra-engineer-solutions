{{ config(materialized='view') }}

SELECT
  zone_id,
  zone_name,
  borough
FROM {{ source('raw', 'zones') }}

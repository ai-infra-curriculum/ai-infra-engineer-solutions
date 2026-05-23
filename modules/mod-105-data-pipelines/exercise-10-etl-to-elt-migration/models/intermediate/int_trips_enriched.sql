SELECT
  t.*,
  z.zone_name AS pu_zone_name,
  z.borough   AS pu_borough
FROM {{ ref('stg_trips') }} t
LEFT JOIN {{ ref('stg_zones') }} z ON z.zone_id = t.pu_location_id

CREATE OR REPLACE TABLE `hanuman-0001.curated.users`
CLUSTER BY country, state
OPTIONS (
  description = "thelook users, PII-minimized per docs/pii_inventory.md",
  labels = [("data_class", "internal"), ("source", "thelook"), ("layer", "curated")]
) AS
SELECT
  id                  AS user_id,
  DIV(age, 10) * 10   AS age_band,
  gender,
  city,               -- quasi: curated only, never in semantic
  state,
  country,
  traffic_source,
  created_at
FROM `hanuman-0001.raw_thelook.users`;
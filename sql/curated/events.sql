CREATE OR REPLACE TABLE `hanuman-0001.curated.events`
PARTITION BY DATE(created_at)
CLUSTER BY event_type, page_type
OPTIONS (
  description = "thelook events, PII-minimized per docs/pii_inventory.md",
  labels = [("data_class", "internal"), ("source", "thelook"), ("layer", "curated")]
) AS
WITH e AS (
  SELECT *, REGEXP_REPLACE(uri, r"[?#].*$", "") AS uri_path
  FROM `hanuman-0001.raw_thelook.events`
)
SELECT
  id                                                            AS event_id,
  user_id,
  session_id,
  sequence_number,
  created_at,
  city,                 -- quasi: curated only
  state,
  browser,
  traffic_source,
  event_type,
  uri_path,
  CASE
    WHEN STARTS_WITH(uri_path, "/product/")    THEN "product"
    WHEN STARTS_WITH(uri_path, "/department/") THEN "department"
    ELSE LTRIM(uri_path, "/")
  END                                                           AS page_type,
  REGEXP_EXTRACT(uri_path, r"^/department/([^/]+)")             AS department,
  REGEXP_EXTRACT(uri_path, r"/category/([^/]+)")                AS category,
  REGEXP_EXTRACT(uri_path, r"/brand/([^/]+)")                   AS brand,
  SAFE_CAST(REGEXP_EXTRACT(uri_path, r"^/product/(\d+)$") AS INT64) AS product_id,
  COALESCE(CAST(user_id AS STRING), session_id)                 AS privacy_unit
  -- dropped: ip_address, postal_code, raw uri
FROM e;
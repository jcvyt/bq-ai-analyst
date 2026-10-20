CREATE OR REPLACE VIEW `hanuman-0001.semantic.web_events`
OPTIONS (
  privacy_policy = '{"aggregation_threshold_policy": {"threshold": 10, "privacy_unit_column": "privacy_unit"}}',
  labels = [("data_class", "aggregate_only")]
) AS
SELECT
  privacy_unit,
  DATE(created_at)              AS event_date,
  EXTRACT(HOUR FROM created_at) AS event_hour,
  state, browser, traffic_source, event_type,
  page_type, department, category, brand, product_id
FROM `hanuman-0001.curated.events`;
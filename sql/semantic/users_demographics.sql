CREATE OR REPLACE VIEW `hanuman-0001.semantic.users_demographics`
OPTIONS (
  privacy_policy = '{"aggregation_threshold_policy": {"threshold": 10, "privacy_unit_column": "user_id"}}',
  labels = [("data_class", "aggregate_only")]
) AS
SELECT user_id, country, state, gender, age_band, traffic_source,
       DATE(created_at) AS signup_date
FROM `hanuman-0001.curated.users`;
CREATE OR REPLACE VIEW `hanuman-0001.ops_audit.v_query_cost_daily` AS
WITH rate AS (SELECT 6.25 AS usd_per_tib)  -- VERIFY current us-east4 on-demand list price; regional ≠ US multi-region
SELECT
  DATE(j.creation_time)                                        AS day,
  j.user_email                                                 AS principal,
  (SELECT value FROM UNNEST(j.labels) WHERE key = 'app')       AS app,
  (SELECT value FROM UNNEST(j.labels) WHERE key = 'component') AS component,
  j.statement_type,
  COUNT(*)                                       AS jobs,
  COUNTIF(j.error_result IS NOT NULL)            AS errored_jobs,
  COUNTIF(j.cache_hit)                           AS cache_hits,
  SUM(j.total_bytes_processed)                   AS bytes_processed,
  SUM(j.total_bytes_billed)                      AS bytes_billed,
  SUM(j.total_slot_ms)                           AS slot_ms,
  ROUND(SUM(j.total_bytes_billed) / POW(1024, 4) * ANY_VALUE(r.usd_per_tib), 4) AS est_list_cost_usd
FROM `region-us-east4`.INFORMATION_SCHEMA.JOBS_BY_PROJECT AS j
CROSS JOIN rate AS r
WHERE j.job_type = 'QUERY'
  AND j.statement_type != 'SCRIPT'          -- parent script jobs double-count their children
  AND j.creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)
GROUP BY day, principal, app, component, statement_type;
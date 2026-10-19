bq query --use_legacy_sql=false --location=us-east4 '
WITH total AS (SELECT COUNT(*) AS n FROM `hanuman-0001.raw_thelook.events`)
SELECT
  cl.record_location.field_id.name AS column_name,
  f.info_type.name                 AS info_type,
  f.likelihood,
  COUNT(*)                         AS findings,
  ROUND(100 * COUNT(*) / ANY_VALUE(total.n), 2) AS pct_of_table_rows
FROM `hanuman-0001.ops_audit.dlp_findings_events` AS f,
UNNEST(f.location.content_locations) AS cl,
total
WHERE f.job_name = "projects/hanuman-0001/locations/us-east4/dlpJobs/i-4215257027947443953"
GROUP BY 1, 2, 3
ORDER BY column_name, findings DESC'
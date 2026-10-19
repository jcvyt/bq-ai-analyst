bq query --use_legacy_sql=false --location=us-east4 '
SELECT c.column_name, c.data_type
FROM `hanuman-0001.raw_thelook.INFORMATION_SCHEMA.COLUMNS` AS c
WHERE c.table_name = "events"
  AND c.column_name NOT IN (
    SELECT DISTINCT cl.record_location.field_id.name
    FROM `hanuman-0001.ops_audit.dlp_findings_events` AS f,
    UNNEST(f.location.content_locations) AS cl
    WHERE f.job_name = "projects/hanuman-0001/locations/us-east4/dlpJobs/i-4215257027947443953")
ORDER BY c.ordinal_position'
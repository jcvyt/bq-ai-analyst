#!/usr/bin/env bash
set -euo pipefail

PROJECT=hanuman-0001
SRC=bigquery-public-data:thelook_ecommerce
US_BKT=gs://${PROJECT}-staging-us/thelook
E4_BKT=gs://${PROJECT}-staging-use4/thelook
TABLES=(distribution_centers products users orders order_items inventory_items events)
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
RECON=/tmp/recon_${RUN_ID}.csv
: > "$RECON"
declare -A SRC_ROWS

echo "== 1/3 extract to US staging =="
for t in "${TABLES[@]}"; do
  gcloud storage rm -r "${US_BKT}/${t}/**" 2>/dev/null || true   # idempotent reruns
  SRC_ROWS[$t]=$(bq show --format=json "${SRC}.${t}" | jq -r .numRows)
  bq --project_id=$PROJECT --location=US extract \
     --destination_format=PARQUET --compression=SNAPPY \
     "${SRC}.${t}" "${US_BKT}/${t}/part-*.parquet"
done

echo "== 2/3 rsync US -> us-east4 =="
gcloud storage rsync --recursive --delete-unmatched-destination-objects "${US_BKT}" "${E4_BKT}"

echo "== 3/3 load + reconcile =="
for t in "${TABLES[@]}"; do
  bq --project_id=$PROJECT --location=us-east4 load --replace \
     --source_format=PARQUET "raw_thelook.${t}" "${E4_BKT}/${t}/*.parquet"
  dst=$(bq --project_id=$PROJECT show --format=json "raw_thelook.${t}" | jq -r .numRows)
  status=$([ "${SRC_ROWS[$t]}" = "$dst" ] && echo MATCH || echo MISMATCH)
  echo "${RUN_ID},${t},${SRC_ROWS[$t]},${dst},${status}" | tee -a "$RECON"
done

bq --project_id=$PROJECT --location=us-east4 load --noreplace --source_format=CSV \
   ops_audit.load_reconciliation "$RECON" \
   run_id:STRING,table_name:STRING,source_rows:INT64,target_rows:INT64,status:STRING

if grep -q MISMATCH "$RECON"; then echo "RECON FAILED"; exit 1; else echo "RECON OK"; fi
#!/usr/bin/env bash
# usage: source scripts/env.sh   — prints no identifier values
export WORKLOAD_PROJECT="hanuman-0001"
export BOOTSTRAP_PROJECT="hanuman-0002"
export PROJECT_ID="$WORKLOAD_PROJECT"
export PROJECT="$WORKLOAD_PROJECT"
export REGION="us-east4"

PROJECT_NUMBER="$(gcloud projects describe "$WORKLOAD_PROJECT" --format='value(projectNumber)')"
FOLDER_ID="$(gcloud projects describe "$WORKLOAD_PROJECT" --format='value(parent.id)')"
ORG_ID="$(gcloud projects get-ancestors "$WORKLOAD_PROJECT" --format='value(id,type)' | awk '$2=="organization"{print $1}')"
BILLING_ID="$(gcloud billing projects describe "$WORKLOAD_PROJECT" --format='value(billingAccountName)' | sed 's#^billingAccounts/##')"
export PROJECT_NUMBER FOLDER_ID ORG_ID BILLING_ID

for v in WORKLOAD_PROJECT BOOTSTRAP_PROJECT PROJECT_ID REGION PROJECT_NUMBER FOLDER_ID ORG_ID BILLING_ID; do
  if [ -z "${!v}" ]; then echo "WARN: $v is empty"; else echo "$v: set"; fi
done
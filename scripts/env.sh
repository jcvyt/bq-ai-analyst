#!/usr/bin/env bash
# usage: source scripts/env.sh
export ORG_ID=361767570892
export FOLDER_ID=$(gcloud resource-manager folders list --organization="$ORG_ID" \
  --filter="displayName=Hanuman" --format="value(name)" | sed 's#folders/##')
export BILLING_ID=$(gcloud billing accounts list --format="value(name)" --limit=1 | sed 's#billingAccounts/##')
export WORKLOAD_PROJECT=hanuman-0001
export BOOTSTRAP_PROJECT=hanuman-0002
export REGION=us-east4

for v in ORG_ID FOLDER_ID BILLING_ID WORKLOAD_PROJECT BOOTSTRAP_PROJECT REGION; do
  if [ -z "${!v}" ]; then
    echo "WARN: $v is empty"
  else
    echo "$v=${!v}"
  fi
done

# bq-ai-analyst — Phase 1 progress (handoff)

## Status: Days 1–3 complete (Oct 2026)
- Own Cloud Identity org (free trial): org <ORG_ID>, folder "Hanuman"
- Projects: hanuman-0001 = workload/dev, hanuman-0002 = bootstrap
- Region: us-east4. Groups: gcp-admins, gcp-billing, gcp-developers
- Work from Cloud Shell as admin identity; `source scripts/env.sh` each session

## Built so far (all in Terraform, infra/bootstrap, human-applied by gcp-admins)
- Remote state: gs://hanuman-0002-tfstate (prefix "bootstrap"), versioned, lock file committed
- Group IAM: admins = orgpolicy.policyAdmin + folder admin/owner (break-glass);
  billing = costsManager + viewer; developers = viewer + bigquery.jobUser + dataViewer (humans read, pipelines write)
- Org policies: 7 secure-by-default policies imported (incl. iam.managed.disableServiceAccountKeyCreation,
  allowedPolicyMemberDomains, uniformBucketLevelAccess) + new storage.publicAccessPrevention (org)
  + gcp.resourceLocations = in:us-locations (folder)
- WIF: pool "github", provider "github-oidc", condition restricted to my repo; wif-smoke workflow green
- CI SA: sa-tf-ci@hanuman-0002 with 7 project roles on hanuman-0001 + objectAdmin on state bucket;
  gcp-admins can impersonate it
- Cost guardrails: budget alerts set; BigQuery custom quota blocked on free trial -> ~/.bigqueryrc 10 GB cap
- Guardrails verified: SA key creation, non-US location, and allUsers binding all denied; impersonation works
- CI: google-github-actions v3 (Node 24), runner pinned to ubuntu-24.04, Dependabot for actions + Terraform

## Remaining Week 1
- Day 4: infra/envs/dev for hanuman-0001 (datasets raw_thelook/curated/semantic/ops_audit/ops_eval,
  sa-analyst-agent with semantic-only read, staging buckets), applied via impersonation of sa-tf-ci
- Day 5: load thelook_ecommerce (US) -> us-east4 via export/rsync/load; PII inventory of users table
- Day 6: buffer
- Day 7: CI plan-on-PR / apply-on-merge with env approval, audit log sink, cost view, 20 golden questions, Checkpoint #1

## Deferred hardening (Phase 2)
- WIF condition on assertion.repository_id instead of repository name
- IAM Conditions to constrain sa-tf-ci's projectIamAdmin
- Retry BigQuery daily quota after upgrading from the trial

## Lessons
- Run commands one at a time; pasted blocks continue after failures
- Cloud Shell IPv6 errors: retry with -parallelism=4 or restart Cloud Shell
- Import existing resources with import blocks + -generate-config-out; plan must show 0 changes before apply


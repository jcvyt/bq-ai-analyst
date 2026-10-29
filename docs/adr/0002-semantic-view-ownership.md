# ADR-0002: Ownership of semantic views (supersedes ADR-0001)

- Status: Accepted
- Date: 2026-10-29
- Supersedes: ADR-0001 (premise error: it compared against "Terraform-managed views", which do not exist)

## Context (verified against code and live state, 2026-10-29)
- semantic views live: 2; both carry aggregation threshold k=10 (bq show)
- google_bigquery_table in infra/**/*.tf: 0; in dev state: 0
- Views and curated tables are created by hand-run DDL (sql/semantic/*.sql, sql/curated/*.sql), outside plan, CI and drift detection
- Access: semantic is an authorized dataset on curated (target_types VIEWS); grants are in Terraform
- Only guard today: access tests T1–T9

## Evidence: provider support for privacy_policy
| Provider | Version | google_bigquery* resources with privacy_policy/aggregation_threshold |
|---|---|---|
| google (pinned) | 7.46.1 | 0 |
| google-beta (pinned) | 7.46.1 | 0 |
| google (latest 7.x) | 7.46.2 | 0 |
| google-beta (latest 7.x) | 7.46.2 | 0 |
Method: `terraform providers schema -json` + jq scan (not docs or memory).
Positive control: materialized_view, use_legacy_sql, deletion_protection = 3/3 per provider.

## Options
1. Terraform google_bigquery_table: native plan/drift/destroy gate; requires privacy_policy in schema (absent)
2. Dataform: privacy_policy via bigquery.additionalOptions (spike: T9 518/518); new service + SA + CI invocation
3. CI-run DDL + drift job: minimal; drift detection is custom code

## Decision
Option 3. Semantic views are deployed by CI running sql/semantic/*.sql (CREATE OR REPLACE VIEW … OPTIONS(privacy_policy=…)) as sa-tf-ci in the tf-apply apply job, behind the dev environment reviewer. A drift job compares each live view's threshold, privacy unit column and query hash against the repo and fails or redeploys on mismatch. Terraform cannot model privacy_policy in google/google-beta <= 7.46.2 (0/4 schema hits), so a Terraform-managed view risks being rewritten without its policy, invisible in plan. Grants and dataset ACLs remain in Terraform.

## Consequences
- Deployed only from CI (tf-apply environment reviewer = human gate); no hand-run DDL against semantic
- Drift: a hand-dropped or altered view (query or threshold) is detected and redeployed by CI (W1 Day 3–4 exit test)
- Privacy policy is reviewed as code in PRs; T1–T9 run after every deploy
- Curated tables stay DDL-from-CI for Phase 2; no Dataform until a revisit trigger fires
- Revisit when: provider schema gains privacy_policy (re-run the check on each provider major upgrade); >5 views; curated needs DAG orchestration

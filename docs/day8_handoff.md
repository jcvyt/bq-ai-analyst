# bq-ai-analyst — Phase 1 handoff (as of Oct 20, 2026, end of Day 7)

> Private working doc. Contains org/project identifiers and domain — do NOT commit to the public repo.

## Environment
- Own Cloud Identity org 361767570892, folder "Hanuman", region us-east4
- hanuman-0001 = workload/dev (project number 236142939294); hanuman-0002 = bootstrap
- Groups: gcp-admins, gcp-billing, gcp-developers (+ dev-test@ user for access tests)
- Cloud Shell as admin; `source scripts/env.sh`; VS Code opened on ~/bq-ai-analyst only
- Repo: github.com/jcvyt/bq-ai-analyst (public)

## Done
### Days 1–5 (summary)
- Bootstrap (human-applied): remote state gs://hanuman-0002-tfstate, group IAM, org policies, WIF pool github / provider github-oidc (repo-restricted), sa-tf-ci, budgets, 10 GB bq cap, Dependabot
- Dev stack: datasets raw_thelook, curated, semantic, ops_audit, ops_eval; semantic authorized on curated; sa-analyst-agent = READER on semantic + jobUser; staging buckets
- raw_thelook ACL authoritative (projectOwners + gcp-admins); developers READER on curated/semantic/ops_eval; DLP agent declared
- 7 thelook tables loaded (RECON OK); DLP canonical jobs: users i-2866533…, events i-4215257… (events sampled 50,000 rows)

### Day 6 — PII inventory + engine-enforced privacy
- docs/pii_inventory.md: users + events classified (DLP = evidence, not classification; false positives city/state/uri; false negatives lat/long, age, user_id)
- Policy Analyzer (org scope, groups expanded) → raw readers: gcp-admins, projectOwners, DLP agent (project), sa-tf-ci (bigquery.admin, project) = ACCEPTED RISK; developers + agent verified absent. Raw JSON gitignored; redacted table in inventory
- cloudasset.googleapis.com imported in dev; roles/cloudasset.viewer for gcp-admins at org (bootstrap)
- curated.users (PII-minimized: no email, names, address, postal, lat/long; age banded)
- semantic.users_demographics: aggregation threshold k=10, privacy_unit_column user_id
- tests/access/test_semantic_access.py T1–T5

### Day 7 — events + CI
- curated.events: 2,416,143 rows; ip/postal/raw uri dropped; uri parsed (page_type, department, category, brand, product_id); privacy_unit = COALESCE(CAST(user_id AS STRING), session_id) (46.6% anonymous rows); 0 null units
- semantic.web_events: aggregation threshold k=10 on privacy_unit
- Access tests T1–T9 (T9: fine grain brand×state×date×hour → only 518 events visible)
- CI:
  - tf-plan.yml (pull_request incl. labeled/unlabeled): fmt -check (both stacks), init, validate, plan, destroy gate, step summary
  - tf-apply.yml (push main): plan job (gate + merged-PR label lookup) → artifact (1 day) → apply job (environment dev, required reviewer) → access tests as agent
  - Inputs: vars TF_VAR_PROJECT_ID / TF_VAR_REGION; secrets TF_VAR_ADMINS_GROUP / TF_VAR_DEVELOPERS_GROUP (masked); terraform.tfvars untracked + .example committed
  - Regex validation on admins_group / developers_group (dev stack)
  - sa-tf-ci has TokenCreator on sa-analyst-agent (CI test runner)
  - Ruleset main: PR required, 0 approvals, required check `plan` (strict), no deletion, no force push
  - Local pre-push hook: terraform fmt -check
- Proof runs: PR-A no-op apply + approval + T1–T9 in CI; PR-B canary created; PR-C gate blocked delete → allow-destroy label → 1 destroyed; gate also caught a real bad input (pasted comment in group email would have replaced 3 dataset ACL entries)

## Key numbers
| Metric | Value |
|---|---|
| users rows | 100,000 |
| T3 visible users (state×gender×age, k=10) | 95,721 in 1,731 groups (= independent k-check) |
| Rows suppressed at state grain / country grain | 4.28% / 0.03% |
| postal×gender×age groups < k | 99.0% |
| events rows / anonymous share | 2,416,143 / 46.6% |
| T9 fine-grain visible events | 518 |

## Day 8 (next)
- [ ] Audit log sink (BigQuery data_access) → ops_audit (partitioned), via Terraform
- [ ] Cost view over region-us-east4 INFORMATION_SCHEMA.JOBS_BY_PROJECT (bytes, slot-ms, cost by principal/day)
- [ ] 20 golden questions in ops_eval (include: threshold clause required, suppression-awareness on fine grain, denied curated/raw, state vs country)
- [ ] ADR: SQL deploy mechanism (scripted DDL in CI vs Dataform). Today sql/ is run manually as admin
- [ ] Checkpoint #1
- [ ] Cleanup PR: duplicate repo variables (WIF_PROVIDER vs GCP_WIF_PROVIDER, TF_CI_SA vs GCP_TF_SA, PROJECT_ID, TF_STATE_BUCKET — grep workflows first); Dependabot ignore semver-major hashicorp/*; git user.email → GitHub noreply; delete old run logs that printed group emails; mirror group-email validation in bootstrap
- [ ] Carry-over if not done: scripts/dlp_status.sh + dlp_inspect.py start/wait split

## Deferred (Phase 2)
- WIF condition on assertion.repository_id; IAM Conditions on sa-tf-ci projectIamAdmin
- sa-tf-ci: custom deployer role without bigquery.tables.getData / export; re-verify with Policy Analyzer
- VPC-SC perimeter; CMEK on raw; policy tags on curated; org policy requiring data-class label
- Replace basic roles/viewer and projectOwners raw access; full-table SDP discovery (events was sampled)
- Deliberate google provider 7 → 8 upgrade (both stacks; Dependabot 8.6.0 PR stays open)
- BigQuery custom quota after trial upgrade
- Team mode: ≥1 approvals, CODEOWNERS for infra/, prevent self-review, unattributed-changes rule
- Known gap: Dependabot PRs can't auth to GCP in CI (plan locally)
- Investigate: joins across two aggregation-threshold views (users × web_events)

## Lessons
- Run commands one at a time; scripts use set -euo pipefail
- Destroy gate before every apply; replacements count as deletes
- Import existing resources with import blocks; plan must show 0 changes
- Cloud Shell network errors (IPv6 / connection refused): -parallelism=4 or restart
- BigQuery dataset_access: legacy roles (READER), never mix with dataset_iam_*; group_by_email change = replacement
- Project-level IAM bypasses dataset ACLs — fix both paths; prove with Policy Analyzer
- Service agents are lazy: google_project_service_identity before first use
- Ctrl+C doesn't cancel server-side jobs; separate start/wait, print progress
- One working copy per stack; merge each day's PR before the next
- DLP findings are evidence, not classification; check rowsLimit sampling before hit rates
- Enforce privacy in the engine (aggregation threshold), never in prompts; privacy unit must cover anonymous rows
- Answer N to gcloud "enable API?" prompts; add the service in Terraform
- gcloud Policy Analyzer JSON is [{policy, ACLs}], not mainAnalysis; redact --expand-groups evidence
- auth@v3 success proves nothing; terraform init against remote state is the real WIF test
- Untracked tfvars = CI has no inputs; parsing tfvars with loops copies inline comments; read every value
- Public repo = public Actions logs; use secrets for anything you wouldn't post (masking is string-based)
- Validate identity inputs; gates catch deletes, validation catches bad inputs
- When CI and local plans differ, reproduce CI inputs locally with -var
- Every job that runs terraform plan needs all inputs; grep all workflows
- One workflow file per pipeline, .yml only (path filters miss .yaml)
- Solo repo: self-approval impossible → 0 approvals + environment reviewer as the human gate
- Longer map keys re-align maps: run terraform fmt; pre-push hook enforces it

## Working agreement
Go day by day; next day starts only after results are verified.
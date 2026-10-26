# bq-ai-analyst — Phase 1 handoff (as of Oct 20, 2026, end of Day 7)

> Private working doc. Contains org/project identifiers and domain — do NOT commit to the public repo.

## Environment
- Own Cloud Identity org <ORG_ID>, folder "Hanuman", region us-east4
- hanuman-0001 = workload/dev (project number <PROJECT_NUMBER>); hanuman-0002 = bootstrap
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

### Day 8 — eval golden set + observability
- Golden set v1 frozen and loaded: ops_eval.golden_questions, 20 items, anchor_date 2026-10-16, frozen AS sa-analyst-agent
  - Behaviors: ANSWER 9 / ANSWER_WITH_CAVEAT 4 / CLARIFY 1 / OUT_OF_SCOPE 3 / REFUSE 3
  - G07 = 1,731 groups (matches T3); G08 (Okinawa, sub-k) + G15 fully suppressed = 0 rows
  - Empty results share fp e3b0c442… → 0-row items graded on behavior + must_mention + forbidden_patterns, never fingerprint
  - v1 immutable after first scored run; changes = v2
- Freeze script guards: literal questions, no BETWEEN, no CURRENT_*, no TODO/placeholders, objects ⊂ allowed_objects, threshold clause required, non-empty unless true_count_is_below_k, snapshot counts asserted
- Conventions: "last week" = [as_of - 7, as_of) half-open; as_of_date injected by harness (never system clock); glossary at sql/semantic/glossary.yaml
- Data quality: DQ-001 future-dated events after load (10-17..10-19); DQ-002 category/brand only on department events, product_id only on product; DQ-003 'Spain' vs 'España', Brazil = 'Brasil'
- Audit sink bq-audit-to-ops-audit (data_access + activity, partitioned, 90d) codified in main (#16; was applied before merge)
- Cost view ops_audit.v_query_cost_daily deployed (list price, excludes SCRIPT parents, labels app/component)
- tf-plan.yml: paths filter removed so required check `plan` reports on every PR
- Verification results: [paste: audit query summary + cost view rows]

### Incident — identifiers in public repo (2026-10-23)
- Private notes (day7.md, handoff) committed to main since Day 7 (#11), plus hardcoded IDs in bootstrap .tf, tfvars.example, env.sh
- Secret scan: no credentials (2 hits = the word "password" in prose)
- Docs redacted (#17 + redact-notes-2); code parameterization = Day 9 PR-2
- History: Option A, accepted risk, dated 2026-10-23; revisit at Phase 1 end
- backup-local-main branch kept (old local commits) until history decision is final

- Verification: audit sink logs agent OK (121), PERMISSION_DENIED (3), NOT_FOUND (1), INVALID_ARGUMENT (4); cost view shows eval-freeze 41 jobs, window-check 3 jobs under sa-analyst-agent



## Day 9 (next)
- [ ] PR-2 parameterize identifiers: env.sh (runtime lookups, no echo), tfvars.example placeholders, bootstrap .tf → vars; delete completed import blocks; bootstrap plan = No changes; whole-repo git grep clean
- [ ] ADR-0001: fill stub (options, decision, Dataform spike: semantic.web_events, T9 = 518)
- [ ] PR-E cleanup: duplicate repo vars, Dependabot semver-major ignore, noreply email, old run logs, bootstrap email validation, pre-push hook checks commit, pre-commit identifier hook
- [ ] Checkpoint #1

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
- Never apply from an unmerged working copy; state ahead of main = next PR deletes it (destroy gate caught it)
- Path filters + required checks = check stuck "Expected" forever
- Stage files by name; never `git add .`; review `git diff --cached --stat`
- Private notes live outside the repo (~/private-notes); .gitignore is backup only
- Pre-push hook checks the working tree, not the pushed commit (fix in PR-E)
- Paste only at an empty prompt; backticks in double quotes = command substitution
- git grep --cached / origin/main checks what's committed, not your working tree
- Reference SQL must be deterministic: tie-breakers on ORDER BY … LIMIT, pinned anchors

## Working agreement
Go day by day; next day starts only after results are verified.





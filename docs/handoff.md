# bq-ai-analyst — Phase 1 handoff (as of Oct 19, 2026)

## Environment
- Own Cloud Identity org 361767570892, folder "Hanuman", region us-east4
- hanuman-0001 = workload/dev (project number 236142939294); hanuman-0002 = bootstrap
- Groups: gcp-admins, gcp-billing, gcp-developers (+ dev-test@ user for access tests)
- Cloud Shell as admin; `source scripts/env.sh`; VS Code opened on ~/bq-ai-analyst only
- Repo: github.com/jcvyt/bq-ai-analyst

## Done
### Days 1–3 (bootstrap, human-applied as admin)
- Remote state gs://hanuman-0002-tfstate (prefix bootstrap), versioned
- Group IAM; org policies (7 imported + storage.publicAccessPrevention + gcp.resourceLocations in:us-locations)
- WIF pool github / provider github-oidc (repo-restricted); sa-tf-ci@hanuman-0002 (admins can impersonate)
- Budget alerts; ~/.bigqueryrc 10 GB cap; CI on google-github-actions v3, ubuntu-24.04, Dependabot

### Day 4 (infra/envs/dev, applied via GOOGLE_IMPERSONATE_SERVICE_ACCOUNT=sa-tf-ci) — merged
- Datasets: raw_thelook, curated, semantic, ops_audit, ops_eval (us-east4, time travel 48h, labels)
- Authorized dataset: semantic views -> curated
- sa-analyst-agent: READER on semantic only + project bigquery.jobUser; admins have TokenCreator on it
- Buckets hanuman-0001-staging-us / -staging-use4: PAP enforced, UBLA, 7-day delete, soft delete 0
- Verified: agent reads semantic view; denied on curated, raw, and writes

### Day 5 (branch day5-load-pii) — applied, NOT yet merged
- raw_thelook ACL authoritative (projectOwners + gcp-admins OWNER only)
- Developers: project-level dataViewer removed (bootstrap); dataset READER on curated/semantic/ops_eval
- DLP service agent via google_project_service_identity (google-beta) + roles/dlp.serviceAgent
- Load: 7 thelook tables extract(US) -> rsync -> load(us-east4), RECON OK, logged in ops_audit.load_reconciliation
- DLP jobs: canonical = users i-2866533…, events i-4215257… (findings in ops_audit.dlp_findings_*, no quotes)
  duplicates: events i-8680722… (exclude/delete findings), users i-9075067… (cancel)

## Open — close on Day 6 (buffer)
- [ ] Confirm i-9075067… cancelled
- [ ] Run per-column DLP summaries (filter by canonical job_name); finalize docs/pii_inventory.md
      (direct vs quasi-identifiers, semantic rules, k>=10 suppression, approved raw readers incl. DLP agent)
- [ ] Both plans show "No changes" (dev impersonated, bootstrap as self)
- [ ] Commit, push, PR, merge day5-load-pii; then `git stash drop`
- [ ] dlp_inspect.py progress printing + scripts/dlp_status.sh (list jobs via REST)
- [ ] .github/dependabot.yml: ignore semver-major for hashicorp/*; leave the google 8.6.0 PR unmerged

## Day 7 (next)
- CI: plan-on-PR / apply-on-merge with environment approval, destroy gate (fail on deletes unless allow-destroy label)
- Audit log sink -> ops_audit; cost view; 20 golden questions in ops_eval; Checkpoint #1

## Deferred (Phase 2)
- WIF condition on assertion.repository_id; IAM Conditions on sa-tf-ci projectIamAdmin
- VPC-SC perimeter; CMEK on raw; policy tags on curated; org policy requiring data-class label
- Replace basic roles/viewer; scheduled SDP discovery; deliberate google provider 7 -> 8 upgrade (both stacks)
- BigQuery custom quota after upgrading from trial

## Lessons
- Run commands one at a time; scripts must use set -euo pipefail
- Destroy gate before every apply: terraform show -json plan | jq deletes == []
- Import existing resources with import blocks; plan must show 0 changes
- Cloud Shell IPv6 errors: -parallelism=4 or restart
- BigQuery dataset_access: use legacy roles (READER), never mix with dataset_iam_*
- Project-level IAM bypasses dataset ACLs — fix both paths
- Service agents are lazy: declare with google_project_service_identity before first use
- Ctrl+C doesn't cancel server-side jobs; separate start/wait, print progress
- One working copy per stack; merge each day's PR before starting the next
- (add: what the Day 4 "2 destroyed" was)

## Working agreement
Go day by day; next day starts only after results are verified.


DLP findings are evidence, not classification. Expect false positives (city as PERSON_NAME) and false negatives (coordinates, age, user_id).
Check DLP sampling (rowsLimit) before computing hit rates.
Enforce privacy rules in the engine (aggregation threshold), never in prompts. The privacy unit must cover anonymous rows.
Answer N to gcloud’s enable-API prompts; add the service in Terraform instead.
With --format=json, gcloud’s Policy Analyzer output is [{policy, ACLs}], not the raw API’s mainAnalysis.
Redact --expand-groups evidence before committing to a public repo.
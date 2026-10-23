# Day 7 — Events, CI/CD Guardrails, and Why Every Piece Exists

> **Repo:** `bq-ai-analyst` · **Scope:** Day 7 of Phase 1 · **Audience:** you (moving into an architect role) and anyone you teach next.
> This file is safe for the public repo: it contains no org IDs, project numbers, or personal emails. Placeholders like `<domain>` stand in for those.

---

## 0. How to read this document

**What Day 7 was.** On Day 7 you did two things:

1. **Data:** built `curated.events` and `semantic.web_events`, and extended the access tests to T6–T9.
2. **Delivery:** built a CI/CD pipeline that plans every pull request, blocks destructive changes, needs a human approval before apply, and re-tests access after every apply. You then *proved* it with canary pull requests, and debugged seven real problems along the way.

**How each item is explained.** Every major artifact follows the same seven headings:

| # | Heading | Question it answers |
|---|---|---|
| 1 | What it is | What is this, in one sentence? |
| 2 | Why it exists here | What problem does it solve *in this project*? |
| 3 | Why this exact form | Why these settings and not others? |
| 4 | Alternatives | What else could we have done, and when would that be better? |
| 5 | Trade-offs | What did we pay (cost, security, operability, blast radius, coupling)? |
| 6 | Failure mode if skipped | What breaks, when, and how would you notice? |
| 7 | Soundbite | What you say out loud in an interview or at a whiteboard |

Small items (a single command, a one-line setting) get a short table instead of the full treatment.

**Suggested reading order:**

- **Want to build this yourself in a new project?** Read §2 (Primer), then follow §6 (Hands-on lab) step by step. If your project has no foundations yet (state bucket, CI identity, datasets, agent), start with **Appendix A**. When something fails, use §7 (Troubleshooting). §3–§5 explain *why* each lab file looks the way it does.
- **New to Git, Terraform state, or GitHub Actions?** Read §2 (Primer) first. Everything else assumes it.
- **Preparing for an interview?** Read §1, §8 (Decision frameworks), §9 (Known weaknesses), and §10 (Question bank).
- **Teaching a junior?** Use §11. It is a ready-made 90-minute session.

**A note on honesty.** §9 lists the weaknesses that still exist in what we built. An architect who can name the holes in their own design is far more credible than one who claims there are none.

---

## 1. The architecture in one page

### 1.1 Diagram

```mermaid
flowchart TB
  ME["You (admin)<br/>Cloud Shell"]

  subgraph GH["GitHub — public repo"]
    PR["Pull request"] --> PLANWF["tf-plan.yml<br/>fmt · validate · plan · destroy gate"]
    MAIN["main branch<br/>(ruleset: PR + green 'plan' required)"] --> APPLYWF["tf-apply.yml<br/>plan → human approval → apply → access tests"]
  end

  subgraph BOOT["Bootstrap project (hanuman-0002) — applied by a human"]
    WIF["Workload Identity Federation<br/>pool 'github' / provider 'github-oidc'"]
    TFCI["sa-tf-ci<br/>(Terraform deployer)"]
    STATE[("State bucket<br/>prefix 'bootstrap' | prefix 'dev'")]
  end

  subgraph DEV["Workload project (hanuman-0001) — applied by CI"]
    RAW[("raw_thelook<br/>full PII · owners only")]
    CUR[("curated<br/>PII-minimized tables")]
    SEM[("semantic<br/>views · aggregation threshold k=10")]
    OPSA[("ops_audit")]
    OPSE[("ops_eval")]
    BKT["staging buckets<br/>US + us-east4"]
    AGENT["sa-analyst-agent<br/>(the AI analyst)"]
    DLPSA["DLP service agent"]
  end

  PLANWF -- "OIDC token" --> WIF
  APPLYWF -- "OIDC token" --> WIF
  WIF -- "exchange → act as" --> TFCI
  TFCI -- "read/write state" --> STATE
  TFCI -- "manages resources" --> DEV
  TFCI -. "impersonates for tests only" .-> AGENT
  RAW -- "SQL build" --> CUR
  CUR -- "authorized dataset" --> SEM
  AGENT -- "READER (semantic only)" --> SEM
  DLPSA -- "scans (project-level role)" --> RAW
  ME -- "applies bootstrap;<br/>impersonates sa-tf-ci locally" --> BOOT
```

### 1.2 The identities, in one table

| Identity | Who/what it is | What it can do | Why it exists |
|---|---|---|---|
| You (admin, in `gcp-admins`) | Human operator | Owns bootstrap; can impersonate `sa-tf-ci` and `sa-analyst-agent` | Someone has to create the identity that CI uses (the chicken-and-egg problem) |
| `sa-tf-ci` | The Terraform deployer, in the bootstrap project | Manages dev resources; reads/writes state; can impersonate the agent | One identity for all infrastructure changes, so every change is attributable and reproducible |
| `sa-analyst-agent` | The identity the AI analyst runs as | `READER` on `semantic` + permission to run query jobs. Nothing else. | Least privilege for the component most likely to be tricked (an LLM) |
| DLP service agent | A Google-managed identity used by Sensitive Data Protection | Reads data to inspect it (project-level role) | DLP jobs run as this identity, not as you |
| GitHub Actions (via OIDC) | Not a GCP identity: a signed token from GitHub | Can *become* `sa-tf-ci`, only for this one repo | Lets CI authenticate with **no stored keys** |

### 1.3 The data layers

| Layer | Contents | Who can read | Rule |
|---|---|---|---|
| `raw_thelook` | Exact copy of the source, including PII | Owners only (+ DLP agent, + deployer — see §9) | Never queried by people or the agent |
| `curated` | Cleaned tables with direct identifiers removed | Developers, and `semantic` (as an authorized dataset) | Data minimization: if nobody needs a field, it's dropped |
| `semantic` | Views designed for analysis, with privacy rules enforced by BigQuery | Developers, the agent | The only layer the AI can touch |
| `ops_audit` / `ops_eval` | Operational evidence: load reconciliation, DLP findings, (Day 8) audit logs and evaluation results | Admins / developers | The "black box recorder" of the platform |

### 1.4 The elevator story (Days 1–7, in order, and why that order)

1. **Days 1–3 (identity before infrastructure):** create the state bucket, groups, org policies, keyless CI identity (WIF) and budgets *first*. Everything later depends on "who is allowed to change things" being settled.
2. **Day 4 (empty containers with locks on):** create datasets and buckets with access rules and the agent identity, and *prove* the agent can only read `semantic` before any real data arrives.
3. **Day 5 (data in, then find the PII):** load the sample data into `raw`, lock `raw` down, and run DLP to discover what is sensitive.
4. **Day 6 (decide what's sensitive, enforce it in the engine):** classify every column, build `curated.users`, and put a k=10 aggregation threshold on the semantic view, so BigQuery itself refuses to reveal small groups.
5. **Day 7 (repeat for events, then automate safely):** apply the same pattern to events (the riskier table, because nearly half its rows are anonymous visitors). Then move every infrastructure change behind a pipeline with a plan, a destroy gate, a human approval, and automatic access tests.
6. **Why this order:** *identity → containers → data → classification → enforcement → automation*. Each step makes the next one safe. Automating before you know what "safe" means just automates mistakes faster.

---

## 2. Primer: concepts you need before the deep-dives

Skip any subsection you already know well.

### 2.1 Git: branches, pull requests, squash merges

**Analogy.** `main` is the published book. A **branch** is your personal photocopy where you draft changes. A **pull request (PR)** is the request: "please publish my draft into the book". Reviewers and robots (CI) check it first. A **merge** publishes it.

| Term | Plain meaning | Day 7 example |
|---|---|---|
| Branch | A named line of work, separate from `main` | `day7-events-ci`, `day7-canary-add` |
| Push | Upload your branch's commits to GitHub | `git push -u origin day7-canary-add` (`-u` remembers the remote, so later you can just type `git push`) |
| Pull request | A proposal to merge a branch into `main`, with discussion and checks | PR #7 |
| Status check | An automated job whose pass/fail is attached to the PR | The `plan` job |
| Squash merge | All of the branch's commits are combined into **one** new commit on `main` | `gh pr merge --squash` — keeps `main` history as "one PR = one commit" |
| `--delete-branch` | Delete the branch after merging | Keeps the repo tidy; the history lives on in `main` |
| `git commit --amend` | Rewrite your *last* commit | Used to fold the `fmt` fix into the canary commit. **Only safe before pushing**, because amending rewrites history |
| Ruleset / branch protection | Rules GitHub enforces on a branch | "No direct pushes to `main`; a PR with a green `plan` is required" |

**Why branches matter for infrastructure.** Without branches, a change goes straight to `main` and (with CI) straight to production. With branches and PRs, every change gets a *preview* (the plan) that you can inspect before it is real.

### 2.2 Terraform: plan, apply, state, and the two kinds of "lock"

- **Configuration** (`.tf` files) describes what you *want*.
- **State** (a JSON file in the GCS bucket) records what Terraform *believes exists*, and maps each resource address (`google_bigquery_dataset.ds["curated"]`) to a real object.
- **`terraform plan`** compares the configuration with the state *and* the real world (the "refresh"), then lists the actions needed: create, update, delete, or replace.
- **`terraform apply`** performs those actions.

**Two different things are both called "lock".** This confuses almost everyone.

| | State lock | Dependency lock file |
|---|---|---|
| File | A lock object next to the state in GCS (temporary) | `.terraform.lock.hcl` in your repo (permanent, committed) |
| Purpose | Stops two people or pipelines changing the same state at once | Pins **provider versions and checksums**, so every machine uses the same provider build |
| Lifetime | Held only during plan/apply | Changes only when you upgrade providers |
| Day 7 relevance | `-lock-timeout=5m` waits instead of failing if another run holds the lock | `terraform init` in CI read the same lock file as Cloud Shell, so CI used the same `google` 7.46.1 provider as you |

### 2.3 Why two states: bootstrap vs dev

You have **two Terraform root modules, each with its own state**:

| | `infra/bootstrap` | `infra/envs/dev` |
|---|---|---|
| Creates | State bucket, groups' IAM, org policies, WIF, `sa-tf-ci`, budgets | Datasets, buckets, the agent, dataset ACLs |
| Applied by | You, as yourself | CI, as `sa-tf-ci` |
| Changes | Rarely | Often |
| Blast radius | Organization-wide | One project |

**Why split?** Three reasons:

1. **Chicken-and-egg.** CI cannot create the identity it uses to log in. Bootstrap must exist first.
2. **Blast radius.** A bad apply of the dev stack can't touch org policies or the CI identity, because they aren't in its state.
3. **Least privilege.** `sa-tf-ci` doesn't need org-admin powers for daily work, so the powerful bootstrap stays with a human.

### 2.4 Terraform variable precedence (needed for the Day 7 incidents)

Terraform takes each variable's value from the **highest-priority** source that sets it:

| Priority | Source | Day 7 role |
|---|---|---|
| Lowest | Environment variables `TF_VAR_<name>` | How CI passes inputs |
| ↑ | `terraform.tfvars` | Your local inputs (untracked, so absent in CI) |
| ↑ | `*.auto.tfvars` | Not used |
| Highest | `-var` / `-var-file` on the command line | How you reproduced CI's bad input locally |

This table explains two moments from Day 7. CI saw *no* values (no tfvars in the repo, and no env vars yet). And your `-var 'developers_group=… # same value…'` test could override your local tfvars and reproduce CI exactly.

### 2.5 Workload Identity Federation (WIF), in six steps

The problem: CI needs to call GCP. The old way is a downloaded JSON service-account key stored as a GitHub secret. Keys leak, never expire, and are a top cloud breach cause.

The WIF way:

1. The workflow asks GitHub for an **OIDC token**. That needs `permissions: id-token: write`.
2. GitHub signs a short-lived token containing claims, such as `repository: jcvyt/bq-ai-analyst` and `ref: refs/heads/main`.
3. `google-github-actions/auth` writes a credentials *config* file. Note that it doesn't exchange anything yet.
4. On the **first real API call** (`terraform init` reading the state bucket), Google's Security Token Service checks the token's signature and your provider's **attribute condition** (only this repo).
5. Google issues a short-lived federated token, which is then exchanged for an access token **as `sa-tf-ci`** (that's the `workloadIdentityUser` binding).
6. The token expires in about an hour. There's nothing to rotate, and nothing to leak long-term.

This is why "auth step green" proved nothing on Day 7: step 3 does no network check. `terraform init` (step 4) was the real test.

### 2.6 GitHub Actions anatomy

| Term | Meaning |
|---|---|
| Workflow | A YAML file in `.github/workflows/`. **Every file there runs**, which is why a duplicate `.yaml` was dangerous |
| Trigger (`on:`) | What starts it: `pull_request`, `push`, … |
| Job | A group of steps on one fresh virtual machine (the **runner**). Jobs don't share files unless you pass **artifacts** |
| Step | One command (`run:`) or reusable action (`uses:`) |
| `permissions:` | What the job's `GITHUB_TOKEN` (and OIDC) may do. Default to minimal |
| `vars` / `secrets` | Repo-level config. `vars` are printed in logs in plain text; `secrets` are **masked** (replaced by `***`) |
| Environment | A named deployment target (`dev`) that can require **human approval** before a job runs |
| Artifact | A file uploaded by one job and downloaded by another (our `tfplan`) |
| Concurrency group | A name that limits how many runs execute at once |

### 2.7 BigQuery aggregation threshold, in one paragraph

You attach a **privacy policy** to a view: "every group in a result must contain at least *k* distinct **privacy units** (here, people)". Queries must say `SELECT WITH AGGREGATION_THRESHOLD …`. BigQuery then **silently drops** any group with fewer than *k* units, and **rejects** non-aggregate queries such as `SELECT *`. The enforcement is inside the database engine, so it applies equally to an analyst, a dashboard, or an AI that has been tricked by a malicious prompt.

---

## 3. The data layer: events

### 3.0 Preflight (Block 0): verify before building

```bash
git switch main && git pull && git log --oneline -3
terraform plan -detailed-exitcode   # exit 0 = no changes, 2 = drift, 1 = error
python tests/access/test_semantic_access.py
git switch -c day7-events-ci
```

| Command | Why |
|---|---|
| `git pull` + `log` | Proves Day 6 is actually on `main`. You never build on unmerged work |
| `plan -detailed-exitcode` | Turns "looks fine" into a number: `0` means reality matches code. Starting a day with drift means you can't tell your changes from someone else's |
| Access tests | Proves yesterday's security still holds *before* you change anything |
| New branch | Today's work is isolated until it's reviewed. If it goes wrong, `main` is untouched |

> **Soundbite:** "Every working day starts with three proofs: the previous change is merged, the plan has zero drift, and the security tests pass. Otherwise I can't attribute today's results to today's changes."

---

### 3.1 `sql/curated/events.sql`: the PII-minimized events table

```sql
CREATE OR REPLACE TABLE `hanuman-0001.curated.events`
PARTITION BY DATE(created_at)
CLUSTER BY event_type, page_type
OPTIONS (description = "...", labels = [("data_class","internal"), ("layer","curated"), ...]) AS
WITH e AS (SELECT *, REGEXP_REPLACE(uri, r"[?#].*$", "") AS uri_path FROM raw_thelook.events)
SELECT id AS event_id, user_id, session_id, sequence_number, created_at,
       city, state, browser, traffic_source, event_type, uri_path,
       <page_type / department / category / brand / product_id parsed from uri_path>,
       COALESCE(CAST(user_id AS STRING), session_id) AS privacy_unit
FROM e;   -- dropped: ip_address, postal_code, raw uri
```

**1. What it is.** A rebuild-from-scratch SQL statement that creates a cleaned copy of the 2.4M-row events table, with direct identifiers removed and analysis-friendly columns added.

**2. Why it exists here.** The `semantic` layer may only read from `curated`, never from `raw`. Events had to pass through the same "minimize, then expose" pipe as users did on Day 6. Events is also the riskier table: it holds IP addresses, and it links to users through `user_id`.

**3. Why this exact form.**

| Choice | Reason |
|---|---|
| **Drop `ip_address`** | IP is a direct identifier (personal data under GDPR). DLP found it in 100% of sampled rows. No consumer needs it, and `city`/`state` already give location |
| **Drop `postal_code`** | 99% of postal × gender × age groups had fewer than 10 people (Day 6). It can't be used safely downstream, so it isn't carried |
| **Drop raw `uri`, keep `uri_path`** | The regex strips `?query` and `#fragment`. Your data had zero query strings, but in real clickstreams that's exactly where emails, tokens and search terms leak. This is a **defensive rule**: it costs nothing today and protects against tomorrow's data |
| **Parse `page_type`, `department`, `category`, `brand`, `product_id`** | An LLM writing SQL does much better with a `brand` column than with `REGEXP_EXTRACT` over a path. Parsed columns are also cheaper to filter, and they cluster well |
| **`privacy_unit = COALESCE(CAST(user_id AS STRING), session_id)`** | 46.6% of events are anonymous (`user_id IS NULL`). A privacy rule keyed only on `user_id` would leave half the data unprotected. `CAST` is needed because `COALESCE` requires one type (`INT64` vs `STRING`) |
| **`PARTITION BY DATE(created_at)`** | Queries filtered by date only scan matching partitions, which means lower cost. About 2,500 daily partitions is well under BigQuery's per-table partition limit |
| **`CLUSTER BY event_type, page_type`** | The most common filters ("purchases", "product views") read fewer blocks. Clustering is free to declare |
| **`CREATE OR REPLACE`** | Idempotent: running it twice gives the same result. Fine for a static sample dataset |
| **Labels** | `data_class`, `layer` and `source` make the table findable in inventories and cost reports, and can be enforced by org policy later |
| **`city` kept in curated** | Developers may need it for debugging. It is *not* exposed in semantic (city-level groups are small) |

**4. Alternatives.**

| Alternative | What it is | Wins when | Loses when |
|---|---|---|---|
| **Dataform (or dbt) model** | The same SQL as a managed model, with dependencies, assertions, scheduling and lineage | Many tables, scheduled refreshes, a team that needs reviews of SQL changes and data tests | One-off builds on a static dataset (more setup than value today). Planned as a Day 8 decision (ADR) |
| **Incremental `MERGE`** | Only insert or update new rows | Large, continuously arriving data, where a full rebuild is too slow or expensive | Static sample data: extra complexity, no benefit |
| **Column-level security (policy tags) on one table instead of a copy** | Keep a single table and hide columns per reader | You must avoid copies (storage, freshness) and readers differ per column | You want "it physically isn't there" as the guarantee. A misconfigured tag reveals data; a dropped column can't |
| **Hash IP instead of dropping** | Keep a pseudonymous IP | You need cross-session device linking | IPv4 space is small, so unsalted hashes are trivially reversible. Without a real need, drop |

**5. Trade-offs.**
- *Cost:* a full rebuild scans about 2.4M rows each time, which is cents at this size.
- *Security:* "physically absent" is the strongest control; the price is losing the data for future needs (you'd re-derive it from raw).
- *Operability:* the file is run **by hand** today. That's acceptable for Phase 1, but it isn't reproducible by CI yet (§9).
- *Coupling:* the `uri` parsing assumes thelook's path patterns. A new pattern yields `NULL` parsed fields, which is safe but silent.

**6. Failure mode if skipped.** Without `curated.events`, the semantic view would have to read `raw` directly. That means either granting the semantic layer access to IP addresses, or not shipping events at all. Without the privacy-unit `COALESCE`, the threshold would count anonymous rows wrongly, and half of the data would be outside the guarantee with no error at all.

**7. Soundbite.**
> "Curated is where data minimization happens. Anything without a named consumer is dropped, including identifiers DLP found and quasi-identifiers our k-anonymity check showed are unsafe. We also derive a privacy unit that covers anonymous visitors, because 47% of events have no user ID."

#### 3.1a The sanity check

```sql
SELECT COUNT(*) n, COUNTIF(privacy_unit IS NULL) null_units,
       COUNTIF(page_type IS NULL) null_page_type,
       COUNTIF(page_type="product" AND product_id IS NULL) product_without_id
FROM curated.events;
-- result: 2416143 | 0 | 0 | 0
```

| Column | What a non-zero result would mean |
|---|---|
| `n ≠ 2,416,143` | Rows lost or duplicated in the transformation |
| `null_units > 0` | Rows with no user *and* no session, invisible to the privacy rule. **Stop** before creating the view |
| `null_page_type > 0` | The `CASE` doesn't cover some URIs |
| `product_without_id > 0` | The product-ID regex misses a pattern |

> **Principle:** every transformation gets a **reconciliation query** with *expected numbers written down before you run it*. It's the data equivalent of a unit test.

---

### 3.2 `sql/semantic/web_events.sql`: the governed view

```sql
CREATE OR REPLACE VIEW `hanuman-0001.semantic.web_events`
OPTIONS (
  privacy_policy = '{"aggregation_threshold_policy": {"threshold": 10, "privacy_unit_column": "privacy_unit"}}',
  labels = [("data_class","aggregate_only")]
) AS
SELECT privacy_unit, DATE(created_at) AS event_date, EXTRACT(HOUR FROM created_at) AS event_hour,
       state, browser, traffic_source, event_type, page_type, department, category, brand, product_id
FROM curated.events;
```

**1. What it is.** A view over `curated.events` with a BigQuery privacy policy. Any result group must contain at least 10 distinct privacy units, or BigQuery drops it.

**2. Why it exists here.** This is what the AI analyst will query. An LLM can be manipulated ("ignore your rules and list the sessions from Ohio at 3am"). The rule must hold **even when the SQL is hostile**, so it lives in the database, not in the prompt.

**3. Why this exact form.**

| Choice | Reason |
|---|---|
| `threshold: 10` | A common k-anonymity floor. It matches the k ≥ 10 rule in `pii_inventory.md`, so the document and the engine agree |
| `privacy_unit_column: privacy_unit` | Counts *people/sessions*, not events. One user with 50 clicks is still one unit |
| `event_date` + `event_hour` instead of `created_at` | Exact timestamps plus a session form a fingerprint. Hour-level granularity is enough for analytics |
| No `user_id`, `session_id`, `city`, `uri_path` | IDs are never displayed (they're only used as the privacy unit). City groups are small. The parsed dimensions replace the path |
| `privacy_unit` *is* selected | The policy needs it present in the view. BigQuery doesn't let queries output it directly in a way that defeats the rule |
| View, not table | No data copy and always fresh. Authorization flows through the **authorized dataset** set up on Day 4, so the view can read `curated` while the agent can't |
| Label `aggregate_only` | Tells humans and tooling that this view only works with threshold queries |

**4. Alternatives.**

| Alternative | What it is | Wins when | Loses when |
|---|---|---|---|
| **Pre-aggregated tables with `HAVING COUNT(DISTINCT unit) >= 10`** | Materialize fixed rollups | Known, fixed dashboards; queries must be ultra-cheap | Free-form questions from an AI need arbitrary `GROUP BY`s. You'd need a rollup for every combination |
| **Differential privacy policy** (`differential_privacy_policy`) | BigQuery adds calibrated noise and tracks a privacy budget | Strong mathematical guarantees; protects against differencing attacks | Noisy numbers confuse business users; budget management is a new operational burden |
| **Rules in the prompt / SQL validator only** | Tell the LLM "always aggregate, never show groups under 10" | Never as the *only* control | A prompt is a suggestion; jailbreaks and bugs bypass it. Use it *in addition to* engine enforcement, to produce better SQL |
| **Row-level security** | Filters rows per user | Different readers see different subsets (region managers) | It solves "who sees which rows", not "small-group disclosure" |

**5. Trade-offs.**
- *Security:* strong against small-group disclosure. **Not** a complete defence against differencing (comparing two large overlapping queries); see §9.
- *Usability:* queries need the extra clause, and fine-grained results get suppressed (T9 showed only 518 of 2.4M events visible at brand × state × date × hour). The AI must *explain* suppression to users.
- *Coupling:* the AI's SQL generator must know which views require `WITH AGGREGATION_THRESHOLD`.
- *Residual weakness:* anonymous privacy units are **sessions**, so one anonymous person with many sessions counts as many units (§9).

**6. Failure mode if skipped.** Without the policy, the agent (or a manipulated agent) can run `GROUP BY state, event_date, event_hour, browser` and isolate single visitors. There's no error, and no alert; it just returns rows. That's an audit finding at best, and a privacy incident at worst.

**7. Soundbite.**
> "Privacy rules live in the engine, not the prompt. The semantic view has an aggregation-threshold policy with k=10, so any query that would reveal a group of fewer than ten people is suppressed by BigQuery, regardless of who or what wrote the SQL."

---

### 3.3 Access tests T6–T9 and the predicate fix

```python
CASES += [
  ("T6 web_events non-aggregate fails", "SELECT * FROM web_events LIMIT 5", BadRequest),
  ("T7 coarse grain returns every event", "...GROUP BY page_type", 2416143),
  ("T8 curated.events is denied", "SELECT * FROM curated.events LIMIT 1", Forbidden),
  ("T9 fine grain suppresses small groups", "...GROUP BY brand, state, event_date, event_hour",
   lambda v: v is not None and v < 2416143),
]
# runner:
if callable(expect) and not isinstance(expect, type):   ok = bool(expect(value))
else:                                                    ok = expect == value
```

**1. What it is.** An automated test suite that logs in **as the AI agent** and checks four facts: raw queries are rejected, coarse aggregates are complete, curated is invisible, and fine aggregates are suppressed.

**2. Why it exists here.** Security configuration drifts silently. Someone grants a role "temporarily", or a Terraform refactor changes an ACL. These tests turn "the agent is confined" from a belief into a check that runs **after every apply** (§5.3).

**3. Why this exact form.**

| Choice | Reason |
|---|---|
| **Runs as `sa-analyst-agent` via impersonation** | Testing as admin proves nothing about the agent. Your Day 6 T3 run in the console proved the engine works, but not the agent's confinement |
| **Negative tests (T6, T8)** | Most security bugs are "allowed when it shouldn't be". Testing only the happy path misses them |
| **Exact expected numbers (T3 = 95,721; T7 = 2,416,143)** | Computed independently (the Day 6 k-check). A match proves the engine and your math agree |
| **A predicate for T9** | The exact suppressed count isn't the point. "Strictly less than the total" is what proves suppression happens |
| **`isinstance(expect, type)` check** | Exception classes are *also* callable in Python. Without this check, `BadRequest(value)` would be "called" as a predicate. The first T9 FAIL (`got 518`) happened because the old line compared `lambda == 518`, which is always `False` |
| **Exit code 1 on any FAIL** | So CI marks the run red automatically |

**4. Alternatives.**

| Alternative | Wins when | Loses when |
|---|---|---|
| **pytest with fixtures** | Larger suites, reports, parametrization; the team already uses pytest | Slightly more setup. A good next step once there are 20+ cases |
| **Policy Analyzer checks only** (IAM-side proof) | Proving *who has* a permission | It doesn't prove the *query behaviour* (thresholds, view logic). Use both |
| **Manual testing in the console** | A first exploration | Not repeatable; runs as the wrong identity; nobody does it after every change |

**5. Trade-offs.** It needs a CI identity that can impersonate the agent (§4.1). Each run costs a few MB of scanning. The tests hard-code the dataset's row counts, which is fine for static data, but with live data you'd assert ratios or bounds instead.

**6. Failure mode if skipped.** An IAM change that widens the agent's access sails through plan (Terraform sees nothing wrong) and through apply. You find out from an audit, or an incident.

**7. Soundbite.**
> "Every apply is followed by an access regression suite that runs *as the AI agent*. It must be rejected on raw and curated, rejected on non-aggregate queries, and see exactly the expected totals on aggregates. Security that isn't continuously tested is just documentation."

---

## 4. CI guardrails: identity, configuration, and rules

### 4.1 `ci_can_test_as_agent`: CI may impersonate the agent

```hcl
resource "google_service_account_iam_member" "ci_can_test_as_agent" {
  service_account_id = google_service_account.analyst_agent.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:sa-tf-ci@hanuman-0002.iam.gserviceaccount.com"
}
```

**1. What it is.** Permission for the deployer to mint short-lived tokens *as the agent*, and only as the agent.

**2. Why it exists here.** The post-apply tests (§3.3) must run as the agent, from CI.

**3. Why this exact form.**
- **`google_service_account_iam_member`** (granted *on the agent SA*), **not** a project-level `TokenCreator`. A project-level grant would let `sa-tf-ci` become *every* service account in the project. That's a privilege-escalation path.
- **`_member` (additive)** rather than `_policy` (authoritative), so it won't wipe the existing admins' TokenCreator binding.
- **Applied locally first.** CI's first run needs it, so it can't be created by the very pipeline that depends on it.

**4. Alternatives.**

| Alternative | Wins when | Loses when |
|---|---|---|
| **A dedicated `sa-ci-tester`** that only impersonates the agent | Strict separation of duties: the deployer can't read data through the agent | One more identity to manage. The right move in "team mode" |
| **Run the tests with the agent's own key** | Never | Keys are exactly what WIF eliminated |
| **No CI tests, only manual ones** | Prototypes | Drift goes unnoticed |

**5. Trade-offs.** The deployer can now read whatever the agent can read (semantic aggregates). That's low risk, because the agent sees less than `sa-tf-ci` already does. It is still an extra edge in the identity graph, and it should be listed in your access review.

**6. Failure mode if skipped.** CI's test step fails with `Permission 'iam.serviceAccounts.getAccessToken' denied`, after a successful apply. The infrastructure changed, but the run is red.

**7. Soundbite.**
> "CI impersonates the agent for tests through a resource-level TokenCreator grant on that single service account, never project-wide, because project-wide TokenCreator means you can become any service account."

---

### 4.2 Inputs: `TF_VAR_*` variables and secrets, plus `terraform.tfvars.example`

```yaml
env:
  TF_VAR_project_id:       ${{ vars.TF_VAR_PROJECT_ID }}
  TF_VAR_region:           ${{ vars.TF_VAR_REGION }}
  TF_VAR_admins_group:     ${{ secrets.TF_VAR_ADMINS_GROUP }}
  TF_VAR_developers_group: ${{ secrets.TF_VAR_DEVELOPERS_GROUP }}
```

**1. What it is.** The way CI receives Terraform input values: non-sensitive ones as repo **variables**, identifying ones as repo **secrets**, both passed as environment variables that Terraform reads automatically.

**2. Why it exists here.** Your `terraform.tfvars` is untracked (gitignored), so CI checked out a repo with no inputs and failed with "No value for required variable".

**3. Why this exact form.**

| Choice | Reason |
|---|---|
| **Env key in lowercase** (`TF_VAR_project_id`) | Terraform matches the variable name *exactly*. GitHub stores names uppercase, but lookups in `${{ }}` ignore case. The left-hand side (the env key) is what must match |
| **Group emails as `secrets`** | **Public repo means public Actions logs.** `vars` print in plain text in the env header of every step. Secrets are masked anywhere they appear in the log, including inside Terraform refresh IDs like `group:***` |
| **`project_id`, `region` as `vars`** | They already appear in the SQL files; masking them adds friction for no gain |
| **Repo-level, not environment-level** | The PR plan job deliberately doesn't use the `dev` environment (that's the approval gate), so it couldn't read environment-scoped values |
| **Only in `plan` jobs** | The `apply` job applies a saved plan file, which already contains the values |
| **`.example` file committed** | Anyone cloning the repo knows which inputs exist, without seeing yours |

**4. Alternatives.**

| Alternative | Wins when | Loses when |
|---|---|---|
| **Commit `terraform.tfvars`** | Private repo; values aren't sensitive. Simplest and fully reproducible | Public repo: publishes your org's domain and group names (reconnaissance material) |
| **Secret Manager + read at plan time** (`data "google_secret_manager_secret_version"`) | Real secrets (passwords, keys); central rotation | Values end up in state and plan anyway; overkill for group names |
| **Per-environment `.tfvars` files** (`dev.tfvars`, `prod.tfvars`) with `-var-file` | Multiple environments with different values | Same public-repo exposure as committing tfvars |
| **Terraform Cloud workspace variables** | You use Terraform Cloud | Another platform to adopt |

**5. Trade-offs.** Inputs now live in two places (local tfvars and GitHub), which can diverge. That's exactly how the comment-contaminated value got in. Validation (§4.5) is the mitigation.

**6. Failure mode if skipped.** Plan fails with "No value for required variable" (loud, and safe). The *dangerous* failure is a **wrong** value. With no validation, that becomes a plan to replace resources (§7.3).

**7. Soundbite.**
> "Non-sensitive config goes in CI variables, identifying values in masked secrets, and the repo carries a `.tfvars.example`. In a public repo, workflow logs are public, so anything printed is published."

---

### 4.3 The `allow-destroy` label

```bash
gh label create allow-destroy --color B60205 --description "Permit resource deletion in terraform plan"
```

| Heading | Content |
|---|---|
| What | A PR label that is the *only* way to let a plan with deletions pass the gate |
| Why | Deletions are sometimes intended (removing the canary). There must be an explicit, visible, auditable "yes, I mean it" |
| Why a label | It's visible on the PR, recorded in the timeline (who added it, and when), and readable by workflows. Red color = danger |
| Alternatives | A PR description keyword (easy to add by accident, not structured); a separate manual workflow for destroys (heavier, better for production); CODEOWNERS approval on deletes (team mode) |
| Failure if skipped | Either deletions are impossible (you'd bypass the gate, which defeats it) or they're always allowed (no gate at all) |
| Soundbite | "Deletion needs an explicit, auditable opt-in: a label on the PR that the pipeline checks both on the PR and again on main." |

---

### 4.4 The `dev` environment (required reviewer) and the `main` ruleset

**1. What it is.**
- The **environment** `dev` makes any job that declares `environment: dev` **pause** until a named reviewer approves.
- The **ruleset** on `main` requires a PR and a passing `plan` check, branch up to date (strict), no force pushes, and no branch deletion. Required approvals: 0.

**2. Why it exists here.** Together they ensure that **nothing reaches the real infrastructure without (a) a passing plan and (b) a human looking at the final plan**.

**3. Why this exact form.**

| Setting | Reason |
|---|---|
| Required check `plan` | Code that fails `fmt`, `validate`, plan or the destroy gate can't merge |
| **Strict** (branch must be up to date) | The plan was computed against the latest `main`. Otherwise two individually-safe PRs could combine into an unsafe state |
| **0 required approvals** | Solo repo: GitHub doesn't let a PR author approve their own PR, so 1 approval would block forever (or force you to use `--admin`, which defeats the rules) |
| Human gate moved to the **environment** | You approve the **main-branch plan** right before apply, which is the moment that matters |
| Deployment branches: `main` only | A branch can't deploy to `dev` by declaring `environment: dev` |
| No force push / no deletion | `main`'s history can't be rewritten or destroyed |

**4. Alternatives.**

| Alternative | Wins when | Loses when |
|---|---|---|
| **Team mode:** ≥1 approval + CODEOWNERS for `infra/` + "prevent self-review" on the environment | Two or more people. Four-eyes principle, which auditors expect | Solo: impossible to satisfy |
| **Classic branch protection** (older feature) | Old repos | Rulesets are newer, can target many branches, and can be layered |
| **Atlantis / Terraform Cloud approvals** | Large teams, many repos, plan comments in PRs | More platform to run |

**5. Trade-offs.** A solo setup has **no four-eyes control**: you approve your own changes. That's acceptable for a portfolio project, but document it as such. The admin bypass (`--admin`) still exists, and using it should be treated as an incident.

**6. Failure mode if skipped.** Without the ruleset, a direct push to `main` triggers apply without any PR plan review. Without the environment, applies happen automatically on merge, so a reviewer who misread the PR plan has no second chance.

**7. Soundbite.**
> "Merging requires a green plan on an up-to-date branch, and applying requires a human to approve the main-branch plan in a protected environment. Solo, the human gate is the environment; with a team, I add required reviews, CODEOWNERS and prevent-self-review."

---

### 4.5 Variable validation blocks

```hcl
variable "developers_group" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9._-]+@[a-z0-9.-]+\\.[a-z]{2,}$", var.developers_group))
    error_message = "developers_group must be a bare group email (e.g. gcp-developers@example.com)."
  }
}
```

**1. What it is.** A rule Terraform checks *before planning*. Invalid input stops the run with a clear message.

**2. Why it exists here.** A pasted comment (`… # same value as in bootstrap`) turned into a group "email" in CI. That produced a plan to **replace three dataset ACL entries**. The destroy gate caught it, but a wrong value that *doesn't* cause a delete would have gone through.

**3. Why this exact form.**
- The regex demands a **bare** email (no `group:` prefix, no spaces, no `#`). Anything else fails.
- `can(regex(...))` returns true/false instead of erroring on a non-match.
- The error message tells the reader the *expected shape*, which saves the next person debugging time.
- Lowercase only: Google emails are case-insensitive, but a mixed-case value can create needless diffs.

**4. Alternatives.**

| Alternative | Wins when | Loses when |
|---|---|---|
| **Policy-as-code on the plan** (OPA/Conftest, Sentinel) | Org-wide rules ("no `allUsers`", "group members must end with our domain") | More tooling; a validation block is the cheapest first line |
| **`precondition` blocks on resources** | Rules involving several values or data sources | For a single input's format, `validation` is clearer |
| **Typed objects** (`object({ email = string })`) | Complex inputs | Doesn't validate format by itself |

**5. Trade-offs.** It's cheap. The regex is deliberately simple; it allows some technically-invalid emails, but blocks every realistic paste error.

**6. Failure mode if skipped.** As Day 7 demonstrated: a typo becomes a destructive plan, or worse, a non-destructive wrong grant that nobody notices.

**7. Soundbite.**
> "The destroy gate catches dangerous *outputs*; input validation catches dangerous *inputs*. Identity inputs like group emails get strict regex validation, because a bad member string forces replacement of BigQuery ACL entries."

---

### 4.6 The local pre-push hook

```bash
# .git/hooks/pre-push
terraform fmt -check -recursive infra/ || { echo "Run: terraform fmt -recursive infra/"; exit 1; }
```

| Heading | Content |
|---|---|
| What | A script Git runs before every `git push`. A non-zero exit cancels the push |
| Why | `fmt -check` in CI found six unformatted files. Catching that in two seconds locally beats a red CI run two minutes later |
| Why this form | `pre-push`, not `pre-commit`: you can commit work-in-progress freely, but you can't publish unformatted code |
| Alternatives | **`pre-commit` framework** (`.pre-commit-config.yaml`, versioned, shared by the team: the team-mode answer); **`git config core.hooksPath .githooks`** (hooks folder committed to the repo); **CI only** (works, just slower feedback) |
| Trade-off | `.git/hooks` is **not versioned**: it exists only in your Cloud Shell. A teammate wouldn't get it. CI remains the real enforcement |
| Failure if skipped | Annoying, not dangerous: CI fails on formatting. It proved its value on Day 7 when the canary key re-aligned the `datasets` map |
| Soundbite | "Formatting is enforced twice: a local pre-push hook for fast feedback, and `fmt -check` in CI as the actual gate. Hooks help people, CI enforces rules." |

---

## 5. The pipelines

The full files are shown here, with explanations. §6 (the lab) tells you exactly where to put them and in which order.

### 5.1 `scripts/destroy_gate.sh`

```bash
#!/usr/bin/env bash
# Fails if the plan deletes or replaces anything, unless ALLOW_DESTROY=true.
set -euo pipefail
PLAN_JSON="${1:?usage: destroy_gate.sh tfplan.json}"
ALLOW="${ALLOW_DESTROY:-false}"

mapfile -t hits < <(jq -r '.resource_changes[]?
  | select(.change.actions | index("delete"))
  | "\(.change.actions | join("/"))\t\(.address)"' "$PLAN_JSON")

if (( ${#hits[@]} == 0 )); then
  echo "Destroy gate: no deletes or replacements."
  exit 0
fi

printf 'Destroy gate: %d resource(s) would be deleted or replaced:\n' "${#hits[@]}"
printf '  %s\n' "${hits[@]}"

if [[ "$ALLOW" == "true" ]]; then
  echo "::warning::allow-destroy label present; proceeding."
  exit 0
fi
echo "::error::Plan deletes resources. Add the 'allow-destroy' label to the PR if this is intended."
exit 1
```

**1. What it is.** A script that reads the machine-readable plan (`terraform show -json tfplan`) and fails the pipeline if any resource would be **deleted or replaced**, unless the PR carries the `allow-destroy` label.

**2. Why it exists here.** In BigQuery and IAM, many "small" edits are actually **delete + create** (a *replacement*). Changing `group_by_email` on a dataset-access entry is one example. A replaced dataset ACL means a window with no access; a replaced dataset can mean **lost data**. Humans skim plans; scripts don't.

**3. Why this exact form, line by line.**

| Line | Meaning |
|---|---|
| `set -euo pipefail` | Stop on any error (`-e`), on unset variables (`-u`), and on failures inside pipes (`pipefail`). Without it, a broken `jq` could silently "pass" |
| `${1:?usage…}` | Fail with a usage message if no file is given |
| `${ALLOW_DESTROY:-false}` | Default is **deny**. Safe by default |
| `.resource_changes[]?` | Every planned change. The `?` makes empty plans not error |
| `index("delete")` | Matches `["delete"]` **and** replacements `["delete","create"]` / `["create","delete"]`. This one detail is why replacements are caught |
| `mapfile -t hits` | Collects the matches into a Bash array, so we can count and print them |
| `::error::` / `::warning::` | GitHub Actions *annotations*: they show up highlighted on the run page |
| Exit `1` | Fails the step, so the job fails, so the required `plan` check fails, so the PR can't merge |

**4. Alternatives.**

| Alternative | What it is | Wins when | Loses when |
|---|---|---|---|
| **`lifecycle { prevent_destroy = true }`** | Terraform refuses to plan a delete of that resource | Crown-jewel resources (the raw dataset, the state bucket) | It's per resource and static (no "unless labelled"). Removing the resource block also removes the protection. **Use it in addition**, on raw data |
| **Policy as code: OPA/Conftest** | Rego policies evaluated against the plan JSON | Many rules ("no public buckets", "labels required", "no deletes") across many repos | A new language and tool to learn. Our 20-line script is enough for one rule |
| **Terraform Cloud + Sentinel / run tasks** | Policies built into the platform | You already pay for TFC/TFE | Vendor lock-in and cost |
| **Read the plan carefully** | Human review only | Never alone | People skim long plans. Day 7's bad-input replacement would have been easy to miss |

**5. Trade-offs.** It's very cheap and easy to understand. It is a blunt instrument: *any* delete blocks, including harmless ones (the canary), so it costs a label occasionally. Edge case: Terraform ≥ 1.7 `removed` blocks can produce a "forget" action, which drops a resource from state *without* deleting it. The gate doesn't flag that, but nothing is destroyed either.

**6. Failure mode if skipped.** Day 7 shows it directly. A pasted comment in a CI variable produced `delete/create` on three dataset ACL entries. Without the gate, merging would have broken developer access, or applied a bogus member, with no alert.

**7. Soundbite.**
> "Every plan, on the PR and again on main, goes through a destroy gate that fails on any delete or replacement unless the PR has an explicit `allow-destroy` label. Its first real catch was a CI-only input error that would have replaced three BigQuery ACL entries."

---

### 5.2 `.github/workflows/tf-plan.yml`: plan on every PR

```yaml
name: tf-plan
on:
  pull_request:
    types: [opened, synchronize, reopened, labeled, unlabeled]
    paths:
      - "infra/envs/dev/**"
      - "infra/modules/**"
      - ".github/workflows/tf-*.yml"
      - "scripts/destroy_gate.sh"

permissions:
  contents: read
  id-token: write

concurrency:
  group: tf-plan-dev-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  plan:
    runs-on: ubuntu-24.04
    env:
      TF_VAR_project_id:       ${{ vars.TF_VAR_PROJECT_ID }}
      TF_VAR_region:           ${{ vars.TF_VAR_REGION }}
      TF_VAR_admins_group:     ${{ secrets.TF_VAR_ADMINS_GROUP }}
      TF_VAR_developers_group: ${{ secrets.TF_VAR_DEVELOPERS_GROUP }}
    defaults:
      run:
        working-directory: infra/envs/dev
    steps:
      - uses: actions/checkout@v5
      - uses: google-github-actions/auth@v3
        with:
          workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}
          service_account: ${{ vars.GCP_TF_SA }}
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ vars.TF_VERSION }}
          terraform_wrapper: false
      - run: terraform fmt -check -recursive ../..
      - run: terraform init -input=false
      - run: terraform validate
      - run: terraform plan -input=false -lock-timeout=5m -parallelism=4 -out=tfplan
      - run: terraform show -json tfplan > tfplan.json
      - name: Destroy gate
        env:
          ALLOW_DESTROY: ${{ contains(github.event.pull_request.labels.*.name, 'allow-destroy') }}
        run: ../../../scripts/destroy_gate.sh tfplan.json
      - name: Plan summary
        if: always() && hashFiles('infra/envs/dev/tfplan') != ''
        run: |
          {
            echo "### dev plan"
            echo '```'
            terraform show -no-color tfplan | tail -n 80
            echo '```'
          } >> "$GITHUB_STEP_SUMMARY"
```

**Line-by-line.**

| Block | What it does | Why this way |
|---|---|---|
| `on: pull_request` | Runs for PRs from branches *in this repo* | **Never `pull_request_target`**: that runs with secrets in the base repo's context and is a classic way to leak credentials to PR code from forks |
| `types: … labeled, unlabeled` | Also re-runs when labels change | Adding `allow-destroy` must re-run the gate, or the label would never take effect |
| `paths:` | Only runs when infra, these workflows or the gate change | Docs-only PRs don't burn CI minutes. **Trap:** the required `plan` check then never reports on a docs-only PR. If such a PR is blocked waiting for `plan`, add a no-op workflow that also reports `plan`, or drop the path filter |
| `permissions: contents: read` | The token can read code, nothing else | Least privilege. The default token is broader |
| `id-token: write` | Allows requesting the GitHub OIDC token | Required for WIF (§2.5) |
| `concurrency … cancel-in-progress: true` | A new push to the same PR cancels the older plan | Only the latest commit's plan matters |
| `runs-on: ubuntu-24.04` | A pinned runner image | `ubuntu-latest` changes underneath you |
| `env: TF_VAR_*` | Terraform inputs | §4.2 |
| `defaults.run.working-directory` | All `run:` steps execute in `infra/envs/dev` | Avoids `cd` in every step |
| `actions/checkout@v5` | Gets the PR's code | Pinned major version (Dependabot keeps it current) |
| `auth@v3` | Sets up WIF credentials | No keys anywhere |
| `setup-terraform` with `TF_VERSION` | The same Terraform version as your laptop | Version skew causes plan differences and state upgrades |
| `terraform_wrapper: false` | Disables a wrapper that captures output | The wrapper can interfere with `terraform show -json > file` |
| `fmt -check -recursive ../..` | Fails if any `.tf` in `infra/` is unformatted (exit 3) | Covers **both** stacks, which is why it caught drift in bootstrap too |
| `init -input=false` | Downloads providers (per the lock file), connects to state | `-input=false` means never wait for a prompt (CI has no keyboard). **This is the real WIF test** |
| `validate` | Syntax and type checks | Cheap and fast, before the slower plan |
| `plan … -lock-timeout=5m -parallelism=4 -out=tfplan` | Computes changes, saves them to a file | Waits for the state lock instead of failing. Lower parallelism avoids API rate-limit and network flakes |
| `show -json` | Converts the binary plan to JSON | The gate needs machine-readable input |
| `ALLOW_DESTROY: ${{ contains(…labels…) }}` | `true` if the PR has the label | Evaluated by GitHub, passed to the script |
| `Plan summary` with `$GITHUB_STEP_SUMMARY` | Writes the plan to the run's **Summary** page | Reviewers can read the plan without digging through logs. `hashFiles` guard: only if a plan file exists |

**Design decisions with the full framework.**

1. **What it is.** The automatic reviewer for every infrastructure PR: formatting, validity, plan and destroy gate, with the result attached to the PR as the `plan` status check.
2. **Why it exists here.** So no change reaches `main` without a computed, visible preview, and so destructive changes require explicit consent.
3. **Why this exact form.** See the table above. The key choices are WIF over keys, `pull_request` over `pull_request_target`, label-aware triggers, and the plan written to the summary.
4. **Alternatives.**

   | Alternative | Wins when | Loses when |
   |---|---|---|
   | **Cloud Build triggers** (GCP-native CI) | Org standardizes on GCP tooling; private pools inside a VPC-SC perimeter | Weaker PR integration and UX than Actions for a GitHub repo |
   | **Atlantis** (self-hosted, plans posted as PR comments, `atlantis apply` by comment) | Many teams/repos; a PR-centric workflow | You run and secure another server |
   | **Terraform Cloud / HCP Terraform** | Managed state, policies, cost estimation, private registry | Cost; state and secrets move to a vendor |

5. **Trade-offs.** Each run costs about 1–2 minutes of CI time. The plan job has read access to state, which can contain sensitive values. Public-repo logs are visible to everyone (hence secrets masking).
6. **Failure mode if skipped.** Changes are only reviewed as code diffs, not as *effects*. A one-line HCL change that replaces a dataset looks harmless in the diff.
7. **Soundbite.**
   > "Every PR gets a plan computed by the same identity and Terraform version that will apply it, using keyless OIDC auth, and the plan must pass format, validation and a destroy gate before the PR can merge."

---

### 5.3 `.github/workflows/tf-apply.yml`: plan, approve, apply, test

```yaml
name: tf-apply
on:
  push:
    branches: [main]
    paths:
      - "infra/envs/dev/**"
      - "infra/modules/**"
      - ".github/workflows/tf-*.yml"
      - "scripts/destroy_gate.sh"

permissions:
  contents: read
  id-token: write
  pull-requests: read

concurrency:
  group: tf-apply-dev
  cancel-in-progress: false

jobs:
  plan:
    runs-on: ubuntu-24.04
    env:
      TF_VAR_project_id:       ${{ vars.TF_VAR_PROJECT_ID }}
      TF_VAR_region:           ${{ vars.TF_VAR_REGION }}
      TF_VAR_admins_group:     ${{ secrets.TF_VAR_ADMINS_GROUP }}
      TF_VAR_developers_group: ${{ secrets.TF_VAR_DEVELOPERS_GROUP }}
    defaults:
      run:
        working-directory: infra/envs/dev
    steps:
      - uses: actions/checkout@v5
      - uses: google-github-actions/auth@v3
        with:
          workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}
          service_account: ${{ vars.GCP_TF_SA }}
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ vars.TF_VERSION }}
          terraform_wrapper: false
      - run: terraform init -input=false
      - run: terraform plan -input=false -lock-timeout=5m -parallelism=4 -out=tfplan
      - run: terraform show -json tfplan > tfplan.json
      - name: Labels of the merged PR
        id: pr
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          labels=$(gh api "repos/${{ github.repository }}/commits/${{ github.sha }}/pulls" \
                   --jq '(.[0].labels // []) | map(.name) | join(",")')
          if [[ ",${labels}," == *",allow-destroy,"* ]]; then a=true; else a=false; fi
          echo "allow_destroy=${a}" >> "$GITHUB_OUTPUT"
      - name: Destroy gate
        env:
          ALLOW_DESTROY: ${{ steps.pr.outputs.allow_destroy }}
        run: ../../../scripts/destroy_gate.sh tfplan.json
      - name: Plan summary
        run: |
          { echo "### dev plan (main)"; echo '```'; terraform show -no-color tfplan | tail -n 80; echo '```'; } >> "$GITHUB_STEP_SUMMARY"
      - uses: actions/upload-artifact@v4
        with:
          name: tfplan-dev
          path: infra/envs/dev/tfplan
          retention-days: 1

  apply:
    needs: plan
    runs-on: ubuntu-24.04
    environment: dev
    steps:
      - uses: actions/checkout@v5
      - uses: google-github-actions/auth@v3
        with:
          workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}
          service_account: ${{ vars.GCP_TF_SA }}
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ vars.TF_VERSION }}
          terraform_wrapper: false
      - uses: actions/download-artifact@v4
        with:
          name: tfplan-dev
          path: infra/envs/dev
      - name: Apply
        working-directory: infra/envs/dev
        run: |
          terraform init -input=false
          terraform apply -input=false -lock-timeout=5m -parallelism=4 tfplan
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Access regression (as sa-analyst-agent)
        run: |
          pip install --quiet -r requirements-dev.txt
          python tests/access/test_semantic_access.py
```

**1. What it is.** The only path by which dev infrastructure changes. On every push to `main`: re-plan, re-gate, **pause for a human**, apply exactly the approved plan, then re-test the agent's access.

**2. Why it exists here.** A PR plan can go stale: another PR may merge in between. The plan that matters is the one against `main` at apply time, and a human should see *that* plan.

**3. Why this exact form.**

| Choice | Reason |
|---|---|
| **Two jobs: `plan` then `apply`** | The approval pause sits *between* them. The approver reads the main-branch plan in the Summary, then approves. A single job with `environment:` would pause *before* the plan exists, so you'd approve blind |
| **Saved plan file passed as an artifact** | `terraform apply tfplan` applies **exactly** what was approved. If state changed since, Terraform refuses ("Saved plan is stale"): a free safety check |
| **`retention-days: 1`** | Plan files can contain sensitive values in plain text. Keep them as briefly as possible (see §9 about public repos) |
| **Gate runs again on `main`** | Defence in depth. The label is re-checked by finding the PR that produced this commit |
| **`commits/{sha}/pulls` lookup** | A `push` event doesn't carry PR labels; this API finds the merged PR. `// []` handles direct pushes with no PR (then `allow_destroy=false`) |
| **`pull-requests: read`** | Needed for that API call. Nothing more |
| **`concurrency: tf-apply-dev`, `cancel-in-progress: false`** | Never cancel an apply halfway (that can leave a partial apply). Applies run one at a time; a newer *pending* run replaces an older pending one, which is fine because each re-plans from the latest `main` |
| **`environment: dev`** | The human gate (§4.4) |
| **Access tests after apply** | Proves the change didn't widen the agent's access (§3.3) |
| **`init` again in the apply job** | Each job is a fresh machine with no providers; init downloads them (same versions, from the lock file) |

**4. Alternatives.**

| Alternative | Wins when | Loses when |
|---|---|---|
| **Apply directly on merge (no approval)** | Low-risk environments with strong PR review; speed matters | One misread plan goes straight to real resources |
| **Re-plan and apply in one job after approval** | You must not store plan files (sensitive values, public repo) | The approver can't see the exact plan that will apply |
| **Apply from the PR before merge (Atlantis style)** | `main` always reflects what's deployed *and* tested | Needs locking discipline so two PRs don't apply at once; more complex |
| **GitOps controller (Config Connector / Crossplane)** | Kubernetes-centric orgs; continuous reconciliation | A very different model; heavy for a data platform |

**5. Trade-offs.**
- *Operability:* every infra merge needs a click from you, which is friction by design.
- *Security:* the plan artifact can contain values. In a **public** repo, artifacts may be downloadable by other GitHub users during the retention window. That's a known weakness (§9).
- *Blast radius:* one apply at a time; the saved-plan check prevents surprises.

**6. Failure mode if skipped.** Without the re-plan, a stale PR plan is "approved" while main contains other changes. Without the approval, an unintended change applies immediately. Without the post-apply tests, an IAM regression ships unnoticed.

**7. Soundbite.**
> "Merging to main triggers a fresh plan against main, a second destroy gate, and a protected-environment approval where a human reads that exact plan. The saved plan file is then applied, so what was approved is exactly what runs, and an access regression suite verifies the AI agent is still confined."

---

### 5.4 The canary pull requests: proving the pipeline

| PR | Change | What it proves | Result on Day 7 |
|---|---|---|---|
| **A** | The Day 7 work itself (no infra diff, since the IAM binding was applied locally) | The whole path works end to end: WIF, plan, approval, apply, tests | `0/0/0`, T1–T9 PASS in CI |
| **B** | Add an empty dataset `ops_ci_canary` | Creates flow through the gate | `1 added` |
| **C** | Remove `ops_ci_canary` | The gate **blocks** a delete; the label **unblocks** it; the main-branch label lookup works | Blocked → label → `1 destroyed` |

**Why a canary (a throwaway resource)?** You must prove the destroy path works *before* you need it on something valuable. An empty dataset costs nothing and exercises every branch of the logic.

**Alternatives:** test the gate script locally with handcrafted plan JSON (faster, but it doesn't prove the label plumbing in GitHub); or only test in a sandbox repo (safer, but a different setup from the real one).

> **Soundbite:** "I don't trust a control until I've seen it fire. I prove gates with canary changes: create a throwaway resource, try to delete it, watch the gate block, then watch the label path allow it."

---

## 6. Hands-on lab: build all of this in a new project, by yourself

This section is a **complete, ordered runbook**. If you follow it top to bottom in a fresh project, you end with the same result as Day 7: governed events data, an AI-agent identity that can only see safe aggregates, and a CI/CD pipeline with a destroy gate, human approval and automatic access tests.

Every step has three parts:

- **Do:** the exact commands or files.
- **Check:** what you must see before moving on. **Never skip a check.** If it doesn't match, stop.
- **If it fails:** a pointer to §7 (Troubleshooting).

Estimated time: 4–6 hours spread over two sessions, plus Appendix A (about 2 hours) if your foundations don't exist yet.

### 6.1 Prerequisites

**Tools.** Cloud Shell already has all of these except possibly `gh`:

```bash
gcloud --version | head -1
terraform version
gh --version | head -1       # GitHub CLI. If missing, see https://cli.github.com
jq --version
python3 --version
git --version
```

Then log in to GitHub once with `gh auth login`.

**Foundations.** Day 7 builds on earlier days. Check each item; anything missing is built in **Appendix A**.

| # | Foundation | How to check |
|---|---|---|
| F1 | Two projects: a *bootstrap* project (state, CI identity) and a *workload* project (data) | `gcloud projects describe <PROJECT_ID>` and `gcloud projects describe <BOOTSTRAP_PROJECT>` |
| F2 | A GCS bucket for Terraform state, with versioning on | `gcloud storage buckets describe gs://<STATE_BUCKET> --format='value(versioning_enabled)'` → `True` |
| F3 | A Terraform root module for the workload project at `infra/envs/dev`, using that bucket as backend | `cd infra/envs/dev && terraform init` succeeds |
| F4 | A deployer service account `sa-tf-ci` that Terraform can use | `gcloud iam service-accounts describe sa-tf-ci@<BOOTSTRAP_PROJECT>.iam.gserviceaccount.com` |
| F5 | A WIF pool and provider restricted to your GitHub repo, and the `workloadIdentityUser` binding on `sa-tf-ci` | `gcloud iam workload-identity-pools providers describe github-oidc --workload-identity-pool=github --location=global --project=<BOOTSTRAP_PROJECT> --format='value(attributeCondition)'` → shows your repo |
| F6 | Datasets `raw_thelook`, `curated`, `semantic` in your region; `semantic` authorized on `curated` | `bq ls --project_id=<PROJECT_ID>` |
| F7 | Agent SA `sa-analyst-agent` with `READER` on `semantic` only, plus `roles/bigquery.jobUser` | `bq show --format=prettyjson <PROJECT_ID>:semantic \| jq '.access'` |
| F8 | You can impersonate `sa-tf-ci` and `sa-analyst-agent` (TokenCreator) | `gcloud auth print-access-token --impersonate-service-account=sa-tf-ci@<BOOTSTRAP_PROJECT>.iam.gserviceaccount.com >/dev/null && echo OK` |
| F9 | Groups for admins and developers (emails) | Your Cloud Identity / Workspace admin console |

### 6.2 Fill in your values once

Create `scripts/env.sh`. Every command below uses these variables.

```bash
#!/usr/bin/env bash
# scripts/env.sh — source this in every new terminal:  source scripts/env.sh
export PROJECT_ID="<PROJECT_ID>"                 # workload project, e.g. acme-data-dev
export BOOTSTRAP_PROJECT="<BOOTSTRAP_PROJECT>"   # e.g. acme-bootstrap
export REGION="us-east4"                         # where your datasets live
export GH_REPO="<OWNER>/<REPO>"                  # e.g. alice/bq-ai-analyst
export TF_SA="sa-tf-ci@${BOOTSTRAP_PROJECT}.iam.gserviceaccount.com"
export AGENT_SA="sa-analyst-agent@${PROJECT_ID}.iam.gserviceaccount.com"
```

```bash
source scripts/env.sh && echo "$PROJECT_ID $REGION $GH_REPO"
```

**Check:** the three values print correctly.

### 6.3 Target repo layout

By the end of the lab, your repo looks like this:

```text
.
├── .github/workflows/
│   ├── tf-plan.yml                 # §5.2
│   └── tf-apply.yml                # §5.3
├── infra/
│   ├── bootstrap/                  # human-applied (Appendix A)
│   └── envs/dev/
│       ├── backend.tf / providers.tf / versions.tf
│       ├── bigquery.tf / iam.tf / services.tf / outputs.tf
│       ├── variables.tf            # with validation (step 7)
│       ├── terraform.tfvars        # LOCAL ONLY, gitignored
│       ├── terraform.tfvars.example
│       └── .terraform.lock.hcl     # committed
├── scripts/
│   ├── env.sh
│   └── destroy_gate.sh             # §5.1
├── sql/
│   ├── curated/users.sql  curated/events.sql
│   └── semantic/users_demographics.sql  semantic/web_events.sql
├── tests/access/test_semantic_access.py
├── requirements-dev.txt
├── .gitignore
└── docs/pii_inventory.md  docs/evidence/ci/*.png
```

**SQL files are project-agnostic.** They contain the token `__PROJECT_ID__`, which a small helper replaces at run time. That way the same files work in any project.

```bash
# Add to scripts/env.sh:
bqrun() {  # usage: bqrun sql/curated/events.sql
  sed "s/__PROJECT_ID__/${PROJECT_ID}/g" "$1" | bq query --use_legacy_sql=false --location="${REGION}"
}
```

---

### Step 1: Load the raw tables (users, events)

The source is Google's public synthetic e-commerce dataset, `bigquery-public-data.thelook_ecommerce`, which lives in the **US multi-region**. BigQuery can't query across locations, so pick the option that matches where your datasets are.

**Option A: your datasets are in `US`** (simplest):

```bash
for t in users events; do
  bq query --use_legacy_sql=false --location=US \
    "CREATE OR REPLACE TABLE \`${PROJECT_ID}.raw_thelook.${t}\` AS SELECT * FROM \`bigquery-public-data.thelook_ecommerce.${t}\`"
done
```

**Option B: your datasets are regional** (for example `us-east4`, as on Day 5). Export to a US bucket, copy to a regional bucket, then load:

```bash
US_BKT="gs://${PROJECT_ID}-staging-us"; REG_BKT="gs://${PROJECT_ID}-staging-use4"
for t in users events; do
  bq extract --location=US --destination_format=PARQUET \
    "bigquery-public-data:thelook_ecommerce.${t}" "${US_BKT}/thelook/${t}/*.parquet"
done
gcloud storage rsync -r "${US_BKT}/thelook" "${REG_BKT}/thelook"
for t in users events; do
  bq load --location="${REGION}" --source_format=PARQUET --replace \
    "${PROJECT_ID}:raw_thelook.${t}" "${REG_BKT}/thelook/${t}/*.parquet"
done
```

**Check:**

```bash
bq query --use_legacy_sql=false --location="${REGION}" \
 "SELECT (SELECT COUNT(*) FROM \`${PROJECT_ID}.raw_thelook.users\`) users,
         (SELECT COUNT(*) FROM \`${PROJECT_ID}.raw_thelook.events\`) events"
```

Both counts are non-zero. **Write them down.** The public dataset is regenerated periodically, so your numbers may differ from Day 7's (100,000 users / 2,416,143 events). That's expected. You'll use *your* numbers from here on.

### Step 2: Users — curated table and governed view (the Day 6 pattern)

`sql/curated/users.sql`:

```sql
CREATE OR REPLACE TABLE `__PROJECT_ID__.curated.users`
CLUSTER BY country, state
OPTIONS (
  description = "thelook users, PII-minimized per docs/pii_inventory.md",
  labels = [("data_class", "internal"), ("source", "thelook"), ("layer", "curated")]
) AS
SELECT
  id                  AS user_id,
  DIV(age, 10) * 10   AS age_band,
  gender,
  city,
  state,
  country,
  traffic_source,
  created_at
  -- dropped: first_name, last_name, email, street_address, postal_code, latitude, longitude
FROM `__PROJECT_ID__.raw_thelook.users`;
```

`sql/semantic/users_demographics.sql`:

```sql
CREATE OR REPLACE VIEW `__PROJECT_ID__.semantic.users_demographics`
OPTIONS (
  privacy_policy = '{"aggregation_threshold_policy": {"threshold": 10, "privacy_unit_column": "user_id"}}',
  labels = [("data_class", "aggregate_only")]
) AS
SELECT user_id, country, state, gender, age_band, traffic_source,
       DATE(created_at) AS signup_date
FROM `__PROJECT_ID__.curated.users`;
```

```bash
bqrun sql/curated/users.sql
bqrun sql/semantic/users_demographics.sql
```

**Check:** both commands end with `Created …` or `Replaced …`.

### Step 3: Events — curated table, reconciliation, governed view

`sql/curated/events.sql`:

```sql
CREATE OR REPLACE TABLE `__PROJECT_ID__.curated.events`
PARTITION BY DATE(created_at)
CLUSTER BY event_type, page_type
OPTIONS (
  description = "thelook events, PII-minimized per docs/pii_inventory.md",
  labels = [("data_class", "internal"), ("source", "thelook"), ("layer", "curated")]
) AS
WITH e AS (
  SELECT *, REGEXP_REPLACE(uri, r"[?#].*$", "") AS uri_path
  FROM `__PROJECT_ID__.raw_thelook.events`
)
SELECT
  id AS event_id,
  user_id,
  session_id,
  sequence_number,
  created_at,
  city,
  state,
  browser,
  traffic_source,
  event_type,
  uri_path,
  CASE
    WHEN STARTS_WITH(uri_path, "/product/")    THEN "product"
    WHEN STARTS_WITH(uri_path, "/department/") THEN "department"
    ELSE LTRIM(uri_path, "/")
  END AS page_type,
  REGEXP_EXTRACT(uri_path, r"^/department/([^/]+)")                 AS department,
  REGEXP_EXTRACT(uri_path, r"/category/([^/]+)")                    AS category,
  REGEXP_EXTRACT(uri_path, r"/brand/([^/]+)")                       AS brand,
  SAFE_CAST(REGEXP_EXTRACT(uri_path, r"^/product/(\d+)$") AS INT64) AS product_id,
  COALESCE(CAST(user_id AS STRING), session_id)                     AS privacy_unit
  -- dropped: ip_address, postal_code, raw uri
FROM e;
```

```bash
bqrun sql/curated/events.sql
```

Reconcile **before** creating the view:

```bash
bq query --use_legacy_sql=false --location="${REGION}" "
SELECT
  (SELECT COUNT(*) FROM \`${PROJECT_ID}.raw_thelook.events\`) AS raw_n,
  COUNT(*)                                                   AS curated_n,
  COUNTIF(privacy_unit IS NULL)                              AS null_units,
  COUNTIF(page_type IS NULL)                                 AS null_page_type,
  COUNTIF(page_type = 'product' AND product_id IS NULL)      AS product_without_id
FROM \`${PROJECT_ID}.curated.events\`"
```

**Check:** `raw_n = curated_n`, and the other three columns are `0`. **If `null_units > 0`, stop:** some rows would sit outside the privacy rule.

`sql/semantic/web_events.sql`:

```sql
CREATE OR REPLACE VIEW `__PROJECT_ID__.semantic.web_events`
OPTIONS (
  privacy_policy = '{"aggregation_threshold_policy": {"threshold": 10, "privacy_unit_column": "privacy_unit"}}',
  labels = [("data_class", "aggregate_only")]
) AS
SELECT
  privacy_unit,
  DATE(created_at)              AS event_date,
  EXTRACT(HOUR FROM created_at) AS event_hour,
  state, browser, traffic_source, event_type,
  page_type, department, category, brand, product_id
FROM `__PROJECT_ID__.curated.events`;
```

```bash
bqrun sql/semantic/web_events.sql
```

**Check:** `Created …semantic.web_events`.

### Step 4: Record your baseline numbers

The tests assert exact numbers. You compute them **independently** (as admin, from curated or raw), so a test pass means the engine and your own math agree.

```bash
bq query --use_legacy_sql=false --location="${REGION}" "
WITH g AS (
  SELECT state, gender, DIV(age, 10) * 10 AS age_band, COUNT(*) AS n
  FROM \`${PROJECT_ID}.raw_thelook.users\` GROUP BY 1, 2, 3)
SELECT
  SUM(IF(n >= 10, n, 0))                                         AS expected_visible_users,
  (SELECT COUNT(*) FROM \`${PROJECT_ID}.curated.events\`)        AS total_events
FROM g"
```

**Check:** two numbers. On Day 7 they were `95721` and `2416143`. Yours may differ. Put yours into the test file in Step 5.

### Step 5: The access regression suite

`requirements-dev.txt`:

```text
google-cloud-bigquery
```

`tests/access/test_semantic_access.py`:

```python
"""Access regression: runs AS the analyst agent (impersonation). Exits 1 on any FAIL.

Edit the constants below for your project (lab steps 4 and 6.2).
"""
import sys

import google.auth
from google.api_core.exceptions import BadRequest, Forbidden
from google.auth import impersonated_credentials
from google.cloud import bigquery

PROJECT = "<PROJECT_ID>"
LOCATION = "us-east4"
AGENT = f"sa-analyst-agent@{PROJECT}.iam.gserviceaccount.com"

EXPECTED_VISIBLE_USERS = 95721   # from lab step 4
TOTAL_EVENTS = 2416143           # from lab step 4

U = f"`{PROJECT}.semantic.users_demographics`"
W = f"`{PROJECT}.semantic.web_events`"

# (name, sql, expected) — expected is an exception class, an exact value, or a predicate.
CASES = [
    ("T1 non-aggregate select fails", f"SELECT * FROM {U} LIMIT 5", BadRequest),
    ("T2 group-by without threshold fails",
     f"SELECT state, COUNT(*) FROM {U} GROUP BY state", BadRequest),
    ("T3 threshold query returns expected visible users",
     f"""SELECT SUM(users) FROM (SELECT WITH AGGREGATION_THRESHOLD
         state, gender, age_band, COUNT(*) AS users FROM {U}
         GROUP BY state, gender, age_band)""", EXPECTED_VISIBLE_USERS),
    ("T4 curated.users is denied", f"SELECT * FROM `{PROJECT}.curated.users` LIMIT 1", Forbidden),
    ("T5 raw is denied", f"SELECT * FROM `{PROJECT}.raw_thelook.users` LIMIT 1", Forbidden),
    ("T6 web_events non-aggregate fails", f"SELECT * FROM {W} LIMIT 5", BadRequest),
    ("T7 coarse grain returns every event",
     f"""SELECT SUM(n) FROM (SELECT WITH AGGREGATION_THRESHOLD page_type, COUNT(*) AS n
         FROM {W} GROUP BY page_type)""", TOTAL_EVENTS),
    ("T8 curated.events is denied", f"SELECT * FROM `{PROJECT}.curated.events` LIMIT 1", Forbidden),
    ("T9 fine grain suppresses small groups",
     f"""SELECT SUM(n) FROM (SELECT WITH AGGREGATION_THRESHOLD brand, state, event_date, event_hour,
         COUNT(*) AS n FROM {W} GROUP BY brand, state, event_date, event_hour)""",
     lambda v: v is not None and v < TOTAL_EVENTS),
]


def client() -> bigquery.Client:
    source, _ = google.auth.default()
    creds = impersonated_credentials.Credentials(
        source_credentials=source,
        target_principal=AGENT,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=PROJECT, credentials=creds, location=LOCATION)


def main() -> int:
    bq, failed = client(), 0
    for name, sql, expect in CASES:
        try:
            value = next(iter(bq.query(sql).result()))[0]
            if callable(expect) and not isinstance(expect, type):
                ok = bool(expect(value))          # predicate
            else:
                ok = expect == value              # exact value (an exception class never equals a value)
            detail = f"got {value}"
        except (BadRequest, Forbidden) as e:
            ok = isinstance(expect, type) and isinstance(e, expect)
            detail = f"{type(e).__name__}: {e.message[:90]}"
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

```bash
pip install --quiet -r requirements-dev.txt
python3 tests/access/test_semantic_access.py
```

**Check:** nine lines, all `PASS`. If T4, T5 or T8 come back as `PASS` with a *value* instead of `Forbidden`, the agent can read data it shouldn't. **Stop and fix IAM before continuing.**

### Step 6: Let CI impersonate the agent (applied locally)

Add to `infra/envs/dev/iam.tf`. Adjust `google_service_account.analyst_agent` to whatever your agent resource is named.

```hcl
resource "google_service_account_iam_member" "ci_can_test_as_agent" {
  service_account_id = google_service_account.analyst_agent.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:sa-tf-ci@${var.bootstrap_project_id}.iam.gserviceaccount.com"
}
```

If you don't have a `bootstrap_project_id` variable, add one, or hard-code the full email.

```bash
cd infra/envs/dev
GOOGLE_IMPERSONATE_SERVICE_ACCOUNT="${TF_SA}" terraform plan -parallelism=4 -out=tfplan
GOOGLE_IMPERSONATE_SERVICE_ACCOUNT="${TF_SA}" terraform apply tfplan
cd -
```

**Check:** the plan shows `1 to add, 0 to change, 0 to destroy`. Apply it this one time locally, because CI's very first run needs this binding to exist.

### Step 7: Validate identity inputs

In `infra/envs/dev/variables.tf`, add a `validation` block to each group-email variable. Keep your existing `type`/`description`.

```hcl
variable "admins_group" {
  type        = string
  description = "Bare group email, no prefix or comments"
  validation {
    condition     = can(regex("^[a-z0-9._-]+@[a-z0-9.-]+\\.[a-z]{2,}$", var.admins_group))
    error_message = "admins_group must be a bare group email (e.g. gcp-admins@example.com)."
  }
}

variable "developers_group" {
  type        = string
  description = "Bare group email, no prefix or comments"
  validation {
    condition     = can(regex("^[a-z0-9._-]+@[a-z0-9.-]+\\.[a-z]{2,}$", var.developers_group))
    error_message = "developers_group must be a bare group email (e.g. gcp-developers@example.com)."
  }
}
```
 

**Check (prove it works):**

```bash
cd infra/envs/dev
GOOGLE_IMPERSONATE_SERVICE_ACCOUNT="${TF_SA}" terraform plan -var 'developers_group=bad value # comment' 2>&1 | grep -A2 "Invalid value"
cd -
```

You must see `Invalid value for variable`. Then run a normal plan and confirm it reports **No changes**.

### Step 8: Repo files for CI

1. **`scripts/destroy_gate.sh`:** copy from §5.1, then `chmod +x scripts/destroy_gate.sh`.
2. **`.github/workflows/tf-plan.yml`:** copy from §5.2. **The extension must be `.yml`**, not `.yaml`.
3. **`.github/workflows/tf-apply.yml`:** copy from §5.3.
4. **`.gitignore`:** must contain at least these lines:

   ```text
   .terraform/
   *.tfstate*
   tfplan
   tfplan.json
   infra/**/terraform.tfvars
   docs/evidence/*.json
   ```

5. **`infra/envs/dev/terraform.tfvars.example`:** generate it from your real file, replacing values with placeholders:

   ```bash
   sed -E 's/=\s*"[^"]*"/= "CHANGE_ME"/' infra/envs/dev/terraform.tfvars > infra/envs/dev/terraform.tfvars.example
   ```

6. **The lock file is committed:** `git ls-files infra/envs/dev/.terraform.lock.hcl` must print the path. If not, `git add` it.
7. **Pre-push hook** (local helper; CI is the real enforcement):

   ```bash
   cat > .git/hooks/pre-push <<'EOF'
   #!/usr/bin/env bash
   set -euo pipefail
   terraform fmt -check -recursive infra/ || { echo "Run: terraform fmt -recursive infra/"; exit 1; }
   EOF
   chmod +x .git/hooks/pre-push
   terraform fmt -recursive infra/
   ```

**Check:**

```bash
ls .github/workflows/     # exactly tf-plan.yml and tf-apply.yml (plus any older, unrelated CI)
grep -c "TF_VAR_" .github/workflows/tf-plan.yml .github/workflows/tf-apply.yml   # 4 and 4
python3 -c "import yaml; [yaml.safe_load(open(f'.github/workflows/{f}')) for f in ('tf-plan.yml','tf-apply.yml')]; print('YAML OK')"
bash -n scripts/destroy_gate.sh && echo "gate syntax OK"
```

### Step 9: GitHub configuration

**9a. Variables (not secret) and secrets (masked).** Type each value by hand. Don't loop over your tfvars file (§7.3 explains why).

```bash
WIF_NUM=$(gcloud projects describe "${BOOTSTRAP_PROJECT}" --format='value(projectNumber)')
gh variable set GCP_WIF_PROVIDER  --body "projects/${WIF_NUM}/locations/global/workloadIdentityPools/github/providers/github-oidc"
gh variable set GCP_TF_SA         --body "${TF_SA}"
gh variable set TF_VERSION        --body "$(terraform version -json | jq -r .terraform_version)"
gh variable set TF_VAR_PROJECT_ID --body "${PROJECT_ID}"
gh variable set TF_VAR_REGION     --body "${REGION}"
gh secret   set TF_VAR_ADMINS_GROUP     --body "gcp-admins@<domain>"
gh secret   set TF_VAR_DEVELOPERS_GROUP --body "gcp-developers@<domain>"
```

If your `variables.tf` has more required variables, add one `TF_VAR_<name>` entry per variable, both here and in the two workflow `env:` blocks.

**Check:** `gh variable list` shows 5 variables, and **read every value**: no comments, no quotes, no trailing spaces. `gh secret list` shows 2 secrets.

**9b. The label.**

```bash
gh label create allow-destroy --color B60205 --description "Permit resource deletion in terraform plan"
```

**9c. The `dev` environment (UI).** Settings → **Environments** → **New environment** → name it `dev` → **Configure environment**:
- ☑ **Required reviewers** → add yourself → **Save protection rules**
- **Deployment branches and tags** → **Selected branches and tags** → **Add deployment branch or tag rule** → `main`

**9d. The `main` ruleset (UI).** Settings → **Rules** → **Rulesets** → **New ruleset** → **New branch ruleset**:
- Name: `main-protection` · Enforcement status: **Active**
- Target branches: **Add target** → **Include default branch**
- ☑ **Restrict deletions**
- ☑ **Block force pushes**
- ☑ **Require a pull request before merging** → Required approvals: **0** (solo) or **1+** (team)
- ☑ **Require status checks to pass** → ☑ *Require branches to be up to date before merging* → **Add checks** → type `plan`. It may only appear in the suggestion list after the first workflow run; you can come back and add it then.
- **Create**

**Check:**

```bash
gh api "repos/${GH_REPO}/rules/branches/main" --jq '.[].type'
```

The output should include `deletion`, `non_fast_forward`, `pull_request` and `required_status_checks`.

### Step 10: First pull request (PR-A: the pipeline itself)

```bash
git switch -c day7-events-ci
git add .github/ scripts/ sql/ tests/ requirements-dev.txt .gitignore infra/
git status                          # make sure terraform.tfvars and *.json evidence are NOT listed
git commit -m "Events curated/semantic, access tests, CI plan/apply with approval and destroy gate"
git push -u origin day7-events-ci
gh pr create --fill --base main
```

**Check (PR):** Actions → `tf-plan` → green. On the run's **Summary** page: **No changes**. The step env header shows `TF_VAR_admins_group: ***`.

```bash
gh pr merge --squash --delete-branch      # never with --admin
```

**Check (apply):** Actions → `tf-apply`:
1. The `plan` job's Summary shows **No changes**.
2. The `apply` job shows **Waiting for review**. Click **Review deployments** → ☑ `dev` → **Approve and deploy**.
3. Apply reports `0 added, 0 changed, 0 destroyed`.
4. The access regression shows **T1–T9 PASS**.

Screenshot the approval banner and the test output into `docs/evidence/ci/`.

### Step 11: Prove the gate (PR-B and PR-C)

**PR-B (create).** Add a canary dataset to your datasets definition. For example, if you use a `locals.datasets` map with `for_each`:

```hcl
ops_ci_canary = { desc = "CI canary: created and deleted to verify the destroy gate. Safe to delete.", data_class = "internal" }
```

```bash
terraform fmt -recursive infra/
git switch main && git pull && git switch -c canary-add
git commit -am "Canary: add ops_ci_canary" && git push -u origin canary-add
gh pr create --fill --base main
```

**Check:** the PR plan shows `1 to add` and the gate passes. Merge, approve, and apply shows `1 added`. Then `bq show ${PROJECT_ID}:ops_ci_canary` works.

**PR-C (delete).** Remove the canary line, then:

```bash
terraform fmt -recursive infra/
git switch main && git pull && git switch -c canary-remove
git commit -am "Canary: remove ops_ci_canary (tests destroy gate)" && git push -u origin canary-remove
gh pr create --fill --base main
```

**Check 1:** the PR plan **fails** at "Destroy gate", listing `delete  google_bigquery_dataset…ops_ci_canary…`. Screenshot it.

```bash
gh pr edit --add-label allow-destroy
```

**Check 2:** the plan re-runs automatically and passes, with the warning "allow-destroy label present".

Merge and approve. **Check 3:** apply reports `1 destroyed`, T1–T9 PASS, and `bq show ${PROJECT_ID}:ops_ci_canary` returns `Not found`.

### Step 12: Definition of done

- [ ] `curated.events` reconciles (`raw_n = curated_n`, zero nulls); `semantic.web_events` exists
- [ ] T1–T9 PASS locally **and** in CI
- [ ] PR plan runs on every infra PR; `plan` is a required check on `main`
- [ ] Apply pauses for approval; the approver sees the main-branch plan in the Summary
- [ ] The destroy gate blocked a delete, and the label allowed it (evidence screenshots saved)
- [ ] Group emails show as `***` in logs; no tfvars or JSON evidence committed
- [ ] `terraform plan` locally and in CI both report **No changes**
- [ ] Your handoff notes record your baseline numbers and any deviations from this lab

---

## 7. Troubleshooting: the real Day 7 incidents, and every error you're likely to hit

Day 7 had seven real problems. Each one taught a rule. They're written as short post-mortems (*symptom → root cause → fix → prevention*). Reading them is the fastest way to build intuition.

### 7.1 `terraform fmt -check` failed (exit code 3)

- **Symptom:** the first CI run failed at the fmt step, listing six files across `bootstrap` and `dev`.
- **Root cause:** the files had been edited without running `terraform fmt`. Nobody noticed, because nothing checked.
- **Fix:** `terraform fmt -recursive infra/`, then `git diff --stat` to confirm whitespace-only changes, then commit. `fmt` never changes meaning, so it's even safe on human-applied stacks.
- **Prevention:** the pre-push hook (§4.6) plus the CI check.
- **Lesson:** *a new check usually finds old drift first. That's the check working, not failing.*

### 7.2 "No value for required variable"

- **Symptom:** CI's plan failed with four "No value for required variable" errors.
- **Root cause:** `terraform.tfvars` is gitignored, so CI's checkout had no inputs.
- **Fix:** CI inputs via `TF_VAR_*` variables and secrets (§4.2), plus a committed `.example`.
- **Lesson:** *CI only has what's in the repo plus what you explicitly give it.*

### 7.3 The destroy gate caught a contaminated input

- **Symptom:** locally `No changes`; in CI `3 to destroy` (replace three `devs_reader` dataset-access entries).
- **Root cause:** a shell loop copied `developers_group = "…" # same value as in bootstrap` into a GitHub variable, *including the comment*. HCL treats `#` as a comment; a shell loop doesn't. Changing `group_by_email` forces replacement.
- **Diagnosis technique:** reproduce CI's input locally. `-var` beats tfvars (§2.4):

  ```bash
  terraform plan -var 'developers_group=gcp-developers@<domain> # same value as in bootstrap'
  ```

  This showed the same three replacements, so the cause was confirmed **before** changing anything.
- **Fix:** set the secret explicitly, delete the contaminated variable, and add input validation (§4.5). With validation, CI then failed fast with "Invalid value for variable".
- **Lesson:** *when CI and local disagree, the inputs differ. Reproduce CI's inputs locally first. Gates catch bad outputs; validation catches bad inputs.*

### 7.4 The apply workflow had no inputs, and the edit was made in a duplicate file

- **Symptom:** `grep TF_VAR_ tf-apply.yml` found nothing, even after editing.
- **Root cause:** the edit was saved in `tf-apply.yaml`, a second file. GitHub runs **every** file in `.github/workflows/`, so after merge there would have been two apply workflows. Path filters (`tf-*.yml`) also don't match `.yaml`.
- **Fix:** `diff` the two files, copy the good one over `tf-apply.yml`, `git rm` the `.yaml`, and check the YAML parses.
- **Lesson:** *one file per workflow, one extension (`.yml`). Every job that runs `terraform plan` needs all inputs. Grep across all workflows, not just one.*

### 7.5 "Pull request is not mergeable: base branch policy prohibits the merge"

- **Symptom:** `gh pr merge` refused, and suggested `--admin`.
- **Root cause:** a ruleset requirement wasn't satisfiable. The usual cause in a solo repo is *required approvals = 1*, because you can't approve your own PR.
- **Diagnosis:**

  ```bash
  gh pr view <N> --json mergeStateStatus,reviewDecision,statusCheckRollup
  gh api repos/<OWNER>/<REPO>/rules/branches/main
  ```

- **Fix:** set required approvals to 0 and keep the human gate in the `dev` environment. **Never use `--admin`** to get past your own controls.
- **Lesson:** *design controls the operator can actually satisfy. Otherwise people learn to bypass them.*

### 7.6 Push rejected by the pre-push hook

- **Symptom:** `git push` failed and printed `infra/envs/dev/bigquery.tf`.
- **Root cause:** adding the longer key `ops_ci_canary` re-aligned the `=` signs of the whole `datasets` map.
- **Fix:** `terraform fmt -recursive infra/`, `git commit --amend --no-edit` (safe because the branch wasn't pushed yet), push.
- **Lesson:** *always format after editing maps and locals.*

### 7.7 T9 reported FAIL with a correct value (`got 518`)

- **Root cause:** the test runner compared `lambda == 518`, which is always `False`, because the predicate edit hadn't landed.
- **Fix:** the `callable(...) and not isinstance(expect, type)` branch (§3.3).
- **Lesson:** *when a test fails with a plausible value, suspect the test before the system.*

### 7.8 Quick reference: other errors

| Error text (contains) | Likely cause | Fix |
|---|---|---|
| `unauthorized_client` / `attribute condition` | The WIF provider's condition doesn't match this repo | Check `attributeCondition` equals `assertion.repository == "<OWNER>/<REPO>"` |
| `iam.serviceAccounts.getAccessToken denied` (at init) | Missing `workloadIdentityUser` binding for the repo's principalSet on `sa-tf-ci` | Add the binding in bootstrap (Appendix A) |
| `iam.serviceAccounts.getAccessToken denied` (in the test step) | `ci_can_test_as_agent` missing | Lab step 6 |
| `storage.objects.list … 403` at init | `sa-tf-ci` can't read the state bucket | `roles/storage.objectAdmin` on the bucket |
| `Error acquiring the state lock` | Another plan/apply is running, or a crashed run left a lock | Wait (we use `-lock-timeout=5m`). If it's truly stale: `terraform force-unlock <ID>`, **only** after confirming nothing is running |
| `Saved plan is stale` | State changed between plan and apply | Expected safety behaviour; re-run the workflow |
| `dial tcp … connection refused` (Cloud Shell) | Cloud Shell network flake | Re-run with `-parallelism=4`; restart Cloud Shell |
| The apply job didn't pause for approval | No required reviewer on the `dev` environment | Lab step 9c |
| Docs-only PR stuck "waiting for status `plan`" | `paths:` filter skipped the workflow, so the required check never reported | Add a lightweight workflow that always reports a `plan` job, or remove the path filter |
| `You must use SELECT WITH AGGREGATION_THRESHOLD` | Expected for non-aggregate queries on governed views | That's T1/T2/T6 working |
| gcloud asks "API not enabled, enable it? (y/N)" | Missing service | Answer **N**, add `google_project_service` in Terraform, and apply through the pipeline |

---

## 8. Decision frameworks (use these next time without a runbook)

### 8.1 Where should a data-protection rule be enforced?

| Layer | Example | Strength | Use for |
|---|---|---|---|
| **Don't copy the data** | Drop IP in curated | Strongest: it isn't there | Fields with no consumer |
| **Engine policy** | Aggregation threshold, differential privacy | Holds against any SQL author | Small-group disclosure on shared views |
| **IAM / dataset ACL** | Agent `READER` on semantic only | Strong, coarse | Who can reach which layer |
| **Column/row security** | Policy tags, row access policies | Strong, fine-grained, easy to misconfigure | Same table, different readers |
| **Application validator** | Reject generated SQL without the threshold clause | Medium | Better UX and earlier errors |
| **Prompt instructions** | "Always aggregate" | Weakest | Steering quality, **never** as a control |

**Rule:** pick the *lowest* row that fits, and add higher rows only for user experience.

### 8.2 Where should a configuration value live?

| Value type | Example | Where |
|---|---|---|
| Public, stable | Region, project ID | Committed `.tf` defaults or CI `vars` |
| Identifying, not secret | Group emails, domain | CI `secrets` (public repo) or committed tfvars (private repo) |
| Real secret | API key, password | Secret Manager. Never in Git; avoid putting it in Terraform state |
| Per-developer | Your local test overrides | Untracked `terraform.tfvars` |

### 8.3 Which CI/CD tool?

| Situation | Choose |
|---|---|
| GitHub repo, small team, GCP | **GitHub Actions + WIF** (what we did) |
| Must run inside a VPC-SC perimeter / private network | **Cloud Build private pools** |
| Many teams and repos, PR-comment workflow | **Atlantis** |
| Want managed state, policy engine, cost estimates | **HCP Terraform / Terraform Enterprise** |

### 8.4 How to stop destructive changes

| Control | Use it for |
|---|---|
| Destroy gate on plan JSON | Every stack. A cheap, general backstop |
| `prevent_destroy` | The two or three resources whose loss is unrecoverable (raw data, state bucket) |
| Policy as code (OPA/Conftest) | When rules grow beyond "no deletes" (labels, public access, regions) |
| Separate destroy workflow + extra approver | Production |

### 8.5 How to run SQL transformations (the Day 8 decision)

| Option | Choose when |
|---|---|
| Manual `bq query` (today) | Prototype, static data, single operator |
| Scripted DDL run by CI with a dedicated transform SA | Few objects, need reproducibility and review |
| **Dataform** (GCP-native) or **dbt** | Many models, dependencies, tests/assertions, schedules, lineage |

### 8.6 Ten questions to ask before adding any resource

1. Who (which identity) creates it, and through which pipeline?
2. Which state file owns it, and could deleting that state's resources hurt it?
3. Who can read it, by **every** path (dataset ACL *and* project IAM)?
4. Does it hold personal data? What's the minimum we need?
5. What happens if it's deleted or replaced? Is recovery possible (time travel, soft delete, versioning)?
6. Does changing any of its arguments force replacement?
7. What does it cost at 10× scale, and is there a guardrail (budget, quota, partition filter)?
8. How will we know it's misconfigured: a test, an alert, an audit query?
9. Are its inputs validated?
10. Can a newcomer recreate it from the repo alone?

---

## 9. Known weaknesses (say these before an interviewer finds them)

| # | Weakness | Why it matters | Planned fix |
|---|---|---|---|
| W1 | **Plan artifact in a public repo.** The `tfplan` file contains input values (including the masked group emails) in plain text, and public-repo artifacts may be downloadable by other GitHub users during the retention window | Masking applies to logs, not to artifact contents | Private repo, **or** encrypt the artifact, **or** re-plan in the approved job (accepting a blind approval) |
| W2 | `sa-tf-ci` has `bigquery.admin` → it can **read raw PII** (Policy Analyzer, Day 6) | A compromised pipeline could exfiltrate data | Custom deployer role without `bigquery.tables.getData`/`export`; re-verify with Policy Analyzer |
| W3 | Anonymous privacy unit = **session**, so one anonymous person with many sessions counts as many "people" | Could satisfy k=10 alone in a small group | Stronger visitor ID (device/cookie), raise k for anonymous-heavy views, or differential privacy |
| W4 | Aggregation threshold doesn't stop **differencing** (subtracting two large overlapping results) | A determined analyst can still isolate individuals | Audit-log anomaly detection (Day 8+), differential privacy for sensitive views |
| W5 | SQL objects are deployed **by hand** | Not reproducible by CI, so drift is possible | Day 8 ADR: scripted DDL in CI or Dataform |
| W6 | **Solo approvals:** you approve your own changes | No four-eyes control | Team mode: ≥1 reviewer, CODEOWNERS, prevent self-review |
| W7 | Dependabot PRs can't authenticate to GCP in CI | Provider upgrades aren't plan-checked automatically | Plan locally; or Dependabot secrets plus a separate read-only plan identity |
| W8 | The pre-push hook isn't versioned | Teammates won't have it | `pre-commit` framework or `core.hooksPath` |
| W9 | Required `plan` check + `paths:` filter | Docs-only PRs can get stuck | An always-run reporter job |
| W10 | Bootstrap has no CI | Org-level changes rely on discipline | Separate pipeline with stronger approvals, or keep it manual with a runbook and drift checks |
| W11 | Tests hard-code row counts | They break if source data is refreshed | Assert ratios/bounds, or recompute the baseline in CI with a separate identity |
| W12 | Only one environment (`dev`) | No promotion path | `envs/prod` with its own state, project, environment and approvers |

---

## 10. Interview question bank (with model answers)

1. **"Why WIF instead of a service-account key in GitHub secrets?"**
   Keys are long-lived, copyable and frequently leaked. WIF exchanges a short-lived, signed GitHub OIDC token, restricted by an attribute condition to one repository, for a one-hour access token. There's nothing to rotate, and nothing worth stealing.

2. **"How do you stop Terraform from deleting something important?"**
   Three layers: a destroy gate on the plan JSON that fails on any delete or replacement unless a PR label opts in; `prevent_destroy` on the few unrecoverable resources; and a human approval on the main-branch plan. Plus recovery options (time travel, state versioning) for when all of those fail.

3. **"Why plan twice, on the PR and on main?"**
   The PR plan can be stale by the time it merges. The main plan reflects what will actually apply, and that's the one the approver reads and the saved file that gets applied.

4. **"Why apply a saved plan file?"**
   It guarantees that what was approved is exactly what runs. If state changed in between, Terraform refuses (the plan is stale) instead of silently applying something different.

5. **"How is the AI agent prevented from leaking individuals' data?"**
   It can only read the semantic layer. Raw and curated are denied by dataset ACLs, and that's verified by tests and Policy Analyzer. Semantic views carry a BigQuery aggregation-threshold policy (k=10), so any result group with fewer than ten people is suppressed by the engine, whatever SQL the agent writes.

6. **"Why not just tell the LLM to aggregate?"**
   Prompts are suggestions. Jailbreaks and bugs bypass them. Controls must hold when the SQL author is hostile, so they live in IAM and in the engine. The prompt is only for output quality.

7. **"What was the hardest bug, and how did you find it?"**
   CI planned three ACL replacements while local showed no changes. I reasoned that identical code meant different inputs, reproduced CI's input locally with `-var` (which overrides tfvars), confirmed the cause (a comment pasted into a variable), fixed it, and added input validation so the class of error now fails fast.

8. **"Why separate bootstrap and dev states?"**
   Chicken-and-egg (CI can't create its own identity), blast radius (a dev apply can't touch org policy or the CI identity), and least privilege (daily automation doesn't need org-admin rights).

9. **"What's the difference between the state lock and `.terraform.lock.hcl`?"**
   The state lock is a temporary mutex that stops concurrent applies. The lock file is committed and pins provider versions and checksums, so every machine uses identical providers.

10. **"Why is required approvals 0? Isn't that insecure?"**
    In a solo repo, self-approval is impossible, so 1 would force admin bypasses. The human gate is the protected environment, where I approve the actual main-branch plan. With a team, I'd require reviews, CODEOWNERS and prevent-self-review.

11. **"What would you change for production?"**
    A private repo or encrypted artifacts; a separate prod project, state and environment with two approvers; a custom deployer role without data read; policy as code; CI-deployed SQL (Dataform); VPC-SC; and alerting on audit logs.

12. **"How do you know your controls work?"**
    I make them fire. Canary PRs proved the gate blocks deletes and the label path allows them. The access suite runs as the agent after every apply. Day 6's k-check computed 95,721 visible users independently, and the engine returned exactly that.

13. **"Why drop data rather than restrict it with policy tags?"**
    Absent data can't be misconfigured into exposure. Policy tags are the right tool when the same table must serve readers with different rights. Without a named consumer, minimization wins.

14. **"Public repo — what leaks, and what did you do about it?"**
    Actions logs and possibly artifacts are public. Identifying values live in masked secrets, the tfvars and Policy Analyzer JSON are gitignored, and I keep the handoff notes with org/project numbers private. The remaining artifact exposure is documented as W1.

15. **"What does `pull_request_target` do, and why avoid it?"**
    It runs in the base repo's context *with secrets*, even for fork PRs. If it checks out the PR's code, untrusted code runs with your credentials. `pull_request` gives fork PRs no secrets and no OIDC token.

---

## 11. Teaching this to a junior (90-minute session)

### 11.1 Session plan

| Time | Activity | Goal |
|---|---|---|
| 0–10 | Draw §1.1 on a whiteboard *from memory* together | Shared mental model: identities, states, layers |
| 10–25 | Primer §2.2–§2.5 with live commands: `terraform plan -detailed-exitcode`, show the state object in GCS, show the lock file | Plan/state/locks stop being magic |
| 25–45 | Open a PR that changes a dataset label, and watch `tf-plan` | See a check attach to a PR; read the Summary |
| 45–60 | Open a PR that removes a canary; watch the gate fail; add the label | Feel why gates exist |
| 60–75 | Run the access suite; then temporarily grant the agent `READER` on curated *in a sandbox* and watch T4 fail; revert | Tests catch real regressions |
| 75–90 | Walk through §7.3 (the contaminated input) and ask: "how would you have debugged it?" | Debugging method, not memorization |

### 11.2 Exercises (with answers)

1. **"Change `max_time_travel_hours` on a dataset. Will the destroy gate fire?"**
   No: it's an in-place update. Confirm with `jq '.resource_changes[].change.actions'`.
2. **"Rename a dataset key in the `for_each` map. What happens?"**
   Terraform sees one delete and one create (the address changed), so the gate blocks it. Use a `moved` block to rename without destroying.
3. **"Add a `TF_VAR_` for a new variable, but only in `tf-plan.yml`. When does it break?"**
   After merge, the apply workflow's plan job fails with "No value for required variable".
4. **"Why does T7 equal the total but T9 doesn't?"**
   Coarse groups (page types) all have far more than 10 units; fine groups (brand × state × date × hour) mostly have fewer, so they're suppressed.
5. **"An analyst says the semantic view 'lost data'. What do you check?"**
   Grain. Compare totals at a coarse grain (they should match) versus a fine grain (suppression is expected). Explain that this is the privacy policy working.

### 11.3 Common junior mistakes to watch for

- Running `terraform apply` locally on the dev stack "just this once". This bypasses every gate. Locally, only `plan` (except deliberate bootstrapping steps like lab step 6).
- Using `--admin` or adding `allow-destroy` to make a red check go away without reading why it's red.
- Editing a value in GitHub and in tfvars differently.
- Testing access as themselves instead of as the agent.
- Committing `terraform.tfvars`, plan files, or evidence JSON to a public repo.

---

## 12. Glossary

| Term | Plain meaning |
|---|---|
| **Aggregation threshold** | BigQuery privacy rule: result groups need ≥ k distinct privacy units, or they're dropped |
| **Artifact** | A file passed between jobs in a workflow |
| **Authorized dataset** | A dataset whose views may read another dataset, even though the view's readers can't |
| **Blast radius** | How much can break if something goes wrong |
| **Canary** | A throwaway change used to test a control safely |
| **Destroy gate** | Our script that fails a plan containing deletes or replacements |
| **Drift** | Real infrastructure differs from what code and state say |
| **Environment (GitHub)** | A deployment target with protection rules, such as required reviewers |
| **Idempotent** | Running it twice gives the same result as running it once |
| **k-anonymity** | Each released group contains at least k people |
| **Least privilege** | Grant only the permissions needed, on the smallest scope |
| **OIDC token** | A short-lived, signed identity statement (here, issued by GitHub) |
| **Privacy unit** | The "person" counted by the threshold (`user_id`, or session for anonymous visitors) |
| **Replacement** | Terraform deletes and re-creates a resource because an argument can't change in place |
| **Ruleset** | GitHub branch rules (PR required, checks required, no force push) |
| **Squash merge** | All of a PR's commits become one commit on `main` |
| **State** | Terraform's record of what it manages |
| **Status check** | A pass/fail result attached to a PR commit |
| **WIF (Workload Identity Federation)** | Lets external identities (GitHub) act as a GCP service account without keys |

---

## Appendix A: Minimal foundations for a brand-new project (F1–F9)

Use this only if §6.1's foundation checks fail. It condenses Days 1–5 to the minimum that Day 7 needs. The hardening from those days (org policies, budgets, VPC-SC plans, DLP) is **not** included. Add it before using this with real data.

### A.1 Bootstrap stack (apply as yourself)

Enable the APIs in the bootstrap project first:

```bash
gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  cloudresourcemanager.googleapis.com storage.googleapis.com --project="${BOOTSTRAP_PROJECT}"
```

Then enable them in the workload project too:

```bash
gcloud services enable bigquery.googleapis.com iam.googleapis.com cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com storage.googleapis.com --project="${PROJECT_ID}"
```

Enabling APIs once by hand is the deliberate bootstrapping exception: Terraform can't run until these exist.

`infra/bootstrap/main.tf`:

```hcl
terraform {
  required_version = ">= 1.9"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
  # Step 1: leave this commented, apply with local state.
  # Step 2: uncomment, then run: terraform init -migrate-state
  # backend "gcs" {
  #   bucket = "<BOOTSTRAP_PROJECT>-tfstate"
  #   prefix = "bootstrap"
  # }
}

provider "google" {
  project = var.bootstrap_project_id
  region  = var.region
}

variable "bootstrap_project_id" { type = string }
variable "workload_project_id" { type = string }
variable "region" { type = string }
variable "github_repo" { type = string } # "owner/repo"
variable "admins_group" { type = string } # bare email

resource "google_storage_bucket" "tfstate" {
  name                        = "${var.bootstrap_project_id}-tfstate"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  versioning {
    enabled = true
  }
}

resource "google_service_account" "tf_ci" {
  account_id   = "sa-tf-ci"
  display_name = "Terraform CI deployer"
}

resource "google_storage_bucket_iam_member" "tf_ci_state" {
  bucket = google_storage_bucket.tfstate.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.tf_ci.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  attribute_condition = "assertion.repository == \"${var.github_repo}\""
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Only workflows from this repo may act as sa-tf-ci.
resource "google_service_account_iam_member" "wif_tf_ci" {
  service_account_id = google_service_account.tf_ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

# Admins can impersonate the deployer for local plans.
resource "google_service_account_iam_member" "admins_impersonate_tf_ci" {
  service_account_id = google_service_account.tf_ci.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "group:${var.admins_group}"
}

# What the deployer may do in the workload project.
# NOTE: bigquery.admin includes data read (weakness W2). Replace with a custom role for production.
resource "google_project_iam_member" "tf_ci_workload" {
  for_each = toset([
    "roles/bigquery.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/storage.admin",
  ])
  project = var.workload_project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.tf_ci.email}"
}
```

```bash
cd infra/bootstrap
terraform init && terraform apply \
  -var "bootstrap_project_id=${BOOTSTRAP_PROJECT}" -var "workload_project_id=${PROJECT_ID}" \
  -var "region=${REGION}" -var "github_repo=${GH_REPO}" -var "admins_group=gcp-admins@<domain>"
# then uncomment the backend block and:
terraform init -migrate-state
```

**Check:** F2, F4, F5 and F8 (the `sa-tf-ci` part) from §6.1 pass. IAM can take a few minutes to propagate.

### A.2 Dev stack foundations (apply impersonating `sa-tf-ci`)

`infra/envs/dev/versions.tf` and `providers.tf`:

```hcl
terraform {
  required_version = ">= 1.9"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
  backend "gcs" {
    bucket = "<BOOTSTRAP_PROJECT>-tfstate"
    prefix = "dev"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
```

`infra/envs/dev/variables.tf`: `project_id`, `region`, `bootstrap_project_id`, plus `admins_group` and `developers_group` **with the validation blocks from lab step 7**.

`infra/envs/dev/bigquery.tf`:

```hcl
locals {
  datasets = {
    raw_thelook = { desc = "Landing copy of thelook. Contains PII. No agent access.", data_class = "confidential" }
    curated     = { desc = "PII-minimized tables. Read via authorized views.", data_class = "confidential" }
    semantic    = { desc = "Governed views for the AI analyst agent.", data_class = "internal" }
    ops_audit   = { desc = "Audit and reconciliation evidence.", data_class = "internal" }
    ops_eval    = { desc = "Golden questions and evaluation results.", data_class = "internal" }
  }

  # raw is locked down authoritatively: only project owners and admins.
  raw_access = [
    { role = "OWNER", special_group = "projectOwners", group_by_email = null },
    { role = "OWNER", special_group = null, group_by_email = var.admins_group },
  ]
}

resource "google_bigquery_dataset" "ds" {
  for_each              = local.datasets
  project               = var.project_id
  dataset_id            = each.key
  location              = var.region
  description           = each.value.desc
  max_time_travel_hours = "48"
  labels = {
    env          = "dev"
    "data-class" = each.value.data_class
    "managed-by" = "terraform"
    layer        = replace(each.key, "_", "-")
  }

  # Authoritative ACL only on raw. Other datasets use google_bigquery_dataset_access
  # (never mix both styles on the same dataset).
  dynamic "access" {
    for_each = each.key == "raw_thelook" ? local.raw_access : []
    content {
      role           = access.value.role
      special_group  = access.value.special_group
      group_by_email = access.value.group_by_email
    }
  }
}

# Views in semantic may read curated (authorized dataset).
resource "google_bigquery_dataset_access" "semantic_reads_curated" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.ds["curated"].dataset_id
  dataset {
    dataset {
      project_id = var.project_id
      dataset_id = google_bigquery_dataset.ds["semantic"].dataset_id
    }
    target_types = ["VIEWS"]
  }
}

resource "google_bigquery_dataset_access" "devs_reader" {
  for_each       = toset(["curated", "semantic", "ops_eval"])
  project        = var.project_id
  dataset_id     = google_bigquery_dataset.ds[each.value].dataset_id
  role           = "READER"
  group_by_email = var.developers_group
}
```

`infra/envs/dev/iam.tf`:

```hcl
resource "google_service_account" "analyst_agent" {
  project      = var.project_id
  account_id   = "sa-analyst-agent"
  display_name = "AI analyst agent (semantic read only)"
}

resource "google_project_iam_member" "agent_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.analyst_agent.email}"
}

# Dataset-level only. NEVER grant the agent project-level dataViewer:
# project IAM bypasses dataset ACLs and would expose curated and raw.
resource "google_bigquery_dataset_access" "agent_semantic_reader" {
  project       = var.project_id
  dataset_id    = google_bigquery_dataset.ds["semantic"].dataset_id
  role          = "READER"
  user_by_email = google_service_account.analyst_agent.email
}

resource "google_service_account_iam_member" "admins_impersonate_agent" {
  service_account_id = google_service_account.analyst_agent.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "group:${var.admins_group}"
}
```

```bash
cd infra/envs/dev
GOOGLE_IMPERSONATE_SERVICE_ACCOUNT="${TF_SA}" terraform init
GOOGLE_IMPERSONATE_SERVICE_ACCOUNT="${TF_SA}" terraform plan -parallelism=4 -out=tfplan
GOOGLE_IMPERSONATE_SERVICE_ACCOUNT="${TF_SA}" terraform apply tfplan
git add .terraform.lock.hcl
```

**Check:** all of F1–F9 in §6.1 pass. Then start the lab at Step 1.

> **Why apply foundations locally rather than through CI?** The pipeline doesn't exist yet. This is the one deliberate exception: after lab step 10, every dev change goes through a PR.
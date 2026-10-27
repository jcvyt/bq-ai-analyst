# ADR-0001: Transformation layer for curated/semantic views
Status: Accepted — 2026-10-27

## Context
Privacy is enforced in the engine: semantic views carry aggregation-threshold
policies (k=10; privacy unit covers anonymous rows) and are authorized on curated.
Any tool must preserve threshold options, authorized-view grants, the CI destroy
gate, and access tests T1–T9.

## Options
| Option | Threshold views | Grants / IAM | CI | Notes |
|---|---|---|---|---|
| A. Terraform-managed views (current) | Native (`table` resource) | Same tool & state | Existing plan/gate/tests | No DAG, lineage, or SQL testing |
| B. Dataform | Native via `bigquery.additionalOptions` (spike) | Split: grants stay in Terraform | New workflow + WIF | DAG, assertions, lineage; policy JSON is an escaped string |
| C. dbt-bigquery | Via config / post-hook DDL | Split | New workflow | No advantage over B on GCP |

## Spike (Dataform CLI, ADC, scratch dataset `df_spike`, deleted)
- `semantic.web_events` rebuilt twice: typed `view` + `additionalOptions`, and `operations` DDL
- Policy present on both (`aggregationThresholdPolicy`)
- T9 parity: 518 / 518 (expected 518)
- Non-aggregate SELECT rejected on the native view
- Dev plan after cleanup: No changes

## Decision
Keep **A** for privacy-critical semantic views and their grants (Phase 1–2).
**B** is approved for curated-layer transformations when it is needed. Semantic
(threshold) views stay Terraform-owned, so the privacy boundary has one owner,
one state and one gate.

## Consequences
+ One tool, one state, one review gate for every privacy object
+ Dataform path proven; no capability blocker
− View SQL changes go through plan/apply; no DAG, assertions or lineage for semantic views
− If B is adopted, curated models live in two places (Dataform logic, Terraform IAM)

## Revisit triggers
- More than 10 curated models, or multi-step transformations needing a DAG or assertions
- A second contributor writing SQL
- Need for column-level lineage in Dataplex
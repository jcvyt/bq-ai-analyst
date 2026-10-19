# PII Inventory — raw_thelook (hanuman-0001, us-east4)

Owner: gcp-admins · Last reviewed: 2026-10-19 · Review: on any schema change + quarterly
Source: bigquery-public-data.thelook_ecommerce (synthetic data, treated as real PII for this project)

## 1. Method
| Item | Value |
|---|---|
| Tool | Sensitive Data Protection (DLP) inspect jobs, regional `us-east4` |
| InfoTypes | EMAIL_ADDRESS, PERSON_NAME, FIRST_NAME, LAST_NAME, STREET_ADDRESS, PHONE_NUMBER, IP_ADDRESS |
| Threshold | min_likelihood = POSSIBLE |
| Quotes stored | **No** (`include_quote=false`) — findings tables hold locations only, no PII values |
| users | Full scan, 100,000 rows — job `i-2866533…` (2026-10-16) |
| events | Random-start sample, 50,000 rows — job `i-4215257…` (2026-10-16) |
| Findings | `ops_audit.dlp_findings_users`, `ops_audit.dlp_findings_events` |
| Duplicates | events `i-8680722…` excluded; users `i-9075067…` cancelled |
| Not scanned | orders, order_items, inventory_items, products, distribution_centers — classified manually |

## 2. DLP detection quality (column level)
| Column | Expected class | DLP hit rate | Verdict |
|---|---|---|---|
| users.email | EMAIL_ADDRESS | 100,000 / 100,000 (100%) | Reliable |
| users.first_name | PERSON_NAME / FIRST_NAME | ~100% / 99.3% | Reliable |
| users.last_name | PERSON_NAME / LAST_NAME | ~100% / 99.2% | Reliable |
| users.street_address | STREET_ADDRESS | 81,818 / 100,000 (81.8%) | **18% false negatives** |
| events.ip_address | IP_ADDRESS | 50,000 / 50,000 (100%) | Reliable |
| users.postal_code | (quasi-identifier) | 233 hits | **Effectively missed** |
| users.age, gender, latitude, longitude, user_geom | (quasi-identifiers) | 0 | **Not detectable by DLP** |
| street_address, city, state, uri | — | PERSON_NAME / *_NAME hits | **False positives** (places/products named after people) |

**Conclusion:** classification is per column = DLP evidence + human review. Row-level finding counts are not a classification.

## 3. Classification tiers
| Tier | Definition | Curated layer | Semantic layer (agent) |
|---|---|---|---|
| **D — Direct identifier** | Identifies a person alone | **Dropped** | Never exposed |
| **Q — Quasi-identifier** | Re-identifying in combination | Kept or generalized | Generalized + aggregate-only, k ≥ 10 |
| **K — Pseudonymous key** | Internal ID linkable to a person | Kept | Join key only, **never projected** |
| **F — Free text / unstructured** | May contain PII | Parsed into safe fields | Raw value never exposed |
| **N — Non-sensitive** | Business attribute | Kept | Allowed |

**Principle: direct identifiers stop at raw.** Curated contains no Tier D columns.

## 4. Column inventory
### users
| Column | Tier | Evidence | Curated | Semantic |
|---|---|---|---|---|
| id | K | — | `user_id` | Join only |
| first_name, last_name | D | DLP ~100% | Drop | — |
| email | D | DLP 100% | Drop | — |
| street_address | D | DLP 81.8% + review | Drop | — |
| postal_code | Q | Review | Keep | **Exclude** |
| latitude, longitude, user_geom | Q | Review (precise location) | Drop | — |
| city | Q | Review | Keep | Aggregate-only, k ≥ 10 |
| state, country | Q (low) | Review | Keep | Allowed |
| age | Q | Review | `age_band` (e.g., 18–24, 25–34…) | `age_band` only, k ≥ 10 |
| gender | Q | Review | Keep | Aggregate-only, k ≥ 10 |
| traffic_source, created_at | N | — | Keep | Allowed |

### events
| Column | Tier | Evidence | Curated | Semantic |
|---|---|---|---|---|
| ip_address | D | DLP 100% of sample | Drop | — |
| user_id, session_id | K | — | Keep | Join only / count distinct only |
| uri | F | DLP name hits (product names) | Parse to `page_type`, `product_id` | `page_type` only |
| city, state, postal_code | Q | Review | Same rules as users | Same rules as users |
| browser, traffic_source, event_type, sequence_number, created_at | N | — | Keep | Allowed |

### Other tables (manual review)
| Table.column | Tier | Semantic |
|---|---|---|
| orders.user_id, order_items.user_id | K | Join only |
| orders.gender | Q | Aggregate-only, k ≥ 10 |
| orders.*, order_items.* (status, dates, prices, quantities) | N | Allowed |
| products.*, inventory_items.* | N | Allowed |
| distribution_centers.latitude, longitude | N (business site, not a person) | Allowed |

## 5. Semantic-layer rules (enforced; these become agent guardrails + eval cases)
1. Semantic views never select Tier D columns, and never project Tier K columns.
2. Any result grouped by a user-level dimension (city, gender, age_band) suppresses groups with **< 10 distinct users**.
3. No row-level user output: user-grain queries must aggregate.
4. `postal_code` and precise geolocation never leave curated.
5. Free-text fields are exposed only as parsed, enumerated values.
6. Negative eval cases (ops_eval): requests for emails, names, addresses, IPs, or "list customers in <small city>" must be refused or suppressed.

## 6. Approved readers of raw_thelook
| Principal | Access path | Purpose |
|---|---|---|
| gcp-admins | Dataset ACL OWNER | Break-glass, loads |
| projectOwners (special group) | Dataset ACL OWNER | Project owners (admins) |
| DLP service agent `service-236142939294@dlp-api.iam.gserviceaccount.com` | Project role `roles/dlp.serviceAgent` | PII scanning |
| sa-tf-ci | Project-level BigQuery admin role | Infra management (dataset metadata) |

Not approved: gcp-developers (verified **denied** via Policy Troubleshooter), sa-analyst-agent (verified **denied**).

## 7. Known gaps (Phase 2)
- Policy tags (column-level security) on curated Tier Q columns
- Scheduled SDP discovery profiles for all datasets (replaces one-off scans)
- DLP scan of the remaining tables + a custom infoType for postal codes
- Reconsider sa-tf-ci data-read access (it needs metadata, not data)
- CMEK on raw_thelook; VPC-SC perimeter

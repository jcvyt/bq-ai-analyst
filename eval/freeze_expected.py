# #!/usr/bin/env python3
# """
# eval/freeze_expected.py

# Freeze the golden set: execute every reference_sql AS sa-analyst-agent, capture
# the result fingerprint and row count, write the set to ops_eval.golden_questions,
# and record the snapshot marker in ops_eval.golden_set_snapshot.

# Rules enforced here, not implied:

#   1. Reference SQL executes as sa-analyst-agent, never as admin. A query that
#      would fail for the agent must fail at freeze time, not at run time.
#   2. Snapshot counts are read once, as admin (aggregates only), and asserted
#      BEFORE any fingerprint is written. A reloaded snapshot aborts the freeze
#      instead of silently producing 20 wrong fingerprints.
#   3. Ranges are half-open (>= / <). BETWEEN is rejected outright. It is
#      inclusive on both ends; it produced an 8-day "week" in three separate
#      drafts of G15 and would do the same to the next window anyone writes.
#   4. Questions are literal user text. Templating belongs in reference_sql.
#   5. ANSWER and ANSWER_WITH_CAVEAT items must freeze with expected_row_count > 0.
#      Zero rows means an empty window or a wrong anchor; a zero-row fingerprint
#      would let an empty agent answer pass.
#   6. v1 is immutable once frozen. Re-anchoring is a new set_version and a full
#      re-freeze, never a silent edit. --reanchor is required to touch an
#      existing set_version.

# Usage:
#     python eval/freeze_expected.py                       # dry-run: checks only
#     python eval/freeze_expected.py --apply               # write to BigQuery
#     python eval/freeze_expected.py --apply --reanchor    # new set_version

# Environment:
#     GOOGLE_CLOUD_PROJECT   required
#     GOLDEN_YAML            optional, defaults to eval/golden/questions_v1.yaml
# """

# import argparse
# import datetime
# import hashlib
# import json
# import os
# import re
# import sys

# import google.auth
# import yaml
# from google.auth import impersonated_credentials
# from google.cloud import bigquery


# # --------------------------------------------------------------------------- #
# # Constants
# # --------------------------------------------------------------------------- #

# AGENT_SA_TMPL     = "sa-analyst-agent@{project}.iam.gserviceaccount.com"
# LOCATION          = "us-east4"
# MAX_BYTES_BILLED  = 1_000_000_000
# ANSWERLIKE        = ("ANSWER", "ANSWER_WITH_CAVEAT")

# PLACEHOLDER_RE    = re.compile(r"[{}<>]")
# BETWEEN_RE        = re.compile(r"\bBETWEEN\b", re.I)
# SEMANTIC_REF_RE   = re.compile(r"`\{project\}\.([A-Za-z0-9_]+)\.")   # captures dataset


# # --------------------------------------------------------------------------- #
# # Clients
# # --------------------------------------------------------------------------- #

# def admin_client(project: str) -> bigquery.Client:
#     return bigquery.Client(project=project, location=LOCATION)


# def agent_client(project: str) -> bigquery.Client:
#     src, _ = google.auth.default()
#     creds = impersonated_credentials.Credentials(
#         source_credentials=src,
#         target_principal=AGENT_SA_TMPL.format(project=project),
#         target_scopes=["https://www.googleapis.com/auth/bigquery"],
#         lifetime=900,
#     )
#     return bigquery.Client(project=project, credentials=creds, location=LOCATION)


# # --------------------------------------------------------------------------- #
# # Rendering and fingerprinting
# # --------------------------------------------------------------------------- #

# def render(template: str, *, project: str, anchor: datetime.date) -> str:
#     """Substitute {project} and {anchor}.

#     .replace, not .format: SQL and regexes contain braces, and .format would
#     raise KeyError or silently mangle them.
#     """
#     return (
#         template
#         .replace("{project}", project)
#         .replace("{anchor}", anchor.isoformat())
#     )


# def fingerprint(rows) -> str:
#     """Stable hash of the result set. Floats rounded to 4dp to absorb float noise."""
#     norm = sorted(
#         json.dumps(
#             {k: round(v, 4) if isinstance(v, float) else v for k, v in dict(r).items()},
#             sort_keys=True,
#             default=str,
#         )
#         for r in rows
#     )
#     return hashlib.sha256("\n".join(norm).encode()).hexdigest()


# # --------------------------------------------------------------------------- #
# # Guards (run before any BigQuery is touched)
# # --------------------------------------------------------------------------- #

# def guard_question_literal(q: dict) -> None:
#     question = q["question"]
#     assert not PLACEHOLDER_RE.search(question), (
#         f"{q['id']}: question must be literal user text; "
#         f"templating and placeholders belong in reference_sql. Got: {question!r}"
#     )


# def guard_half_open(sql: str, qid: str) -> None:
#     """Reject BETWEEN anywhere in reference_sql. Convention, not a bug fix.

#     This also rejects numeric or string BETWEEN. If a future query genuinely
#     needs 'BETWEEN 1 AND 5', that is a PR conversation, not a silent exception.
#     """
#     assert not BETWEEN_RE.search(sql), (
#         f"{qid}: use half-open >= / < windows, not BETWEEN. "
#         f"BETWEEN is inclusive on both ends and produced an 8-day 'week' in "
#         f"three drafts of G15; it will do the same to the next window you write."
#     )


# def guard_semantic_only(sql: str, qid: str) -> None:
#     """Every backticked {project}.<dataset>. reference must be to a semantic dataset.

#     Reference SQL is ours and reviewed in PR; this catches a stray curated.*
#     that slipped through, which would silently leak data into the eval set.
#     """
#     for dataset in SEMANTIC_REF_RE.findall(sql):
#         assert dataset == "semantic", (
#             f"{qid}: reference_sql references `{{project}}.{dataset}.*`. "
#             f"Reference SQL must read only semantic.* objects."
#         )


# def guard_nonempty(q: dict, row: dict) -> None:
#     if q["expected_behavior"] in ANSWERLIKE:
#         assert row["expected_row_count"] is not None and row["expected_row_count"] > 0, (
#             f"{q['id']}: froze with {row['expected_row_count']} rows. "
#             f"Check anchor_date ({row['anchor_date']}) against MAX(event_date); "
#             f"an empty window would let an empty answer pass."
#         )


# # --------------------------------------------------------------------------- #
# # Snapshot
# # --------------------------------------------------------------------------- #

# def read_snapshot(admin: bigquery.Client, project: str) -> tuple[int, int]:
#     """Aggregate counts only. Runs as admin because the agent may not see all rows."""
#     def one(sql: str) -> int:
#         return next(iter(admin.query(sql).result()))[0]

#     users = one(f"SELECT COUNT(*) FROM `{project}.semantic.users_demographics`")
#     events = one(f"SELECT COUNT(*) FROM `{project}.semantic.events`")
#     return users, events


# def assert_snapshot(project: str, set_version: str, expected: dict,
#                     actual: tuple[int, int], allow_reanchor: bool) -> None:
#     users, events = actual
#     exp_u, exp_e = expected["users"], expected["events"]
#     if (users, events) != (exp_u, exp_e):
#         raise SystemExit(
#             f"snapshot changed: users {users} (expected {exp_u}), "
#             f"events {events} (expected {exp_e}). "
#             f"The set_version {set_version!r} fingerprints are stale. "
#             f"Re-anchor, bump set_version, update the YAML snapshot block, "
#             f"and re-freeze with --reanchor."
#         )


# def assert_set_not_frozen(admin: bigquery.Client, project: str, set_version: str,
#                           allow_reanchor: bool) -> None:
#     if allow_reanchor:
#         return
#     q = (f"SELECT COUNT(*) FROM `{project}.ops_eval.golden_questions` "
#          f"WHERE set_version = @sv")
#     job = admin.query(
#         q,
#         job_config=bigquery.QueryJobConfig(
#             query_parameters=[bigquery.ScalarQueryParameter("sv", "STRING", set_version)]
#         ),
#     )
#     n = next(iter(job.result()))[0]
#     assert n == 0, (
#         f"set_version {set_version!r} already has {n} rows in ops_eval.golden_questions. "
#         f"v1 is immutable once frozen. Bump set_version and re-freeze, "
#         f"or pass --reanchor if you are certain."
#     )


# # --------------------------------------------------------------------------- #
# # Freeze one item
# # --------------------------------------------------------------------------- #

# def freeze_item(agent: bigquery.Client, project: str, q: dict,
#                 anchor: datetime.date) -> dict:
#     sql = render(q["reference_sql"], project=project, anchor=anchor)
#     cfg = bigquery.QueryJobConfig(
#         maximum_bytes_billed=MAX_BYTES_BILLED,
#         labels={
#             "app": "bq-ai-analyst",
#             "component": "eval-freeze",
#             "qid": q["id"].lower(),
#         },
#     )
#     rows = list(agent.query(sql, job_config=cfg).result())
#     return {
#         "rendered_sql": sql,
#         "anchor_date": anchor.isoformat(),
#         "expected_row_count": len(rows),
#         "expected_result_fingerprint": fingerprint(rows),
#     }


# # --------------------------------------------------------------------------- #
# # Row assembly
# # --------------------------------------------------------------------------- #

# ROW_COLUMNS = (
#     "question_id", "set_version", "question", "category", "expected_behavior",
#     "reference_sql", "allowed_objects", "must_mention", "expected_row_count",
#     "expected_result_fingerprint", "notes", "loaded_at", "forbidden_patterns",
#     "true_count_is_below_k", "anchor_date", "rendered_sql",
# )


# def build_row(q: dict, set_version: str, anchor: datetime.date,
#               loaded_at: datetime.datetime) -> dict:
#     row = {
#         "question_id": q["id"],
#         "set_version": set_version,
#         "question": q["question"],
#         "category": q.get("category"),
#         "expected_behavior": q["expected_behavior"],
#         "reference_sql": q.get("reference_sql"),
#         "allowed_objects": q.get("allowed_objects") or [],
#         "must_mention": q.get("must_mention") or [],
#         "expected_row_count": None,
#         "expected_result_fingerprint": None,
#         "notes": q.get("notes"),
#         "loaded_at": loaded_at.isoformat(),
#         "forbidden_patterns": q.get("forbidden_patterns") or [],
#         "true_count_is_below_k": q.get("true_count_is_below_k"),
#         "anchor_date": anchor.isoformat(),
#         "rendered_sql": None,
#     }
#     assert set(row) == set(ROW_COLUMNS), (
#         f"{q['id']}: row keys drifted from schema. "
#         f"extra={set(row) - set(ROW_COLUMNS)} missing={set(ROW_COLUMNS) - set(row)}"
#     )
#     return row


# # --------------------------------------------------------------------------- #
# # Main
# # --------------------------------------------------------------------------- #

# def main() -> int:
#     ap = argparse.ArgumentParser(description="Freeze the ops_eval golden set.")
#     ap.add_argument("--apply", action="store_true", help="write to BigQuery")
#     ap.add_argument("--reanchor", action="store_true",
#                     help="allow writing an already-frozen set_version")
#     ap.add_argument("--yaml", default=os.environ.get(
#         "GOLDEN_YAML", "eval/golden/questions_v1.yaml"))
#     args = ap.parse_args()

#     project = os.environ.get("GOOGLE_CLOUD_PROJECT")
#     if not project:
#         raise SystemExit("GOOGLE_CLOUD_PROJECT is not set")

#     with open(args.yaml, "r") as f:
#         doc = yaml.safe_load(f)

#     set_version = doc["set_version"]
#     anchor      = datetime.date.fromisoformat(doc["anchor_date"])
#     questions   = doc["questions"]
#     expected_snapshot = doc["snapshot"]

#     # ---- Pass 1: static guards, no BigQuery yet ----
#     seen_ids = set()
#     for q in questions:
#         assert q["id"] not in seen_ids, f"duplicate question id: {q['id']}"
#         seen_ids.add(q["id"])
#         guard_question_literal(q)
#         sql = q.get("reference_sql") or ""
#         if sql:
#             guard_half_open(sql, q["id"])
#             guard_semantic_only(sql, q["id"])

#     # ---- Pass 2: snapshot check (fail fast, before any fingerprint) ----
#     admin = admin_client(project)
#     users, events = read_snapshot(admin, project)
#     assert_snapshot(project, set_version, expected_snapshot, (users, events),
#                     args.reanchor)
#     if args.apply:
#         assert_set_not_frozen(admin, project, set_version, args.reanchor)

#     print(f"snapshot OK: users={users} events={events} "
#           f"anchor_date={anchor} set_version={set_version}")

#     # ---- Pass 3: freeze every ANSWER item as the agent ----
#     agent = agent_client(project)
#     loaded_at = datetime.datetime.now(datetime.timezone.utc)

#     rows_out = []
#     for q in questions:
#         row = build_row(q, set_version, anchor, loaded_at)
#         if q.get("reference_sql"):
#             row.update(freeze_item(agent, project, q, anchor))
#             guard_nonempty(q, row)
#             print(f"  {q['id']:>4}  rows={row['expected_row_count']:>6}  "
#                   f"fp={row['expected_result_fingerprint'][:12]}…  "
#                   f"{q['expected_behavior']}")
#         else:
#             print(f"  {q['id']:>4}  (no reference_sql; {q['expected_behavior']})")
#         rows_out.append(row)

#     # ---- Pass 4: write ----
#     if not args.apply:
#         print(f"\nDRY RUN: {len(rows_out)} rows staged, nothing written. "
#               f"Re-run with --apply.")
#         return 0

#     errors = admin.insert_rows_json(
#         f"{project}.ops_eval.golden_questions", rows_out)
#     if errors:
#         raise SystemExit(f"insert into golden_questions failed: {errors}")

#     snap_err = admin.insert_rows_json(
#         f"{project}.ops_eval.golden_set_snapshot",
#         [{
#             "set_version": set_version,
#             "users_count": users,
#             "events_count": events,
#             "anchor_date": anchor.isoformat(),
#             "frozen_as": "sa-analyst-agent",
#             "frozen_at": loaded_at.isoformat(),
#         }],
#     )
#     if snap_err:
#         raise SystemExit(f"insert into golden_set_snapshot failed: {snap_err}")

#     print(f"\nWrote {len(rows_out)} rows to ops_eval.golden_questions "
#           f"and 1 snapshot row. set_version={set_version}")
#     return 0


# if __name__ == "__main__":
#     sys.exit(main())
#!/usr/bin/env python3
"""Freeze golden set: READ as sa-analyst-agent, WRITE to ops_eval as you (admin).
Usage: python3 eval/freeze_expected.py eval/golden/questions_v1.yaml [--replace]
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys

import google.auth
import yaml
from google.auth import impersonated_credentials
from google.cloud import bigquery

PROJECT = os.environ["WORKLOAD_PROJECT"]
LOCATION = "us-east4"
AGENT = f"sa-analyst-agent@{PROJECT}.iam.gserviceaccount.com"
TABLE = f"{PROJECT}.ops_eval.golden_questions"
EXECUTABLE = {"ANSWER", "ANSWER_WITH_CAVEAT"}

src, _ = google.auth.default()
agent = bigquery.Client(
    project=PROJECT, location=LOCATION,
    credentials=impersonated_credentials.Credentials(
        source_credentials=src, target_principal=AGENT,
        target_scopes=["https://www.googleapis.com/auth/bigquery"], lifetime=1800),
)
admin = bigquery.Client(project=PROJECT, location=LOCATION)


def run_as_agent(sql: str, qid: str):
    cfg = bigquery.QueryJobConfig(
        maximum_bytes_billed=1_000_000_000,
        labels={"app": "bq-ai-analyst", "component": "eval-freeze", "qid": qid.lower()},
    )
    job = agent.query(sql, job_config=cfg)
    rows = list(job.result())
    assert job.user_email == AGENT, f"{qid}: ran as {job.user_email}"
    return rows


def fingerprint(rows) -> str:
    norm = sorted(
        json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in dict(r).items()},
                   sort_keys=True, default=str)
        for r in rows)
    return hashlib.sha256("\n".join(norm).encode()).hexdigest()


def lint(q: dict):
    qid, sql = q["id"], q.get("reference_sql") or ""
    assert "{" not in q["question"], f"{qid}: question must be literal"
    assert not re.search(r"\bBETWEEN\b", sql, re.I), f"{qid}: use half-open >= / < windows"
    assert not re.search(r"\bCURRENT_(DATE|TIMESTAMP|DATETIME)\b", sql, re.I), f"{qid}: use {{anchor}}"
    if q["expected_behavior"] in EXECUTABLE:
        assert sql, f"{qid}: executable item needs reference_sql"
        assert re.search(r"WITH\s+AGGREGATION_THRESHOLD", sql, re.I), f"{qid}: threshold clause missing"


def check_snapshot(snap: dict):
    for view, key in [("users_demographics", "users_rows"), ("web_events", "events_rows")]:
        rows = run_as_agent(
            f"SELECT WITH AGGREGATION_THRESHOLD COUNT(*) AS n FROM `{PROJECT}.semantic.{view}`",
            "snapshot")
        n = rows[0].n
        assert n == snap[key], f"SNAPSHOT CHANGED: {view} {n} != {snap[key]}, re-freeze as new set_version"
    print(f"snapshot OK: {snap}")


def main():
    path, replace = sys.argv[1], "--replace" in sys.argv
    spec = yaml.safe_load(open(path))
    ver, anchor = spec["set_version"], str(spec["anchor_date"])
    qs = spec["questions"]

    ids = [q["id"] for q in qs]
    assert len(ids) == len(set(ids)), "duplicate question ids"
    for q in qs:
        lint(q)

    existing = list(admin.query(
        f"SELECT COUNT(*) AS n FROM `{TABLE}` WHERE set_version = @v",
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("v", "STRING", ver)])).result())[0].n
    if existing and not replace:
        sys.exit(f"{ver} already frozen ({existing} rows). Immutable: bump set_version, "
                 f"or --replace only if v1 was never used for a scored run.")

    check_snapshot(spec["snapshot"])

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    out = []
    for q in qs:
        row = {
            "question_id": q["id"], "set_version": ver, "question": q["question"],
            "category": q.get("category"), "expected_behavior": q["expected_behavior"],
            "reference_sql": q.get("reference_sql"), "allowed_objects": q.get("allowed_objects", []),
            "must_mention": q.get("must_mention", []), "forbidden_patterns": q.get("forbidden_patterns", []),
            "true_count_is_below_k": q.get("true_count_is_below_k"), "notes": q.get("notes"),
            "anchor_date": anchor, "loaded_at": now,
            "rendered_sql": None, "expected_row_count": None, "expected_result_fingerprint": None,
        }
        if q["expected_behavior"] in EXECUTABLE:
            sql = q["reference_sql"].format(project=PROJECT, anchor=anchor)
            rows = run_as_agent(sql, q["id"])
            if q.get("true_count_is_below_k"):
                assert len(rows) == 0, f"{q['id']}: expected full suppression, got {len(rows)} rows"
            else:
                assert len(rows) > 0, f"{q['id']}: empty result would make an empty answer pass"
            row.update(rendered_sql=sql, expected_row_count=len(rows),
                       expected_result_fingerprint=fingerprint(rows))
        out.append(row)
        print(f"{row['question_id']:>4} {row['expected_behavior']:<19} "
              f"rows={row['expected_row_count']} fp={(row['expected_result_fingerprint'] or '-')[:12]}")

    if existing and replace:
        admin.query(f"DELETE FROM `{TABLE}` WHERE set_version = @v",
                    job_config=bigquery.QueryJobConfig(query_parameters=[
                        bigquery.ScalarQueryParameter("v", "STRING", ver)])).result()
    admin.load_table_from_json(
        out, TABLE,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")).result()
    print(f"loaded {len(out)} rows into {TABLE} ({ver}, anchor {anchor})")


if __name__ == "__main__":
    main()
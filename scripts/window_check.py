#!/usr/bin/env python3
"""G15 window check, run AS sa-analyst-agent.
Usage:
  python3 scripts/window_check.py             # last 10 event dates -> pick anchor
  python3 scripts/window_check.py 2026-10-15  # verify half-open window for that anchor
"""
import datetime as dt
import os
import sys

import google.auth
from google.auth import impersonated_credentials
from google.cloud import bigquery

PROJECT = os.environ["WORKLOAD_PROJECT"]
AGENT = f"sa-analyst-agent@{PROJECT}.iam.gserviceaccount.com"
VIEW = f"`{PROJECT}.semantic.web_events`"
DATE_COL = "event_date"  # <-- adjust to your real column name

src, _ = google.auth.default()
creds = impersonated_credentials.Credentials(
    source_credentials=src,
    target_principal=AGENT,
    target_scopes=["https://www.googleapis.com/auth/bigquery"],
    lifetime=900,
)
client = bigquery.Client(project=PROJECT, credentials=creds, location="us-east4")


def run(sql: str):
    cfg = bigquery.QueryJobConfig(
        maximum_bytes_billed=1_000_000_000,
        labels={"app": "bq-ai-analyst", "component": "window-check"},
    )
    job = client.query(sql, job_config=cfg)
    rows = list(job.result())
    assert job.user_email == AGENT, f"ran as {job.user_email}, not the agent"
    print(f"# job {job.job_id} as {job.user_email}, billed {job.total_bytes_billed} bytes")
    return rows


if len(sys.argv) == 1:
    # Step A: find the latest dates. A low count on the last day = partial load day.
    for r in run(f"""
        SELECT WITH AGGREGATION_THRESHOLD {DATE_COL} AS d, COUNT(*) AS events
        FROM {VIEW}
        GROUP BY d ORDER BY d DESC LIMIT 10"""):
        print(r.d, r.events)
    sys.exit(0)

# Step B: verify the half-open window [anchor-7, anchor)
anchor = dt.date.fromisoformat(sys.argv[1])
rows = run(f"""
    SELECT WITH AGGREGATION_THRESHOLD {DATE_COL} AS d, COUNT(*) AS events
    FROM {VIEW}
    WHERE {DATE_COL} >= DATE_SUB(DATE '{anchor}', INTERVAL 7 DAY)
      AND {DATE_COL} <  DATE '{anchor}'
    GROUP BY d ORDER BY d""")
for r in rows:
    print(r.d, r.events)

expected = [anchor - dt.timedelta(days=i) for i in range(7, 0, -1)]
got = [r.d for r in rows]
assert got == expected, f"FAIL: expected {expected[0]}..{expected[-1]} (7 days), got {got}"
print(f"PASS: 7 days {expected[0]} .. {expected[-1]}, anchor {anchor} excluded, "
      f"total {sum(r.events for r in rows)} events")
#!/usr/bin/env python3
"""Offline tests for scripts/semantic_views.py drift logic (no GCP calls)."""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("sv", ROOT / "scripts" / "semantic_views.py")
sv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sv)


def pol(threshold="10", units=("user_id",)):
    return {"privacyPolicy": {"aggregationThresholdPolicy": {"threshold": threshold, "privacyUnitColumns": list(units)}}}


SQL = ("CREATE OR REPLACE VIEW `p.semantic.x`\n"
       "OPTIONS(privacy_policy='{\"aggregation_threshold_policy\":{\"threshold\":10,\"privacy_unit_column\":\"user_id\"}}')\n"
       "AS (\n  SELECT a, b\n  FROM `p.curated.t`\n  WHERE a > 0\n);\n")
SPEC = {"file": "x.sql", "table_id": "p.semantic.x", "threshold": 10, "unit": "user_id", "sql": SQL}
LIVE = "SELECT a, b FROM `p.curated.t` WHERE a > 0"

cases = [
    ("match paren form", sv.query_matches(SQL, "\n  SELECT a, b\n  FROM `p.curated.t`\n  WHERE a > 0\n"), True),
    ("match no-paren form", sv.query_matches("CREATE OR REPLACE VIEW v AS SELECT 1 x;", "SELECT 1 x"), True),
    ("truncated query", sv.query_matches(SQL, "SELECT a, b FROM `p.curated.t`"), False),
    ("extra clause", sv.query_matches(SQL, LIVE + " LIMIT 5"), False),
    ("empty query", sv.query_matches(SQL, ""), False),
    ("evaluate OK", sv.evaluate(SPEC, "VIEW", pol(), LIVE)[0], "OK"),
    ("threshold 5", sv.evaluate(SPEC, "VIEW", pol(threshold="5"), LIVE)[0], "DRIFT"),
    ("policy missing", sv.evaluate(SPEC, "VIEW", {}, LIVE)[0], "DRIFT"),
    ("unit changed", sv.evaluate(SPEC, "VIEW", pol(units=("session_id",)), LIVE)[0], "DRIFT"),
    ("not a view", sv.evaluate(SPEC, "TABLE", pol(), LIVE)[0], "DRIFT"),
]
specs = sv.load_specs()
cases += [
    ("repo files parsed", len(specs), 2),
    ("repo thresholds", sorted({s["threshold"] for s in specs}), [10]),
    ("repo units", sorted(s["unit"] for s in specs), ["privacy_unit", "user_id"]),
]

failed = [n for n, got, exp in cases if got != exp]
for n, got, exp in cases:
    print(f"{'PASS' if got == exp else 'FAIL'} {n}")
print(f"UNIT {len(cases) - len(failed)}/{len(cases)} passed")
sys.exit(1 if failed else 0)

#!/usr/bin/env python3
"""Offline tests for scripts/semantic_views.py drift logic (no GCP calls)."""
import importlib.util
import pathlib 
import sys
from types import SimpleNamespace as NS
import re



ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("sv", ROOT / "scripts" / "semantic_views.py")
sv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sv)

find_unmanaged = sv.find_unmanaged
run_unmanaged = sv.run_unmanaged
spec_name = sv.spec_name
target_dataset = sv.target_dataset

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
import contextlib, io

def _fake_client(extra):
    seen = []
    def lt(ds):
        seen.append(ds)
        return [NS(table_id=n, table_type=k) for n, k in OK2 + extra]
    return NS(project=None, list_tables=lt, list_routines=lambda ds: []), seen

def _exits(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except SystemExit:
        return True
    return False

REPO = {"users_demographics", "web_events"}
OK2 = [("users_demographics", "VIEW"), ("web_events", "VIEW")]
_SPECS = [{"file": f"{n}.sql", "table_id": f"`p.semantic.{n}`"} for n in sorted(REPO)]

def case_run_unmanaged():
    client, seen = _fake_client([("zz", "VIEW")])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        um = run_unmanaged(client, _SPECS)
    out = buf.getvalue()
    return um == [("zz", "VIEW")] and seen == ["p.semantic"] and "zz UNMANAGED" in out and "SUMMARY unmanaged=1" in out
NEW_CASES = [
    ("unmanaged view flagged",   lambda: find_unmanaged(OK2 + [("zz_probe", "VIEW")], REPO) == [("zz_probe", "VIEW")]),
    ("unmanaged table flagged",  lambda: find_unmanaged(OK2 + [("copy", "TABLE")], REPO) == [("copy", "TABLE")]),
    ("unmanaged routine flagged",lambda: len(find_unmanaged(OK2 + [("tvf", "ROUTINE:TABLE_VALUED_FUNCTION")], REPO)) == 1),
    ("repo-only set ok",         lambda: find_unmanaged(OK2, REPO) == []),
    ("spec_name forms",          lambda: all(spec_name({"table_id": t}) == "web_events" for t in
                                   ["`p.semantic.web_events`", "p.semantic.web_events", "semantic.web_events", "web_events"])),
    ("run_unmanaged repo-derived dataset", case_run_unmanaged),
    ("target_dataset qualified", lambda: target_dataset([{"file": "a.sql", "table_id": "p.semantic.a"},
                                                         {"file": "b.sql", "table_id": "`p.semantic.b`"}]) == "p.semantic"),
    ("target_dataset mixed fails",       lambda: _exits(target_dataset, [{"file": "a.sql", "table_id": "p.semantic.a"},
                                                                         {"file": "b.sql", "table_id": "p.curated.b"}])),
    ("target_dataset unresolvable fails",lambda: _exits(target_dataset, [{"file": "a.sql", "table_id": "semantic.a"}], None)),
    ("no delete path in source", lambda: not re.search(r"\bDROP\s+(VIEW|TABLE|FUNCTION)|delete_(table|routine|dataset)",
                                   (ROOT / "scripts" / "semantic_views.py").read_text(), re.I)),
]
cases += [(n, bool(fn()), True) for n, fn in NEW_CASES]
failed = [n for n, got, exp in cases if got != exp]
for n, got, exp in cases:
    print(f"{'PASS' if got == exp else 'FAIL'} {n}")
print(f"UNIT {len(cases) - len(failed)}/{len(cases)} passed")
sys.exit(1 if failed else 0)

#!/usr/bin/env python3
"""Semantic view deploy + drift check (ADR-0002, Option 3).

Modes:
  check      detect only; exit 0 = no drift, 2 = drift
  dry-run    dry-run every DDL file (PR check); exit 1 on failure
  reconcile  check -> deploy drifted views -> re-check; exit 1 if drift remains
Output: file names, statuses and counts only.
"""
import argparse
import json
import os
import pathlib
import re
import sys

SQL_DIR = pathlib.Path(__file__).resolve().parent.parent / "sql" / "semantic"
LABELS = {"app": "bq-ai-analyst", "component": "view-deploy"}
VIEW_RE = re.compile(r"create\s+or\s+replace\s+view\s+`?([\w.-]+)`?", re.I)
POLICY_RE = re.compile(r"privacy_policy\s*=\s*(?:'''|')(.*?)(?:'''|')", re.I | re.S)


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def parse_file(path):
    sql = path.read_text()
    m = VIEW_RE.search(sql)
    if not m:
        raise ValueError(f"{path.name}: no CREATE OR REPLACE VIEW")
    p = POLICY_RE.search(sql)
    if not p:
        raise ValueError(f"{path.name}: no privacy_policy")
    atp = json.loads(p.group(1))["aggregation_threshold_policy"]
    return {"file": path.name, "sql": sql, "table_id": m.group(1),
            "threshold": int(atp["threshold"]), "unit": atp["privacy_unit_column"]}


def load_specs():
    files = sorted(SQL_DIR.glob("*.sql"))
    if not files:
        raise SystemExit("no view files in sql/semantic")
    return [parse_file(f) for f in files]


def query_matches(file_sql, live_query):
    """Exact match: live query must be the whole body after AS (optionally wrapped in parens)."""
    f = norm(file_sql).rstrip(";").rstrip()
    q = norm(live_query)
    if not q or f.count(q) != 1:
        return False
    i = f.index(q)
    prefix, suffix = f[:i].rstrip(), f[i + len(q):].strip()
    m = re.search(r"\bAS\s*(\(?)$", prefix, re.I)
    if not m:
        return False
    return suffix == (")" if m.group(1) else "")


def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        obj = list(obj.values())
    if isinstance(obj, list):
        for v in obj:
            r = find_key(v, key)
            if r is not None:
                return r
    return None


def evaluate(spec, table_type, props, view_query):
    if table_type != "VIEW":
        return "DRIFT", f"type={table_type}"
    reasons = []
    atp = find_key(props, "aggregationThresholdPolicy")
    if not atp:
        reasons.append("privacy_policy missing")
    else:
        if int(atp.get("threshold", -1)) != spec["threshold"]:
            reasons.append(f"threshold live={atp.get('threshold')} repo={spec['threshold']}")
        units = atp.get("privacyUnitColumns") or (
            [atp["privacyUnitColumn"]] if atp.get("privacyUnitColumn") else [])
        if units != [spec["unit"]]:
            reasons.append(f"privacy_unit live={units} repo={spec['unit']}")
    if not query_matches(spec["sql"], view_query or ""):
        reasons.append("query differs")
    return ("DRIFT", "; ".join(reasons)) if reasons else ("OK", "")


def check_view(client, spec):
    from google.api_core.exceptions import NotFound
    try:
        t = client.get_table(spec["table_id"])
    except NotFound:
        return "MISSING", "view not found"
    return evaluate(spec, t.table_type, t._properties, t.view_query)


def run_check(client, specs):
    bad = []
    for s in specs:
        status, why = check_view(client, s)
        print(f"{s['file']} {status} {why}".rstrip())
        if status != "OK":
            bad.append(s)
    print(f"SUMMARY views={len(specs)} drift={len(bad)}")
    return bad

def spec_name(s):
    """Bare object name from VIEW_RE group: handles `proj.semantic.x`, semantic.x, x."""
    return s["table_id"].strip("`").split(".")[-1]


def list_live_objects(client, ds):
    """Full live inventory: tables/views/MVs/externals/snapshots + routines."""
    objs = [(t.table_id, t.table_type) for t in client.list_tables(ds)]
    objs += [(r.routine_id, f"ROUTINE:{r.type_}") for r in client.list_routines(ds)]
    return objs


def find_unmanaged(live_objects, repo_names):
    """Live objects with no repo file. Pure; offline-testable."""
    return [(n, k) for n, k in sorted(live_objects) if n not in repo_names]


def run_unmanaged(client, specs):
    """Print UNMANAGED lines; return list. Never passed to deploy()."""
    ds = target_dataset(specs, client.project)
    um = find_unmanaged(list_live_objects(client, ds), {spec_name(s) for s in specs})
    for n, k in um:
        print(f"{n} UNMANAGED live {k} has no repo file")
    print(f"SUMMARY unmanaged={len(um)}")
    return um


def deploy(client, specs, dry):
    from google.cloud import bigquery
    cfg = bigquery.QueryJobConfig(labels=LABELS, dry_run=dry, use_query_cache=False)
    for s in specs:
        job = client.query(s["sql"], job_config=cfg)
        if not dry:
            job.result()
        print(f"{s['file']} {'DRYRUN_OK' if dry else 'DEPLOYED'}")

def target_dataset(specs, default_project=None):
    """Dataset the repo files deploy to. Exactly one, and it must be `semantic`. Fails closed."""
    refs = set()
    for s in specs:
        parts = s["table_id"].strip("`").split(".")
        if len(parts) == 3:
            refs.add(f"{parts[0]}.{parts[1]}")
        elif len(parts) == 2 and default_project:
            refs.add(f"{default_project}.{parts[0]}")
        else:
            raise SystemExit(f"{s['file']}: cannot resolve dataset (set TF_VAR_PROJECT_ID)")
    if len(refs) != 1:
        raise SystemExit(f"repo files target {len(refs)} datasets; expected 1")
    ref = refs.pop()
    if not ref.endswith(".semantic"):
        raise SystemExit("repo files do not target dataset semantic")
    return ref
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["check", "dry-run", "reconcile"])
    args = ap.parse_args()
    specs = load_specs()
    from google.cloud import bigquery
    project = os.environ.get("TF_VAR_PROJECT_ID") or os.environ.get("TF_VAR_project_id") or None
    client = bigquery.Client(project=project)
    if args.mode == "dry-run":
        deploy(client, specs, dry=True)
        print(f"SUMMARY dry_run_ok={len(specs)}")
        return 0
    bad = run_check(client, specs)
    um = run_unmanaged(client, specs)
    if args.mode == "check":
        return 2 if (bad or um) else 0
    if bad:
        deploy(client, bad, dry=False)
        bad = run_check(client, specs)
    um = run_unmanaged(client, specs)
    if um:
        print("RECONCILE unmanaged objects are never deployed or dropped; remove via logged break-glass")
    print(f"RECONCILE remaining_drift={len(bad) + len(um)} unmanaged={len(um)}")
    return 1 if (bad or um) else 0


if __name__ == "__main__":
    sys.exit(main())

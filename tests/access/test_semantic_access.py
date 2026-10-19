"""Access regression: run as sa-analyst-agent via impersonation. Exit 1 on any FAIL."""
import sys
import google.auth
from google.auth import impersonated_credentials
from google.api_core.exceptions import BadRequest, Forbidden
from google.cloud import bigquery

PROJECT, LOCATION = "hanuman-0001", "us-east4"
AGENT = f"sa-analyst-agent@{PROJECT}.iam.gserviceaccount.com"
V = f"`{PROJECT}.semantic.users_demographics`"

CASES = [
    ("T1 non-aggregate select fails", f"SELECT * FROM {V} LIMIT 5", BadRequest),
    ("T2 group-by without threshold fails",
     f"SELECT state, COUNT(*) FROM {V} GROUP BY state", BadRequest),
    ("T3 threshold query returns 95721",
     f"""SELECT SUM(users) FROM (SELECT WITH AGGREGATION_THRESHOLD
         state, gender, age_band, COUNT(*) AS users FROM {V}
         GROUP BY state, gender, age_band)""", 95721),
    ("T4 curated is denied", f"SELECT * FROM `{PROJECT}.curated.users` LIMIT 1", Forbidden),
    ("T5 raw is denied", f"SELECT * FROM `{PROJECT}.raw_thelook.users` LIMIT 1", Forbidden),
]

def client() -> bigquery.Client:
    src, _ = google.auth.default()
    creds = impersonated_credentials.Credentials(
        source_credentials=src, target_principal=AGENT,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return bigquery.Client(project=PROJECT, credentials=creds, location=LOCATION)

def main() -> int:
    bq, failed = client(), 0
    for name, sql, expect in CASES:
        try:
            value = next(iter(bq.query(sql).result()))[0]
            ok = expect == value
            detail = f"got {value}"
        except (BadRequest, Forbidden) as e:
            ok = isinstance(expect, type) and isinstance(e, expect)
            detail = f"{type(e).__name__}: {e.message[:90]}"
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})", flush=True)
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
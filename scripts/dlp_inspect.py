"""DLP inspect jobs over raw_thelook -> findings (no quotes) in ops_audit."""
import time
from google.api_core.client_options import ClientOptions
from google.cloud import dlp_v2

PROJECT, LOCATION = "hanuman-0001", "us-east4"
INFO_TYPES = ["EMAIL_ADDRESS", "PERSON_NAME", "FIRST_NAME", "LAST_NAME",
              "STREET_ADDRESS", "PHONE_NUMBER", "IP_ADDRESS"]
TARGETS = {"users": 0, "events": 50_000}  # 0 = full table

client = dlp_v2.DlpServiceClient(client_options=ClientOptions(quota_project_id=PROJECT))
parent = f"projects/{PROJECT}/locations/{LOCATION}"

TERMINAL = {
    dlp_v2.DlpJob.JobState.DONE,
    dlp_v2.DlpJob.JobState.FAILED,
    dlp_v2.DlpJob.JobState.CANCELED,
}

def start(table: str, rows_limit: int) -> str:
    bq_opts = {"table_reference": {"project_id": PROJECT, "dataset_id": "raw_thelook", "table_id": table}}
    if rows_limit:
        bq_opts |= {"rows_limit": rows_limit,
                    "sample_method": dlp_v2.BigQueryOptions.SampleMethod.RANDOM_START}
    job = client.create_dlp_job(parent=parent, inspect_job={
        "storage_config": {"big_query_options": bq_opts},
        "inspect_config": {
            "info_types": [{"name": n} for n in INFO_TYPES],
            "min_likelihood": dlp_v2.Likelihood.POSSIBLE,
            "include_quote": False,
        },
        "actions": [{"save_findings": {"output_config": {"table": {
            "project_id": PROJECT, "dataset_id": "ops_audit", "table_id": f"dlp_findings_{table}"}}}}],
    })
    print(f"started {table}: {job.name}")
    return job.name


def wait(job_name: str, poll_s: int = 30) -> dlp_v2.DlpJob:
    client = dlp_v2.DlpServiceClient()
    while True:
        job = client.get_dlp_job(name=job_name)
        r = job.inspect_details.result
        pct = 100 * r.processed_bytes / r.total_estimated_bytes if r.total_estimated_bytes else 0.0
        findings = sum(s.count for s in r.info_type_stats)
        print(f"{time.strftime('%H:%M:%S')} {job.state.name:<9} {pct:5.1f}% findings={findings}",
              flush=True)
        if job.state in TERMINAL:
            if job.state != dlp_v2.DlpJob.JobState.DONE:
                raise SystemExit(f"Job ended {job.state.name}: {list(job.errors)}")
            return job
        time.sleep(poll_s)

if __name__ == "__main__":
    for name in [start(t, n) for t, n in TARGETS.items()]:
        wait(name)
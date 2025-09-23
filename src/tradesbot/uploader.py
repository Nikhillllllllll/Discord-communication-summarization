# src/tradesbot/uploader.py
from __future__ import annotations
import os
from pathlib import Path
from google.cloud import storage

INGEST_BASE = Path("/tmp/ingest")

def upload_all_days() -> int:
    """
    Upload every *.jsonl under /tmp/ingest/<day>/ to gs://$GCS_BUCKET/<day>/.
    Returns number of files uploaded. Safe to call even if nothing exists.
    """
    bucket_name = os.getenv("GCS_BUCKET", "")
    if not bucket_name:
        print("GCS_BUCKET not set; skipping upload.")
        return 0

    client = storage.Client()  # uses Cloud Run job's service account
    bucket = client.bucket(bucket_name)

    uploaded = 0
    if not INGEST_BASE.exists():
        print(f"{INGEST_BASE} does not exist; nothing to upload.")
        return 0

    for day_dir in sorted(INGEST_BASE.iterdir()):
        if not day_dir.is_dir():
            continue
        day = day_dir.name  # e.g., 2025-09-20
        for jf in day_dir.glob("*.jsonl"):
            blob = bucket.blob(f"{day}/{jf.name}")
            blob.upload_from_filename(str(jf))
            uploaded += 1
            print(f"Uploaded {jf} -> gs://{bucket_name}/{day}/{jf.name}")

    return uploaded

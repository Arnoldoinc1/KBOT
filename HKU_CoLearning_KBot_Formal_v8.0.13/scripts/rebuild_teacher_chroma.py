from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.models import StudentQARecord
from teacher_app.app import create_app


parser = argparse.ArgumentParser(
    description="Build or refresh the Teacher App Chroma semantic index from the shared database."
)
parser.add_argument(
    "--max-records",
    type=int,
    default=0,
    help="Optional upper bound; defaults to the configured teacher search corpus limit.",
)
args = parser.parse_args()

app = create_app()
with app.app_context():
    record_index = app.extensions["teacher_record_index"]
    max_records = args.max_records or app.config["TEACHER_SEARCH_MAX_RECORDS"]
    records = (
        StudentQARecord.query
        .order_by(StudentQARecord.created_at.desc())
        .limit(max(1, min(max_records, 50000)))
        .all()
    )
    if not record_index.sync(records, prune_missing=True):
        status = record_index.status(total_records=len(records))
        raise SystemExit(
            "Teacher Chroma index is unavailable: "
            f"{status.get('error') or 'unknown error'}"
        )
    print(
        "Teacher Chroma index ready: "
        f"records={len(records)} collection={record_index.collection_name} "
        f"path={record_index.persist_path}"
    )

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from knowledge_service.app import create_app


parser = argparse.ArgumentParser(
    description="Build or refresh the Knowledge Service Chroma chunk index from SQLite metadata."
)
parser.add_argument(
    "--max-chunks",
    type=int,
    default=0,
    help="Optional upper bound; defaults to all chunks.",
)
args = parser.parse_args()

app = create_app()
repository = app.extensions["knowledge_repository"]
if not repository.rebuild_semantic_index(args.max_chunks):
    status = repository.health().get("semantic_index", {})
    raise SystemExit(
        "Knowledge Chroma index is unavailable: "
        f"{status.get('error') or 'unknown error'}"
    )

chunk_count = len(repository.chunks_for_index(args.max_chunks))
print(
    "Knowledge Chroma index ready: "
    f"chunks={chunk_count} "
    f"retrieval={repository.retrieval_backend_name()}"
)

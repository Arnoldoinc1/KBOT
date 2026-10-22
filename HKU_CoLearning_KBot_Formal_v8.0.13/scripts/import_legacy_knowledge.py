from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config import env, resolve_path
from knowledge_service.repository import KnowledgeRepository


parser = argparse.ArgumentParser(description="Import original PDF/DOCX/TXT files into the independent Knowledge Service.")
parser.add_argument("source", type=Path, help="Legacy upload directory or one material file")
parser.add_argument("--data-dir", type=Path, default=resolve_path(env("KNOWLEDGE_DATA_DIR", "data/knowledge")))
args = parser.parse_args()
repository = KnowledgeRepository(args.data_dir)
files = [args.source] if args.source.is_file() else sorted(path for path in args.source.rglob("*") if path.suffix.casefold() in {".pdf", ".docx", ".txt"})
if not files:
    raise SystemExit("No supported material files found.")
for path in files:
    result = repository.upload(path.read_bytes(), path.name.split("__", 1)[-1], "legacy-import")
    print(f"{path.name}: id={result['id']} pages={result['page_count']} chunks={result['chunk_count']} duplicate={result.get('duplicate',False)}")


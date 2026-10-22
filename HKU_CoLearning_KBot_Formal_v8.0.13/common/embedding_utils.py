from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any


_MODEL_LOCK = RLock()
_MODEL_CACHE: dict[str, Any] = {}

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def semantic_query_text(query: str, model_path: str | Path = "") -> str:
    path_text = str(model_path or "").casefold()
    if "bge" in path_text:
        return f"{BGE_QUERY_PREFIX}{str(query or '').strip()}"
    return str(query or "").strip()


def load_local_sentence_transformer(model_path: str | Path):
    path = Path(model_path).expanduser() if str(model_path or "").strip() else None
    if path is None or not path.exists():
        return None
    key = str(path.resolve())
    with _MODEL_LOCK:
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            model = SentenceTransformer(key, local_files_only=True)
        except Exception:
            return None
        _MODEL_CACHE[key] = model
        return model

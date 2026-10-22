from __future__ import annotations

import hashlib
from pathlib import Path
from threading import RLock
from typing import Any, Iterable

from teacher_app.embedding_utils import load_local_sentence_transformer, semantic_query_text
from teacher_app.record_search import record_search_text


class ChromaRecordIndex:
    """Optional persistent semantic index for teacher-side student records."""

    def __init__(
        self,
        *,
        enabled: bool,
        persist_path: str | Path,
        collection_name: str,
        model_path: str | Path,
        top_k: int = 50,
    ) -> None:
        self.enabled = bool(enabled)
        self.persist_path = Path(persist_path)
        self.collection_name = str(collection_name or "student_qa_records")
        self.model_path = Path(model_path).expanduser() if str(model_path or "").strip() else None
        self.top_k = max(1, min(int(top_k or 50), 250))

        self._lock = RLock()
        self._attempted = False
        self._available = False
        self._last_error = ""
        self._client: Any = None
        self._collection: Any = None
        self._model: Any = None
        self._known_signatures: dict[str, str] = {}

    def _ensure_backend(self) -> bool:
        with self._lock:
            if self._attempted:
                return self._available
            self._attempted = True

            if not self.enabled:
                self._last_error = "disabled"
                return False
            if self.model_path is None or not self.model_path.exists():
                self._last_error = "embedding model path does not exist"
                return False

            try:
                import chromadb

                self.persist_path.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(path=str(self.persist_path))
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                self._model = load_local_sentence_transformer(self.model_path)
                if self._model is None:
                    raise RuntimeError("Could not load the local embedding model")
                self._load_existing_signatures()
                self._available = True
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                self._available = False
            return self._available

    def _load_existing_signatures(self) -> None:
        if self._collection is None:
            return
        try:
            payload = self._collection.get(include=["metadatas"])
        except Exception:
            payload = self._collection.get()
        ids = payload.get("ids") or []
        metadatas = payload.get("metadatas") or []
        self._known_signatures = {}
        for record_id, metadata in zip(ids, metadatas):
            if not isinstance(metadata, dict):
                continue
            signature = str(metadata.get("record_signature") or "")
            if signature:
                self._known_signatures[str(record_id)] = signature

    @staticmethod
    def _record_id(record: Any) -> str:
        return str(getattr(record, "id", "") or "").strip()

    @staticmethod
    def _record_signature(record: Any) -> str:
        digest = hashlib.sha256()
        for field in (
            "id",
            "student_name",
            "chapter",
            "topic",
            "question_type",
            "question",
            "answer",
            "options_or_pairs",
            "correct_answer",
            "ai_feedback",
            "teacher_feedback",
            "explanation",
            "score",
            "teacher_score",
            "teacher_verified",
            "update_time",
        ):
            digest.update(str(getattr(record, field, "") or "").encode("utf-8", errors="ignore"))
            digest.update(b"\0")
        return digest.hexdigest()

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts or self._model is None:
            return []
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [
            vector.tolist() if hasattr(vector, "tolist") else list(vector)
            for vector in vectors
        ]

    def sync(self, records: Iterable[Any], *, prune_missing: bool = False) -> bool:
        """Upsert changed records; optionally prune SQL-deleted records."""
        if not self._ensure_backend():
            return False

        current: dict[str, Any] = {}
        current_signatures: dict[str, str] = {}
        for record in records:
            record_id = self._record_id(record)
            if not record_id:
                continue
            current[record_id] = record
            current_signatures[record_id] = self._record_signature(record)

        with self._lock:
            changed = [
                (record_id, current[record_id], current_signatures[record_id])
                for record_id in current
                if self._known_signatures.get(record_id) != current_signatures[record_id]
            ]
            stale_ids = sorted(set(self._known_signatures) - set(current)) if prune_missing else []

            try:
                if changed:
                    ids = [record_id for record_id, _record, _signature in changed]
                    records_to_index = [record for _record_id, record, _signature in changed]
                    signatures = [signature for _record_id, _record, signature in changed]
                    texts = [record_search_text(record) for record in records_to_index]
                    embeddings = self._encode(texts)
                    metadatas = [
                        {
                            "record_signature": signature,
                            "student_name": str(getattr(record, "student_name", "") or ""),
                            "question_type": str(getattr(record, "question_type", "") or ""),
                        }
                        for record, signature in zip(records_to_index, signatures)
                    ]
                    self._collection.upsert(
                        ids=ids,
                        documents=texts,
                        embeddings=embeddings,
                        metadatas=metadatas,
                    )
                if stale_ids:
                    self._collection.delete(ids=stale_ids)
                self._known_signatures = current_signatures if prune_missing else {**self._known_signatures, **current_signatures}
                return True
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                return False

    def delete(self, record_ids: Iterable[str]) -> bool:
        if not self._ensure_backend():
            return False
        ids = [str(record_id) for record_id in record_ids if str(record_id or "").strip()]
        if not ids:
            return True
        with self._lock:
            try:
                self._collection.delete(ids=ids)
                for record_id in ids:
                    self._known_signatures.pop(record_id, None)
                return True
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                return False

    def search(
        self,
        records: Iterable[Any],
        query: str,
        *,
        top_k: int | None = None,
    ) -> dict[str, float] | None:
        """Return Chroma cosine scores keyed by SQL record id.

        ``None`` means the optional semantic backend is unavailable. An empty
        mapping means Chroma is available but found no usable result.
        """
        query = str(query or "").strip()
        if not query or not self.sync(records, prune_missing=False):
            return None

        with self._lock:
            if self._collection is None:
                return None
            result_limit = max(1, min(int(top_k or self.top_k), self.top_k, len(self._known_signatures)))
            if result_limit <= 0:
                return {}
            try:
                query_embedding = self._encode([semantic_query_text(query, self.model_path)])
                if not query_embedding:
                    return {}
                result = self._collection.query(
                    query_embeddings=query_embedding,
                    n_results=result_limit,
                    include=["distances"],
                )
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                return None

        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        scores: dict[str, float] = {}
        for record_id, distance in zip(ids, distances):
            try:
                score = 1.0 - float(distance)
            except (TypeError, ValueError):
                continue
            scores[str(record_id)] = max(0.0, min(1.0, score))
        return scores

    def backend_name(self, fallback: str = "hybrid-sparse-vector") -> str:
        return "chroma+rrf" if self._available else fallback

    def status(self, *, total_records: int | None = None) -> dict[str, Any]:
        total = max(0, int(total_records or 0))
        indexed = len(self._known_signatures)
        return {
            "enabled": self.enabled,
            "available": self._available,
            "collection": self.collection_name,
            "indexed_records": indexed,
            "unindexed_records": max(0, total - indexed) if total else 0,
            "error": self._last_error,
        }

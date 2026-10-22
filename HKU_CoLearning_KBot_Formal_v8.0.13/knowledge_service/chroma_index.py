from __future__ import annotations

import hashlib
from pathlib import Path
from threading import RLock
from typing import Any, Iterable

from common.embedding_utils import load_local_sentence_transformer, semantic_query_text


def chunk_embedding_text(chunk: Any) -> str:
    chapter = str(_field(chunk, "chapter_label", "chapter") or "").strip()
    section = str(_field(chunk, "section_label", "section") or "").strip()
    text = str(_field(chunk, "text") or "").strip()
    return "\n".join(item for item in (chapter, section, section, text) if item)


def _field(chunk: Any, *names: str) -> object:
    for name in names:
        if isinstance(chunk, dict) and name in chunk:
            return chunk.get(name)
        try:
            if name in chunk.keys():
                return chunk[name]
        except Exception:
            pass
        value = getattr(chunk, name, None)
        if value is not None:
            return value
    return ""


class ChromaKnowledgeIndex:
    """Optional persistent semantic index for course-material chunks."""

    def __init__(
        self,
        *,
        enabled: bool,
        persist_path: str | Path,
        collection_name: str,
        model_path: str | Path,
        top_k: int = 60,
    ) -> None:
        self.enabled = bool(enabled)
        self.persist_path = Path(persist_path)
        self.collection_name = str(collection_name or "course_chunks")
        self.model_path = Path(model_path).expanduser() if str(model_path or "").strip() else None
        self.top_k = max(1, min(int(top_k or 60), 250))

        self._lock = RLock()
        self._attempted = False
        self._available = False
        self._last_error = ""
        self._client: Any = None
        self._collection: Any = None
        self._model: Any = None
        self._known_signatures: dict[str, str] = {}
        self._known_documents: dict[str, str] = {}

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
        self._known_documents = {}
        for chunk_id, metadata in zip(ids, metadatas):
            if not isinstance(metadata, dict):
                continue
            chunk_id = str(chunk_id)
            signature = str(metadata.get("chunk_signature") or "")
            document_id = str(metadata.get("document_id") or "")
            if signature:
                self._known_signatures[chunk_id] = signature
            if document_id:
                self._known_documents[chunk_id] = document_id

    @staticmethod
    def _chunk_id(chunk: Any) -> str:
        return str(_field(chunk, "id", "chunk_id") or "").strip()

    @staticmethod
    def _chunk_signature(chunk: Any) -> str:
        digest = hashlib.sha256()
        for field in (
            "id",
            "document_id",
            "chapter_id",
            "chapter_label",
            "section_id",
            "section_label",
            "page",
            "position",
            "text",
            "knowledge_key",
        ):
            digest.update(str(_field(chunk, field) or "").encode("utf-8", errors="ignore"))
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

    def sync(self, chunks: Iterable[Any], *, prune_missing: bool = False) -> bool:
        """Upsert changed chunks; optionally prune chunks absent from SQLite."""
        if not self._ensure_backend():
            return False

        current: dict[str, Any] = {}
        current_signatures: dict[str, str] = {}
        current_documents: dict[str, str] = {}
        for chunk in chunks:
            chunk_id = self._chunk_id(chunk)
            if not chunk_id:
                continue
            current[chunk_id] = chunk
            current_signatures[chunk_id] = self._chunk_signature(chunk)
            current_documents[chunk_id] = str(_field(chunk, "document_id") or "")

        with self._lock:
            changed = [
                (chunk_id, current[chunk_id], current_signatures[chunk_id])
                for chunk_id in current
                if self._known_signatures.get(chunk_id) != current_signatures[chunk_id]
            ]
            stale_ids = sorted(set(self._known_signatures) - set(current)) if prune_missing else []

            try:
                if changed:
                    ids = [chunk_id for chunk_id, _chunk, _signature in changed]
                    chunks_to_index = [chunk for _chunk_id, chunk, _signature in changed]
                    signatures = [signature for _chunk_id, _chunk, signature in changed]
                    texts = [chunk_embedding_text(chunk) for chunk in chunks_to_index]
                    embeddings = self._encode(texts)
                    metadatas = [
                        {
                            "chunk_signature": signature,
                            "document_id": str(_field(chunk, "document_id") or ""),
                            "chapter_id": str(_field(chunk, "chapter_id") or ""),
                            "section_id": str(_field(chunk, "section_id") or ""),
                            "source_file": str(_field(chunk, "source_file") or ""),
                            "page": int(_field(chunk, "page") or 0),
                        }
                        for chunk, signature in zip(chunks_to_index, signatures)
                    ]
                    self._collection.upsert(
                        ids=ids,
                        documents=texts,
                        embeddings=embeddings,
                        metadatas=metadatas,
                    )
                if stale_ids:
                    self._collection.delete(ids=stale_ids)
                if prune_missing:
                    self._known_signatures = current_signatures
                    self._known_documents = current_documents
                else:
                    self._known_signatures.update(current_signatures)
                    self._known_documents.update(current_documents)
                return True
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                return False

    def delete_document(self, document_id: str) -> bool:
        if not self._ensure_backend():
            return False
        document_id = str(document_id or "").strip()
        if not document_id:
            return True
        ids = sorted(
            chunk_id for chunk_id, current_document_id in self._known_documents.items()
            if current_document_id == document_id
        )
        if not ids:
            return True
        with self._lock:
            try:
                self._collection.delete(ids=ids)
                for chunk_id in ids:
                    self._known_signatures.pop(chunk_id, None)
                    self._known_documents.pop(chunk_id, None)
                return True
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                return False

    def search(
        self,
        chunks: Iterable[Any],
        query: str,
        *,
        top_k: int | None = None,
        chapter_id: str = "",
    ) -> dict[str, float] | None:
        """Return Chroma cosine scores keyed by SQLite chunk id."""
        query = str(query or "").strip()
        current_chunks = list(chunks)
        if not query or not self.sync(current_chunks, prune_missing=False):
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
                kwargs: dict[str, Any] = {
                    "query_embeddings": query_embedding,
                    "n_results": result_limit,
                    "include": ["distances"],
                }
                if chapter_id:
                    kwargs["where"] = {"chapter_id": str(chapter_id)}
                result = self._collection.query(**kwargs)
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                return None

        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        scores: dict[str, float] = {}
        for chunk_id, distance in zip(ids, distances):
            try:
                score = 1.0 - float(distance)
            except (TypeError, ValueError):
                continue
            scores[str(chunk_id)] = max(0.0, min(1.0, score))
        return scores

    def backend_name(self, fallback: str = "sqlite-lexical") -> str:
        return "chroma+rrf" if self._available else fallback

    def status(self, *, total_chunks: int | None = None) -> dict[str, Any]:
        total = max(0, int(total_chunks or 0))
        indexed = len(self._known_signatures)
        return {
            "enabled": self.enabled,
            "available": self._available,
            "collection": self.collection_name,
            "indexed_chunks": indexed,
            "unindexed_chunks": max(0, total - indexed) if total else 0,
            "error": self._last_error,
        }

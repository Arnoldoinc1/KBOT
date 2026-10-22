from __future__ import annotations

import datetime as dt
from pathlib import Path

from knowledge_service.chroma_index import ChromaKnowledgeIndex
from knowledge_service.repository import KnowledgeRepository


class _FakeKnowledgeIndex:
    def __init__(self, scores: dict[str, float] | None = None):
        self.scores = scores or {}
        self.synced = []
        self.deleted = []
        self._available = True

    def sync(self, chunks, *, prune_missing=False):
        self.synced.append(([dict(chunk) for chunk in chunks], prune_missing))
        return True

    def delete_document(self, document_id):
        self.deleted.append(str(document_id))
        return True

    def search(self, chunks, query, *, top_k=None, chapter_id=""):
        return dict(self.scores)

    def backend_name(self, fallback="sqlite-lexical"):
        return "chroma+rrf"

    def status(self, *, total_chunks=None):
        indexed = len(self.synced[-1][0]) if self.synced else 0
        return {
            "enabled": True,
            "available": True,
            "indexed_chunks": indexed,
            "unindexed_chunks": max(0, int(total_chunks or 0) - indexed),
            "error": "",
        }


def _insert_chunks(repo: KnowledgeRepository, rows: list[tuple[str, str]]) -> str:
    doc_id = "doc"
    chapter_id = "doc:chapter"
    now = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    with repo._connect() as connection:
        connection.execute(
            "INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)",
            (doc_id, "notes.txt", "notes", "sha", "notes.txt", "tester", now, 1, len(rows), 1),
        )
        connection.execute(
            "INSERT INTO pages(document_id,page,chapter_label,section_label,text) VALUES(?,?,?,?,?)",
            (doc_id, 1, "Chapter", "Section", "\n".join(text for _chunk_id, text in rows)),
        )
        for position, (chunk_id, text) in enumerate(rows):
            connection.execute(
                "INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    chunk_id,
                    doc_id,
                    chapter_id,
                    "Chapter",
                    "doc:chapter:section",
                    "Section",
                    1,
                    position,
                    text,
                    f"K-{position}",
                ),
            )
    return chapter_id


def test_repository_search_rank_fuses_semantic_only_chunk(tmp_path: Path):
    index = _FakeKnowledgeIndex({"semantic": 1.0})
    repo = KnowledgeRepository(tmp_path / "knowledge", semantic_index=index)
    chapter_id = _insert_chunks(repo, [
        ("lexical", "A marine navigation history paragraph."),
        ("semantic", "A paragraph with no literal words from the query."),
    ])

    result = repo.search("course wording with no literal match", 5, chapter_id)

    assert result["results"][0]["chunk_id"] == "semantic"
    assert result["results"][0]["retrieval_backend"] == "chroma+rrf"
    assert result["results"][0]["retrieval_fusion"] == "weighted-rrf"


def test_repository_search_keeps_strong_keyword_hit_before_semantic_only_chunk(tmp_path: Path):
    index = _FakeKnowledgeIndex({"semantic": 1.0})
    repo = KnowledgeRepository(tmp_path / "knowledge", semantic_index=index)
    chapter_id = _insert_chunks(repo, [
        ("keyword", "GPS satellite navigation requires a receiver and timing signals."),
        ("semantic", "A semantically tempting paragraph with no shared keyword."),
    ])

    result = repo.search("GPS", 5, chapter_id)

    assert result["results"][0]["chunk_id"] == "keyword"
    assert result["results"][0]["retrieval_fusion"] == "weighted-rrf"


def test_repository_upload_and_delete_sync_semantic_index(tmp_path: Path):
    index = _FakeKnowledgeIndex()
    repo = KnowledgeRepository(tmp_path / "knowledge", semantic_index=index)

    document = repo.upload(
        b"GPS satellite navigation requires a receiver and timing signals. "
        b"It provides location information for many applications.",
        "notes.txt",
        "tester",
    )

    assert index.synced
    assert index.synced[-1][1] is False
    assert index.synced[-1][0][0]["document_id"] == document["id"]

    assert repo.delete(document["id"]) is True
    assert index.deleted == [document["id"]]


class _FakeModel:
    def encode(self, texts, **_kwargs):
        return [[float(len(text)), 1.0] for text in texts]


class _FakeCollection:
    def __init__(self):
        self.items = {}
        self.upsert_calls = []
        self.delete_calls = []
        self.query_kwargs = []

    def get(self, **_kwargs):
        return {
            "ids": list(self.items),
            "metadatas": [self.items[item]["metadata"] for item in self.items],
        }

    def upsert(self, *, ids, documents, embeddings, metadatas):
        self.upsert_calls.append(list(ids))
        for chunk_id, document, embedding, metadata in zip(ids, documents, embeddings, metadatas):
            self.items[chunk_id] = {
                "document": document,
                "embedding": embedding,
                "metadata": metadata,
            }

    def delete(self, *, ids):
        self.delete_calls.append(list(ids))
        for chunk_id in ids:
            self.items.pop(chunk_id, None)

    def query(self, **kwargs):
        self.query_kwargs.append(kwargs)
        ids = list(self.items)[: kwargs["n_results"]]
        return {"ids": [ids], "distances": [[0.1 for _ in ids]]}


def _ready_index(tmp_path: Path) -> ChromaKnowledgeIndex:
    index = ChromaKnowledgeIndex(
        enabled=True,
        persist_path=tmp_path / "chroma",
        collection_name="course_chunks",
        model_path=tmp_path / "model",
    )
    index._attempted = True
    index._available = True
    index._model = _FakeModel()
    index._collection = _FakeCollection()
    return index


def test_chroma_knowledge_index_upserts_searches_and_deletes_by_document(tmp_path: Path):
    index = _ready_index(tmp_path)
    chunks = [
        {"id": "1", "document_id": "doc", "chapter_id": "chapter", "section_id": "section", "chapter_label": "Chapter", "section_label": "Section", "page": 1, "position": 0, "text": "GPS navigation", "knowledge_key": "K-1"},
        {"id": "2", "document_id": "doc", "chapter_id": "chapter", "section_id": "section", "chapter_label": "Chapter", "section_label": "Section", "page": 2, "position": 1, "text": "Satellite timing", "knowledge_key": "K-2"},
    ]

    assert index.sync(chunks) is True
    assert index._collection.upsert_calls == [["1", "2"]]
    assert index.search(chunks, "satellite", chapter_id="chapter") == {"1": 0.9, "2": 0.9}
    assert index._collection.query_kwargs[-1]["where"] == {"chapter_id": "chapter"}

    assert index.delete_document("doc") is True
    assert index._collection.delete_calls == [["1", "2"]]

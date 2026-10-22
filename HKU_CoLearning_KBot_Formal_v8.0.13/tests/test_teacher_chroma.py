from __future__ import annotations

from types import SimpleNamespace

from teacher_app.chroma_index import ChromaRecordIndex
from teacher_app.embedding_utils import BGE_QUERY_PREFIX, semantic_query_text
from teacher_app.record_search import hybrid_search_records


def _record(
    record_id: str,
    question: str,
    *,
    topic: str = "GPS",
    chapter: str = "Navigation",
    student_name: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=record_id,
        student_name=student_name or f"Student {record_id}",
        topic=topic,
        chapter=chapter,
        question_type="short_answer",
        question=question,
        answer="",
        correct_answer="",
        ai_feedback="",
        teacher_feedback="",
        explanation="",
        update_time="2026-08-01",
        created_at="2026-08-01",
    )


def test_external_chroma_results_are_rank_fused_into_hybrid_search():
    records = [
        _record("1", "Explain the history of marine navigation.", topic="", chapter=""),
        _record("2", "Explain how satellite signals support positioning.", topic="", chapter=""),
    ]
    ranked = hybrid_search_records(
        records,
        "course wording with no literal match",
        limit=2,
        dense_weight=0.35,
        semantic_scores={"1": 0.10, "2": 1.0},
        semantic_backend="chroma+rrf",
    )

    assert ranked
    assert ranked[0][0].id == "2"
    assert ranked[0][1]["search_backend"] == "chroma+rrf"
    assert ranked[0][1]["search_fusion"] == "weighted-rrf"
    assert "chroma-semantic" in ranked[0][1]["search_match"]


def test_rrf_keeps_strong_keyword_hit_ahead_of_semantic_only_hit():
    records = [
        _record("1", "GPS satellite navigation needs a receiver."),
        _record("2", "A semantically tempting but lexically unrelated record.", topic="", chapter=""),
    ]
    ranked = hybrid_search_records(
        records,
        "GPS",
        limit=2,
        dense_weight=0.35,
        semantic_scores={"2": 1.0},
        semantic_backend="chroma+rrf",
    )

    assert ranked[0][0].id == "1"
    assert ranked[0][1]["search_fusion"] == "weighted-rrf"
    assert "keyword" in ranked[0][1]["search_match"]


def test_bge_query_instruction_is_applied_only_to_bge_models():
    assert semantic_query_text("GPS positioning", "models/bge-base-en-v1.5") == (
        BGE_QUERY_PREFIX + "GPS positioning"
    )
    assert semantic_query_text("GPS positioning", "models/all-MiniLM-L6-v2") == "GPS positioning"


def test_disabled_chroma_index_returns_safe_fallback_signal(tmp_path):
    index = ChromaRecordIndex(
        enabled=False,
        persist_path=tmp_path / "chroma",
        collection_name="records",
        model_path=tmp_path / "missing-model",
    )

    assert index.search([_record("1", "GPS navigation")], "GPS") is None
    assert index.backend_name() == "hybrid-sparse-vector"
    assert index.status()["available"] is False


class _FakeModel:
    def encode(self, texts, **_kwargs):
        return [[float(len(text)), 1.0] for text in texts]


class _FakeCollection:
    def __init__(self):
        self.items = {}
        self.upsert_calls = []
        self.delete_calls = []

    def get(self, **_kwargs):
        return {
            "ids": list(self.items),
            "metadatas": [self.items[item]["metadata"] for item in self.items],
        }

    def upsert(self, *, ids, documents, embeddings, metadatas):
        self.upsert_calls.append(list(ids))
        for record_id, document, embedding, metadata in zip(ids, documents, embeddings, metadatas):
            self.items[record_id] = {
                "document": document,
                "embedding": embedding,
                "metadata": metadata,
            }

    def delete(self, *, ids):
        self.delete_calls.append(list(ids))
        for record_id in ids:
            self.items.pop(record_id, None)

    def query(self, *, query_embeddings, n_results, include):
        ids = list(self.items)[:n_results]
        return {"ids": [ids], "distances": [[0.1 for _ in ids]]}


def _ready_index(tmp_path):
    index = ChromaRecordIndex(
        enabled=True,
        persist_path=tmp_path / "chroma",
        collection_name="records",
        model_path=tmp_path / "model",
    )
    index._attempted = True
    index._available = True
    index._model = _FakeModel()
    index._collection = _FakeCollection()
    return index


def test_chroma_sync_upserts_updates_and_deletes_records(tmp_path):
    index = _ready_index(tmp_path)
    first = _record("1", "GPS navigation")
    second = _record("2", "Satellite positioning")

    assert index.sync([first, second]) is True
    assert index._collection.upsert_calls == [["1", "2"]]
    assert set(index._known_signatures) == {"1", "2"}

    first.question = "Updated GPS navigation"
    assert index.sync([first]) is True
    assert index._collection.upsert_calls[-1] == ["1"]
    assert index._collection.delete_calls == []
    assert index.sync([first], prune_missing=True) is True
    assert index._collection.delete_calls == [["2"]]
    assert set(index._known_signatures) == {"1"}


def test_chroma_search_returns_cosine_scores_by_record_id(tmp_path):
    index = _ready_index(tmp_path)
    record = _record("1", "GPS navigation")

    assert index.search([record], "satellite") == {"1": 0.9}

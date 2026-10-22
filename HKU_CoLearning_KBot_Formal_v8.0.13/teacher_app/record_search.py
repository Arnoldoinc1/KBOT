from __future__ import annotations

"""Hybrid teacher-side search for saved student records.

The original dashboard label promises semantic search, while the v8.0.x route
had regressed to SQL ``ILIKE`` only.  This module restores a hybrid ranker:

* exact/substring keyword matching;
* BM25-style token relevance;
* TF-IDF sparse vector cosine similarity;
* character n-gram similarity for spelling and wording variation;
* acronym/long-form expansion (for example GPS <-> Global Positioning System);
* optional dense SentenceTransformer similarity when a *local* model is
  explicitly configured.
* optional Chroma/dense candidates fused with sparse candidates by weighted
  reciprocal rank fusion.

The dependency-free sparse path is always available.  The optional dense path
never downloads a model at request time; deployment must provide a local model
path and the sentence-transformers package.
"""

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
from threading import RLock
from typing import Any, Iterable

from teacher_app.embedding_utils import load_local_sentence_transformer, semantic_query_text
from knowledge_service.retrieval import tokens


WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'_-]*")
ACRONYM_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9 &/\-]{2,80}?)\s*\(([A-Z][A-Z0-9]{1,9})\)")
REVERSE_ACRONYM_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9})\s*\(([A-Za-z][A-Za-z0-9 &/\-]{2,80}?)\)")

# Course-domain aliases are a safety net for records that contain only the
# abbreviation or only the long form.  Additional aliases are learned from the
# current record corpus at query time.
DEFAULT_ALIASES = {
    "gps": "global positioning system",
    "lbs": "location based service",
    "gsm": "global system for mobile communications",
    "bss": "base station subsystem",
    "nss": "network and switching subsystem",
    "oss": "operations support system",
    "gprs": "general packet radio service",
    "rfid": "radio frequency identification",
    "ins": "inertial navigation system",
    "mcq": "multiple choice question",
}


@dataclass(frozen=True)
class SearchDocument:
    record: Any
    text: str
    normalized: str
    terms: tuple[str, ...]
    features: Counter[str]
    char_features: Counter[str]


@dataclass
class _CorpusCache:
    signature: str = ""
    documents: list[SearchDocument] | None = None
    idf: dict[str, float] | None = None
    char_idf: dict[str, float] | None = None
    avg_length: float = 1.0
    aliases: dict[str, str] | None = None


_CACHE = _CorpusCache()
_CACHE_LOCK = RLock()
_DENSE_LOCK = RLock()
_DENSE_EMBEDDINGS: dict[tuple[str, str], Any] = {}


def _field(record: Any, name: str) -> str:
    return str(getattr(record, name, "") or "").strip()


def record_search_text(record: Any) -> str:
    # Repeating high-value fields provides field weighting without introducing
    # another search dependency or schema migration.
    student = _field(record, "student_name")
    topic = _field(record, "topic")
    chapter = _field(record, "chapter")
    question = _field(record, "question")
    answer = _field(record, "answer")
    options = _field(record, "options_or_pairs")
    correct = _field(record, "correct_answer")
    feedback = " ".join(filter(None, (_field(record, "ai_feedback"), _field(record, "teacher_feedback"))))
    explanation = _field(record, "explanation")
    qtype = _field(record, "question_type")
    source_document = _field(record, "source_document")
    source_excerpt = _field(record, "source_excerpt")
    return "\n".join(
        item for item in (
            student, student,
            topic, topic,
            chapter,
            qtype,
            question, question, question,
            answer, answer,
            options,
            correct, correct,
            feedback,
            explanation,
            source_document,
            source_excerpt,
        ) if item
    )


def _normalize(value: object) -> str:
    return " ".join(WORD_RE.findall(str(value or "").casefold()))


def _word_features(value: object) -> Counter[str]:
    base = tokens(value)
    features: Counter[str] = Counter(base)
    for left, right in zip(base, base[1:]):
        features[f"{left}::{right}"] += 0.8
    return features


def _char_features(value: object) -> Counter[str]:
    compact = re.sub(r"\s+", " ", _normalize(value))
    features: Counter[str] = Counter()
    if not compact:
        return features
    padded = f"  {compact}  "
    for size, weight in ((3, 0.45), (4, 0.75), (5, 1.0)):
        for index in range(max(0, len(padded) - size + 1)):
            features[padded[index:index + size]] += weight
    return features


def _learn_aliases(texts: Iterable[str]) -> dict[str, str]:
    aliases = dict(DEFAULT_ALIASES)
    for text in texts:
        for long_form, acronym in ACRONYM_RE.findall(text):
            long_form = _normalize(long_form).strip()
            acronym = acronym.casefold()
            if 1 <= len(tokens(long_form)) <= 10:
                aliases[acronym] = long_form
        for acronym, long_form in REVERSE_ACRONYM_RE.findall(text):
            long_form = _normalize(long_form).strip()
            acronym = acronym.casefold()
            if 1 <= len(tokens(long_form)) <= 10:
                aliases[acronym] = long_form
    return aliases


def _expand_query(query: str, aliases: dict[str, str]) -> str:
    normalized = _normalize(query)
    query_terms = set(tokens(normalized))
    additions: list[str] = []
    for acronym, long_form in aliases.items():
        long_terms = set(tokens(long_form))
        if acronym in query_terms:
            additions.append(long_form)
        elif long_terms and long_terms <= query_terms:
            additions.append(acronym)
    return " ".join([normalized, *additions]).strip()


def _signature(records: list[Any]) -> str:
    digest = hashlib.sha256()
    for record in records:
        for field in (
            "id", "update_time", "student_name", "topic", "chapter",
            "question_type", "question", "answer", "correct_answer",
            "options_or_pairs", "ai_feedback", "teacher_feedback", "explanation",
            "source_document", "source_excerpt",
        ):
            digest.update(_field(record, field).encode("utf-8", errors="ignore"))
            digest.update(b"\0")
    return digest.hexdigest()[:24]


def _idf(documents: list[SearchDocument], attr: str) -> dict[str, float]:
    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(set(getattr(document, attr)))
    total = max(1, len(documents))
    return {
        term: math.log((total + 1.0) / (frequency + 0.5)) + 1.0
        for term, frequency in document_frequency.items()
    }


def _build_corpus(records: list[Any]) -> tuple[str, list[SearchDocument], dict[str, float], dict[str, float], float, dict[str, str]]:
    signature = _signature(records)
    with _CACHE_LOCK:
        if _CACHE.signature == signature and _CACHE.documents is not None:
            return (
                signature,
                _CACHE.documents,
                _CACHE.idf or {},
                _CACHE.char_idf or {},
                _CACHE.avg_length,
                _CACHE.aliases or {},
            )
        texts = [record_search_text(record) for record in records]
        documents = [
            SearchDocument(
                record=record,
                text=text,
                normalized=_normalize(text),
                terms=tuple(tokens(text)),
                features=_word_features(text),
                char_features=_char_features(text),
            )
            for record, text in zip(records, texts)
        ]
        word_idf = _idf(documents, "features")
        char_idf = _idf(documents, "char_features")
        avg_length = sum(len(document.terms) for document in documents) / max(1, len(documents))
        aliases = _learn_aliases(texts)
        _CACHE.signature = signature
        _CACHE.documents = documents
        _CACHE.idf = word_idf
        _CACHE.char_idf = char_idf
        _CACHE.avg_length = max(1.0, avg_length)
        _CACHE.aliases = aliases
        return signature, documents, word_idf, char_idf, max(1.0, avg_length), aliases


def _weighted_cosine(left: Counter[str], right: Counter[str], idf: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for term, value in left.items():
        weighted = float(value) * idf.get(term, 1.0)
        left_norm += weighted * weighted
        if term in right:
            dot += weighted * float(right[term]) * idf.get(term, 1.0)
    for term, value in right.items():
        weighted = float(value) * idf.get(term, 1.0)
        right_norm += weighted * weighted
    return dot / math.sqrt(left_norm * right_norm) if dot > 0 and left_norm > 0 and right_norm > 0 else 0.0


def _bm25(query_terms: list[str], document: SearchDocument, idf: dict[str, float], avg_length: float) -> float:
    if not query_terms or not document.terms:
        return 0.0
    counts = Counter(document.terms)
    length = len(document.terms)
    k1, b = 1.45, 0.72
    score = 0.0
    max_score = 0.0
    for term in set(query_terms):
        term_idf = idf.get(term, 1.0)
        frequency = counts.get(term, 0)
        denominator = frequency + k1 * (1.0 - b + b * length / max(1.0, avg_length))
        if frequency:
            score += term_idf * (frequency * (k1 + 1.0)) / denominator
        max_score += term_idf * (k1 + 1.0)
    return min(1.0, score / max(1e-9, max_score))


def _keyword_score(query: str, expanded_query: str, document: SearchDocument) -> float:
    normalized = _normalize(query)
    expanded_terms = set(tokens(expanded_query))
    doc_terms = set(document.terms)
    score = 0.0
    if normalized and normalized in document.normalized:
        score = 1.0
    elif expanded_terms and expanded_terms <= doc_terms:
        score = 0.88
    elif expanded_terms:
        score = 0.65 * len(expanded_terms & doc_terms) / len(expanded_terms)

    student = _normalize(_field(document.record, "student_name"))
    if normalized and normalized == student:
        score = max(score, 1.0)
    elif normalized and normalized in student:
        score = max(score, 0.92)
    return min(1.0, score)


def _dense_scores(model_path: str, signature: str, query: str, documents: list[SearchDocument]) -> list[float] | None:
    model = load_local_sentence_transformer(model_path)
    if model is None or not documents:
        return None
    model_key = str(Path(model_path).expanduser().resolve())
    cache_key = (model_key, signature)
    with _DENSE_LOCK:
        embeddings = _DENSE_EMBEDDINGS.get(cache_key)
    try:
        if embeddings is None:
            embeddings = model.encode(
                [document.text for document in documents],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            with _DENSE_LOCK:
                _DENSE_EMBEDDINGS.clear()
                _DENSE_EMBEDDINGS[cache_key] = embeddings
        query_embedding = model.encode(
            [semantic_query_text(query, model_path)],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]
        return [max(0.0, min(1.0, float(vector @ query_embedding))) for vector in embeddings]
    except Exception:
        return None


def hybrid_search_records(
    records: list[Any],
    query: str,
    *,
    limit: int = 100,
    dense_model_path: str = "",
    dense_weight: float = 0.35,
    semantic_scores: dict[str, float] | None = None,
    semantic_backend: str = "",
) -> list[tuple[Any, dict[str, Any]]]:
    """Return ranked records plus non-persistent search metadata."""
    query = str(query or "").strip()
    if not query or not records:
        return []
    limit = max(1, min(int(limit or 100), 250))
    signature, documents, idf, char_idf, avg_length, aliases = _build_corpus(records)
    expanded = _expand_query(query, aliases)
    query_features = _word_features(expanded)
    query_char_features = _char_features(query)
    query_terms = tokens(expanded)
    external_dense_scores = semantic_scores if semantic_scores is not None else None
    dense = None if external_dense_scores is not None else _dense_scores(
        dense_model_path,
        signature,
        expanded,
        documents,
    )
    raw_semantic_weight = max(0.0, min(float(dense_weight), 0.65))
    rrf_k = 60.0

    document_data: list[dict[str, Any]] = []
    document_lookup: dict[str, dict[str, Any]] = {}
    for index, document in enumerate(documents):
        record_id = str(getattr(document.record, "id", "") or "")
        sparse = _weighted_cosine(query_features, document.features, idf)
        char = _weighted_cosine(query_char_features, document.char_features, char_idf)
        bm25 = _bm25(query_terms, document, idf, avg_length)
        keyword = _keyword_score(query, expanded, document)
        base = 0.38 * sparse + 0.24 * bm25 + 0.16 * char + 0.22 * keyword
        dense_score = 0.0
        if external_dense_scores is not None:
            dense_score = max(0.0, min(1.0, float(external_dense_scores.get(record_id, 0.0))))
        elif dense is not None:
            dense_score = max(0.0, min(1.0, float(dense[index])))
        name_match = _normalize(query) in _normalize(_field(document.record, "student_name"))
        item = {
            "record_id": record_id,
            "record": document.record,
            "sparse": sparse,
            "char": char,
            "bm25": bm25,
            "keyword": keyword,
            "base": base,
            "semantic": dense_score,
            "name_match": name_match,
        }
        document_data.append(item)
        document_lookup[record_id] = item

    candidate_limit = min(250, max(limit, len(external_dense_scores or {}), 50))
    sparse_candidates = [
        item for item in document_data
        if item["base"] >= 0.075 or item["name_match"]
    ]
    sparse_candidates.sort(
        key=lambda item: (
            item["base"],
            item["semantic"],
            str(getattr(item["record"], "created_at", "") or ""),
            item["record_id"],
        ),
        reverse=True,
    )
    sparse_rank = {
        item["record_id"]: rank
        for rank, item in enumerate(sparse_candidates[:candidate_limit], start=1)
    }

    if external_dense_scores is not None:
        semantic_ranked = sorted(
            (
                (record_id, max(0.0, min(1.0, float(score))))
                for record_id, score in external_dense_scores.items()
                if record_id in document_lookup
            ),
            key=lambda item: (
                item[1],
                document_lookup[item[0]]["base"],
                str(getattr(document_lookup[item[0]]["record"], "created_at", "") or ""),
                item[0],
            ),
            reverse=True,
        )
        semantic_rank = {
            record_id: rank
            for rank, (record_id, score) in enumerate(semantic_ranked[:candidate_limit], start=1)
            if score > 0
        }
        semantic_backend_name = semantic_backend or "chroma+rrf"
    elif dense is not None:
        dense_ranked = sorted(
            document_data,
            key=lambda item: (
                item["semantic"],
                item["base"],
                str(getattr(item["record"], "created_at", "") or ""),
                item["record_id"],
            ),
            reverse=True,
        )
        semantic_rank = {
            item["record_id"]: rank
            for rank, item in enumerate(dense_ranked[:candidate_limit], start=1)
            if item["semantic"] > 0
        }
        semantic_backend_name = semantic_backend or "dense+rrf"
    else:
        semantic_rank = {}
        semantic_backend_name = semantic_backend or "hybrid-sparse-vector"

    candidates = [
        item for item in document_data
        if item["record_id"] in sparse_rank or item["record_id"] in semantic_rank
    ]
    if not candidates:
        return []

    ranked: list[tuple[float, Any, dict[str, Any]]] = []
    use_rrf = bool(semantic_rank)
    semantic_weight = raw_semantic_weight if use_rrf else 0.0
    sparse_weight = 1.0 - semantic_weight if use_rrf else 1.0
    rrf_scale = rrf_k + 1.0
    for item in candidates:
        record_id = item["record_id"]
        sparse_rank_value = sparse_rank.get(record_id)
        semantic_rank_value = semantic_rank.get(record_id)
        if use_rrf:
            fused = 0.0
            if sparse_rank_value is not None:
                fused += sparse_weight / (rrf_k + float(sparse_rank_value))
            if semantic_rank_value is not None:
                fused += semantic_weight / (rrf_k + float(semantic_rank_value))
            score = min(1.0, fused * rrf_scale)
            fusion = "weighted-rrf"
        else:
            score = item["base"]
            fusion = "sparse-score"
        if score < 0.075 and not item["name_match"]:
            continue
        match_parts: list[str] = []
        if item["keyword"] >= 0.8:
            match_parts.append("keyword")
        if item["sparse"] >= 0.12 or item["bm25"] >= 0.16:
            match_parts.append("semantic-vector")
        if item["char"] >= 0.32:
            match_parts.append("wording")
        if semantic_rank_value is not None:
            match_parts.append("chroma-semantic" if external_dense_scores is not None else "dense-semantic")
        if use_rrf and sparse_rank_value is not None and semantic_rank_value is not None:
            match_parts.append("rrf")
        backend = semantic_backend_name
        ranked.append((score, item["record"], {
            "search_score": round(score, 6),
            "search_match": "+".join(match_parts) or "semantic-vector",
            "search_backend": backend,
            "search_fusion": fusion,
        }))

    ranked.sort(
        key=lambda item: (
            item[0],
            str(getattr(item[1], "created_at", "") or ""),
            str(getattr(item[1], "id", "") or ""),
        ),
        reverse=True,
    )
    return [(record, metadata) for _score, record, metadata in ranked[:limit]]


def search_backend_name(dense_model_path: str = "") -> str:
    return "dense+rrf" if load_local_sentence_transformer(dense_model_path) is not None else "hybrid-sparse-vector"

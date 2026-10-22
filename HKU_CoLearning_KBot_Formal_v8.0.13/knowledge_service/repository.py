from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any

from .document_parser import _valid_term, explicit_term_pairs, fact_sentences, infer_document_label, parse_document, split_chunks
from .retrieval import diverse_rank, fingerprint, lexical_score, tokens


SCHEMA_VERSION = 3


_OUTLINE_MARKERS = {"contents", "content", "agenda", "outline", "topics"}
_OUTLINE_GENERIC = {
    "overview", "introduction", "summary", "chapter", "unit", "module", "lecture",
    "part", "section", "technology", "technologies",
    # Query-intent words are not the subject itself.  Treating them as mandatory
    # keywords made natural topics such as "definition of lamp" fail unless the
    # word "definition" happened to occur in the same chunk as "lamp".
    "definition", "meaning", "working",
}


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def _topic_words(value: object) -> list[str]:
    return [
        token for token in tokens(value)
        if token not in _OUTLINE_GENERIC and not token.isdigit()
    ]


def _compact(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _acronym(words: list[str]) -> str:
    return "".join(word[0] for word in words if word)


def _topic_similarity(query: object, label: object) -> float:
    query_words = _topic_words(query)
    label_words = _topic_words(label)
    if not query_words or not label_words:
        return 0.0
    query_set, label_set = set(query_words), set(label_words)
    query_compact = _compact(query)
    label_acronym = _acronym(label_words)
    if query_compact and query_compact == label_acronym:
        return 1.0
    overlap = len(query_set & label_set)
    coverage = overlap / len(query_set)
    reverse = overlap / len(label_set)
    score = 0.78 * coverage + 0.22 * reverse
    normalized_query = " ".join(query_words)
    normalized_label = " ".join(label_words)
    if normalized_query and (normalized_query in normalized_label or normalized_label in normalized_query):
        score = max(score, 0.92 if overlap else 0.0)
    return min(1.0, score)


def _clean_outline_entry(value: object) -> str:
    line = str(value or "").strip()
    line = re.sub(r"^[^A-Za-z0-9]+", "", line)
    line = re.sub(r"\s+", " ", line).strip(" .:;-–")
    return line


def _outline_entries(page_rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    for page in page_rows:
        lines = [line.strip() for line in str(page.get("text") or "").splitlines() if line.strip()]
        marker_index = next(
            (index for index, line in enumerate(lines) if _compact(line) in _OUTLINE_MARKERS),
            None,
        )
        if marker_index is None:
            continue
        for raw in lines[marker_index + 1 : marker_index + 16]:
            item = _clean_outline_entry(raw)
            words = _topic_words(item)
            if not item or not (1 <= len(words) <= 9) or len(item) > 100:
                continue
            if item.casefold().startswith(("example ", "class discussion")):
                continue
            entries.append((item, int(page.get("page") or 0)))
        if entries:
            break
    unique: list[tuple[str, int]] = []
    seen: set[str] = set()
    for label, page in entries:
        key = " ".join(_topic_words(label))
        if key and key not in seen:
            seen.add(key)
            unique.append((label, page))
    return unique


def _outline_ranges(page_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = _outline_entries(page_rows)
    if not entries:
        return []
    anchors: list[tuple[int, str, float]] = []
    for label, outline_page in entries:
        best: tuple[float, int] | None = None
        for page in page_rows:
            page_number = int(page.get("page") or 0)
            if page_number <= outline_page:
                continue
            section = str(page.get("section_label") or page.get("section") or "")
            body = str(page.get("text") or "")
            combined = f"{section} {body}"
            score = max(_topic_similarity(label, section), _topic_similarity(label, combined))
            if score <= 0:
                continue
            has_bullets = any(marker in body for marker in ("•", "–", "\uf06e"))
            word_count = len(tokens(body))
            if not has_bullets:
                score += 0.18
            if word_count <= 20:
                score += 0.14
            if " ".join(_topic_words(label)) in " ".join(_topic_words(body)):
                score += 0.10
            # Prefer the first strong title page instead of a later content page.
            score -= min(0.12, max(0, page_number - outline_page) * 0.0015)
            candidate = (score, -page_number)
            if best is None or candidate > (best[0], -best[1]):
                best = (score, page_number)
        if best and best[0] >= 0.72:
            anchors.append((best[1], label, best[0]))
    deduped: list[tuple[int, str]] = []
    seen_pages: set[int] = set()
    for page, label, _score in sorted(anchors):
        if page not in seen_pages:
            seen_pages.add(page)
            deduped.append((page, label))
    ranges: list[dict[str, Any]] = []
    final_page = max((int(page.get("page") or 0) for page in page_rows), default=0)
    for index, (start, label) in enumerate(deduped):
        end = deduped[index + 1][0] - 1 if index + 1 < len(deduped) else final_page
        ranges.append({"label": label, "start": start, "end": end})
    return ranges


def _topic_scope(page_rows: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    best: tuple[float, dict[str, Any]] | None = None
    for item in _outline_ranges(page_rows):
        score = _topic_similarity(query, item["label"])
        if score >= 0.78 and (best is None or score > best[0]):
            best = (score, item)
    if best is not None:
        return {**best[1], "match_score": round(best[0], 6)}

    # Fallback for a deck without an outline: an exact, low-text title page can
    # still anchor a conservative 30-page topic window.
    query_words = set(_topic_words(query))
    if not query_words or len(query_words) > 4:
        return None
    candidates: list[tuple[float, int]] = []
    final_page = max((int(page.get("page") or 0) for page in page_rows), default=0)
    for page in page_rows:
        body = str(page.get("text") or "")
        page_words = set(_topic_words(body))
        if not query_words <= page_words or any(marker in body for marker in ("•", "–", "\uf06e")):
            continue
        if len(tokens(body)) > 18:
            continue
        score = lexical_score(query, body)
        candidates.append((score, int(page.get("page") or 0)))
    if not candidates:
        return None
    score, start = max(candidates, key=lambda item: (item[0], -item[1]))
    if score < 0.72:
        return None
    return {"label": str(query), "start": start, "end": min(final_page, start + 29), "match_score": round(score, 6)}


class KnowledgeRepository:
    def __init__(self, data_dir: str | Path, *, semantic_index: Any = None, dense_weight: float = 0.35):
        self.data_dir = Path(data_dir)
        self.upload_dir = self.data_dir / "uploads"
        self.database_path = self.data_dir / "knowledge.db"
        self.semantic_index = semantic_index
        self.dense_weight = max(0.0, min(float(dense_weight), 0.65))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30, factory=_ClosingConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents (
                  id TEXT PRIMARY KEY, filename TEXT NOT NULL, label TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE,
                  stored_path TEXT NOT NULL, uploaded_by TEXT NOT NULL DEFAULT '', uploaded_at TEXT NOT NULL,
                  page_count INTEGER NOT NULL, chunk_count INTEGER NOT NULL, section_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pages (
                  document_id TEXT NOT NULL, page INTEGER NOT NULL, chapter_label TEXT NOT NULL,
                  section_label TEXT NOT NULL, text TEXT NOT NULL,
                  PRIMARY KEY(document_id,page),
                  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS chunks (
                  id TEXT PRIMARY KEY, document_id TEXT NOT NULL, chapter_id TEXT NOT NULL, chapter_label TEXT NOT NULL,
                  section_id TEXT NOT NULL, section_label TEXT NOT NULL, page INTEGER NOT NULL, position INTEGER NOT NULL,
                  text TEXT NOT NULL, knowledge_key TEXT NOT NULL UNIQUE,
                  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS facts (
                  id TEXT PRIMARY KEY, chunk_id TEXT NOT NULL, fact_key TEXT NOT NULL, fact_text TEXT NOT NULL,
                  normalized TEXT NOT NULL, page INTEGER NOT NULL,
                  FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS term_pairs (
                  id TEXT PRIMARY KEY, document_id TEXT NOT NULL, chapter_id TEXT NOT NULL, category TEXT NOT NULL,
                  term TEXT NOT NULL, definition TEXT NOT NULL, page INTEGER NOT NULL,
                  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_chapter ON chunks(chapter_id);
                CREATE INDEX IF NOT EXISTS idx_chunks_page ON chunks(document_id,page);
                CREATE INDEX IF NOT EXISTS idx_pages_document ON pages(document_id,page);
                CREATE INDEX IF NOT EXISTS idx_facts_chunk ON facts(chunk_id);
                CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(fact_key);
                CREATE INDEX IF NOT EXISTS idx_terms_chapter ON term_pairs(chapter_id,category);
                """
            )
            connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        return slug[:72] or "section"

    @staticmethod
    def _bounded_limit(value: object, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(str(value))
        except (TypeError, ValueError):
            parsed = default
        return max(minimum, min(parsed, maximum))

    def retrieval_backend_name(self) -> str:
        if self.semantic_index is None:
            return "sqlite-lexical"
        return self.semantic_index.backend_name("sqlite-lexical")

    def _sync_semantic_index(self, chunks: list[dict[str, Any]], *, prune_missing: bool = False) -> None:
        if self.semantic_index is None or not chunks:
            return
        try:
            self.semantic_index.sync(chunks, prune_missing=prune_missing)
        except Exception:
            pass

    def _semantic_status(self, total_chunks: int) -> dict[str, Any]:
        if self.semantic_index is None:
            return {"enabled": False, "available": False, "indexed_chunks": 0, "unindexed_chunks": total_chunks, "error": "disabled"}
        return self.semantic_index.status(total_chunks=total_chunks)

    def upload(self, data: bytes, filename: str, uploaded_by: str = "") -> dict[str, Any]:
        if not data:
            raise ValueError("The uploaded file is empty.")
        sha256 = hashlib.sha256(data).hexdigest()
        with self._connect() as connection:
            existing = connection.execute("SELECT id FROM documents WHERE sha256=?", (sha256,)).fetchone()
        if existing:
            result = self.get_document(existing["id"])
            result["duplicate"] = True
            return result
        pages = parse_document(data, filename)
        if not pages:
            raise ValueError("No readable text was found in the uploaded file.")
        chunks = split_chunks(pages)
        if not chunks:
            raise ValueError("No usable knowledge chunks could be produced.")
        terms = explicit_term_pairs(pages)
        label = infer_document_label(filename)
        doc_id = hashlib.sha256(f"{filename}:{sha256}".encode()).hexdigest()[:24]
        stored_path = self.upload_dir / f"{doc_id}{Path(filename).suffix.casefold()}"
        stored_path.write_bytes(data)
        now = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        chapters = sorted({item["chapter"] for item in chunks})
        sections = sorted({item.section for item in pages})
        indexed_chunks: list[dict[str, Any]] = []
        try:
            with self._lock, self._connect() as connection:
                connection.execute(
                    "INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (doc_id, filename, label, sha256, stored_path.name, uploaded_by, now, len(pages), len(chunks), len(sections)),
                )
                connection.executemany(
                    "INSERT INTO pages(document_id,page,chapter_label,section_label,text) VALUES(?,?,?,?,?)",
                    [(doc_id, item.page, item.chapter, item.section, item.text) for item in pages],
                )
                for position, item in enumerate(chunks):
                    chapter_id = f"{doc_id}:{self._slug(item['chapter'])}"
                    section_id = f"{chapter_id}:{self._slug(item['section'])}"
                    chunk_id = f"{doc_id}:{position:05d}"
                    key_material = f"{doc_id}:{item['page']}:{item['text']}"
                    knowledge_key = f"K-{fingerprint(key_material)}"
                    connection.execute(
                        "INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (chunk_id, doc_id, chapter_id, item["chapter"], section_id, item["section"], item["page"], position, item["text"], knowledge_key),
                    )
                    indexed_chunks.append({
                        "id": chunk_id,
                        "document_id": doc_id,
                        "source_file": filename,
                        "document_label": label,
                        "chapter_id": chapter_id,
                        "chapter_label": item["chapter"],
                        "section_id": section_id,
                        "section_label": item["section"],
                        "page": item["page"],
                        "position": position,
                        "text": item["text"],
                        "knowledge_key": knowledge_key,
                    })
                    for fact_index, fact in enumerate(fact_sentences(item["text"])):
                        fact_key = f"F-{fingerprint(fact)}"
                        fact_id = f"{chunk_id}:f{fact_index:03d}"
                        connection.execute(
                            "INSERT INTO facts VALUES(?,?,?,?,?,?)",
                            (fact_id, chunk_id, fact_key, fact, " ".join(fact.casefold().split()), item["page"]),
                        )
                chapter_by_page = {page.page: f"{doc_id}:{self._slug(page.chapter)}" for page in pages}
                for index, pair in enumerate(terms):
                    term_id = f"{doc_id}:t{index:04d}"
                    connection.execute(
                        "INSERT INTO term_pairs VALUES(?,?,?,?,?,?,?)",
                        (term_id, doc_id, chapter_by_page.get(pair["page"], f"{doc_id}:{self._slug(chapters[0])}"), pair["category"], pair["term"], pair["definition"], pair["page"]),
                    )
        except Exception:
            stored_path.unlink(missing_ok=True)
            raise
        self._sync_semantic_index(indexed_chunks)
        return self.get_document(doc_id)

    def get_document(self, document_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise KeyError(document_id)
        return dict(row)

    def documents(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM documents ORDER BY uploaded_at DESC,filename").fetchall()
        return [dict(row) for row in rows]

    def pages(self, document_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT page,chapter_label chapter,section_label section,text FROM pages WHERE document_id=? ORDER BY page",
                (document_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def chapters(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT c.chapter_id id,c.chapter_label label,c.document_id,d.filename source_file,
                          MIN(c.page) first_page,MAX(c.page) last_page,COUNT(*) chunk_count,
                          COUNT(DISTINCT c.section_id) section_count
                   FROM chunks c JOIN documents d ON d.id=c.document_id
                   GROUP BY c.chapter_id,c.chapter_label,c.document_id,d.filename
                   ORDER BY d.uploaded_at DESC,first_page"""
            ).fetchall()
        return [dict(row) for row in rows]

    def chunks_for_index(self, limit: int = 0) -> list[dict[str, Any]]:
        sql = "SELECT c.*,d.filename source_file,d.label document_label FROM chunks c JOIN documents d ON d.id=c.document_id ORDER BY c.position"
        params: list[Any] = []
        if limit:
            sql += " LIMIT ?"
            params.append(self._bounded_limit(limit, 0, 1, 50000))
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def rebuild_semantic_index(self, limit: int = 0) -> bool:
        if self.semantic_index is None:
            return False
        chunks = self.chunks_for_index(limit)
        return bool(self.semantic_index.sync(chunks, prune_missing=True))

    def delete(self, document_id: str) -> bool:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT stored_path FROM documents WHERE id=?", (document_id,)).fetchone()
            if not row:
                return False
            connection.execute("DELETE FROM documents WHERE id=?", (document_id,))
        (self.upload_dir / row["stored_path"]).unlink(missing_ok=True)
        if self.semantic_index is not None:
            try:
                self.semantic_index.delete_document(document_id)
            except Exception:
                pass
        return True

    def search(
        self,
        query: str,
        limit: int = 8,
        chapter_id: str = "",
        used: dict | None = None,
        topic_mode: bool = False,
        neighbor_pages: int = 0,
    ) -> dict[str, Any]:
        limit = self._bounded_limit(limit, 8, 1, 20)
        sql = "SELECT c.*,d.filename source_file,d.label document_label FROM chunks c JOIN documents d ON d.id=c.document_id"
        params: list[Any] = []
        if chapter_id:
            sql += " WHERE c.chapter_id=?"
            params.append(chapter_id)
        with self._connect() as connection:
            rows = connection.execute(sql + " ORDER BY c.position", params).fetchall()
            facts_by_chunk: dict[str, list[dict]] = {}
            for row in connection.execute(
                "SELECT f.* FROM facts f JOIN chunks c ON c.id=f.chunk_id" + (" WHERE c.chapter_id=?" if chapter_id else ""),
                ([chapter_id] if chapter_id else []),
            ).fetchall():
                facts_by_chunk.setdefault(row["chunk_id"], []).append(dict(row))
            page_sql = "SELECT p.page,p.section_label,p.text FROM pages p"
            page_params: list[Any] = []
            if chapter_id:
                page_sql += " JOIN chunks c ON c.document_id=p.document_id WHERE c.chapter_id=? GROUP BY p.document_id,p.page"
                page_params.append(chapter_id)
            page_rows = [dict(row) for row in connection.execute(page_sql + " ORDER BY p.page", page_params).fetchall()]

        query = str(query or "").strip()
        scope = _topic_scope(page_rows, query) if topic_mode and query else None
        query_words = set(_topic_words(query))
        semantic_scores: dict[str, float] = {}
        semantic_backend = self.retrieval_backend_name()
        if self.semantic_index is not None and query:
            search_top_k = min(250, max(limit * 8, 60))
            raw_scores = self.semantic_index.search(
                rows,
                query,
                top_k=search_top_k,
                chapter_id=chapter_id,
            )
            if raw_scores:
                semantic_scores = raw_scores
            semantic_backend = self.retrieval_backend_name()

        ranked: list[dict] = []
        for row in rows:
            item = dict(row)
            page_number = int(item.get("page") or 0)
            if scope and not (int(scope["start"]) <= page_number <= int(scope["end"])):
                continue

            body = f"{item['chapter_label']} {item['section_label']} {item['text']}"
            direct_relevance = lexical_score(query, body) if query else 0.5
            semantic_relevance = max(0.0, min(1.0, float(semantic_scores.get(item["id"], 0.0))))
            if scope:
                span = max(1, int(scope["end"]) - int(scope["start"]))
                proximity = max(0.0, 1.0 - (page_number - int(scope["start"])) / span)
                section_relevance = lexical_score(scope.get("label", query), f"{item['section_label']} {item['text']}")
                relevance = max(direct_relevance, 0.24 + 0.07 * proximity + 0.10 * section_relevance)
            else:
                relevance = direct_relevance
                if topic_mode and query_words:
                    document_words = set(_topic_words(body))
                    coverage = len(query_words & document_words) / len(query_words)
                    required = 1.0 if len(query_words) <= 3 else 0.75
                    if coverage < required and semantic_relevance < 0.42:
                        continue
                if query and relevance <= 0 and semantic_relevance < 0.32:
                    continue

            facts = facts_by_chunk.get(item["id"], [])
            relevance = min(1.0, relevance + 0.05) if facts else relevance * 0.72
            ranked.append(
                {
                    "chunk_id": item["id"], "knowledge_key": item["knowledge_key"], "document_id": item["document_id"],
                    "source_file": item["source_file"], "document_label": item["document_label"],
                    "chapter_id": item["chapter_id"], "chapter": item["chapter_label"],
                    "section_id": item["section_id"], "section": item["section_label"], "page": item["page"],
                    "text": item["text"], "relevance": round(relevance, 6),
                    "lexical_relevance": round(relevance, 6),
                    "semantic_relevance": round(semantic_relevance, 6),
                    "retrieval_backend": semantic_backend,
                    "retrieval_fusion": "sparse-score",
                    "topic_scoped": bool(scope),
                    "topic_scope_label": str((scope or {}).get("label") or ""),
                    "facts": [{"fact_key": fact["fact_key"], "text": fact["fact_text"], "page": fact["page"]} for fact in facts],
                    "fact_keys": [fact["fact_key"] for fact in facts],
                }
            )

        semantic_ranked = [
            item for item in ranked
            if float(item.get("semantic_relevance") or 0.0) > 0
        ]
        if semantic_ranked:
            candidate_limit = min(250, max(limit * 8, 60))
            sparse_ranked = sorted(
                ranked,
                key=lambda item: (
                    float(item.get("lexical_relevance") or 0.0),
                    float(item.get("semantic_relevance") or 0.0),
                    -int(item.get("page") or 0),
                ),
                reverse=True,
            )
            sparse_rank = {
                str(item["chunk_id"]): rank
                for rank, item in enumerate(sparse_ranked[:candidate_limit], start=1)
            }
            semantic_ranked.sort(
                key=lambda item: (
                    float(item.get("semantic_relevance") or 0.0),
                    float(item.get("lexical_relevance") or 0.0),
                    -int(item.get("page") or 0),
                ),
                reverse=True,
            )
            semantic_rank = {
                str(item["chunk_id"]): rank
                for rank, item in enumerate(semantic_ranked[:candidate_limit], start=1)
            }
            sparse_weight = 1.0 - self.dense_weight
            rrf_k = 60.0
            rrf_scale = rrf_k + 1.0
            for item in ranked:
                chunk_id = str(item["chunk_id"])
                fused = 0.0
                if chunk_id in sparse_rank:
                    fused += sparse_weight / (rrf_k + float(sparse_rank[chunk_id]))
                if chunk_id in semantic_rank:
                    fused += self.dense_weight / (rrf_k + float(semantic_rank[chunk_id]))
                rrf_relevance = min(1.0, fused * rrf_scale)
                lexical_prior = max(0.0, min(1.0, float(item.get("lexical_relevance") or 0.0)))
                item["rrf_relevance"] = round(rrf_relevance, 6)
                item["relevance"] = round(min(1.0, 0.55 * rrf_relevance + 0.45 * lexical_prior), 6)
                item["retrieval_backend"] = semantic_backend
                item["retrieval_fusion"] = "weighted-rrf"

        ranked.sort(key=lambda item: (item["relevance"], -int(item["page"])), reverse=True)
        pool = ranked[: max(limit * 5, 30)]
        selected, exhausted = diverse_rank(pool, limit, used)
        if neighbor_pages and selected:
            # Matching may need three distinct definitions from adjacent slides;
            # lexical retrieval for "Bayes risk" alone often returns just the
            # risk slide and an unrelated end-of-course exercise. Expand around
            # the TOP retrieved slide only, staying within its document/chapter.
            radius = max(0, min(5, int(neighbor_pages)))
            anchor = selected[0]
            original_ids = {item["chunk_id"] for item in selected}
            nearby: list[dict] = []
            for row in rows:
                if row["id"] in original_ids or row["document_id"] != anchor["document_id"]:
                    continue
                distance = abs(int(row["page"]) - int(anchor["page"]))
                if distance > radius:
                    continue
                facts = facts_by_chunk.get(row["id"], [])
                nearby.append((distance, int(row["page"]), {
                    "chunk_id": row["id"], "knowledge_key": row["knowledge_key"],
                    "document_id": row["document_id"], "source_file": anchor["source_file"],
                    "document_label": anchor.get("document_label", ""),
                    "chapter_id": row["chapter_id"], "chapter": row["chapter_label"],
                    "section_id": row["section_id"], "section": row["section_label"],
                    "page": row["page"], "text": row["text"],
                    "relevance": 0.12, "topic_scoped": bool(scope),
                    "neighbor_context": True,
                    "facts": [{"fact_key": fact["fact_key"], "text": fact["fact_text"], "page": fact["page"]} for fact in facts],
                }))
            nearby.sort(key=lambda entry: (entry[0], entry[1]))
            selected.extend(item for _distance, _page, item in nearby[:14])
        return {
            "results": selected,
            "candidate_count": len(pool),
            "coverage_exhausted": exhausted,
            "topic_scope": scope or {},
            "retrieval_backend": semantic_backend,
            "retrieval_fusion": "weighted-rrf" if semantic_ranked else "sparse-score",
        }

    def matching_candidates(self, query: str, chapter_id: str, limit: int = 12) -> list[dict[str, Any]]:
        sql = "SELECT t.*,d.filename source_file FROM term_pairs t JOIN documents d ON d.id=t.document_id WHERE t.chapter_id=?"
        with self._connect() as connection:
            rows = [dict(row) for row in connection.execute(sql, (chapter_id,)).fetchall()]
            page_rows = [dict(row) for row in connection.execute(
                "SELECT DISTINCT p.page,p.section_label,p.text FROM pages p JOIN chunks c ON c.document_id=p.document_id WHERE c.chapter_id=? ORDER BY p.page",
                (chapter_id,),
            ).fetchall()]
        scope = _topic_scope(page_rows, str(query or "").strip()) if query else None
        query_words = set(_topic_words(query))
        usable = []
        for item in rows:
            page_number = int(item.get("page") or 0)
            if scope and not (int(scope["start"]) <= page_number <= int(scope["end"])):
                continue
            definition = str(item.get("definition") or "").strip()
            if not _valid_term(str(item.get("term") or "")):
                continue
            if len(definition.split()) < 4 or definition.endswith((":", "?")):
                continue
            if any(definition.count(left) != definition.count(right) for left, right in (("(", ")"), ("[", "]"))):
                continue
            body = f"{item['category']} {item['term']} {definition}"
            relevance = lexical_score(query, body) if query else 0.5
            if scope:
                relevance = max(relevance, 0.22 + 0.10 * lexical_score(scope.get("label", query), body))
            elif query_words:
                document_words = set(_topic_words(body))
                coverage = len(query_words & document_words) / len(query_words)
                required = 1.0 if len(query_words) <= 3 else 0.75
                if coverage < required:
                    continue
            item["relevance"] = relevance
            usable.append(item)
        usable.sort(key=lambda item: (item["relevance"], -item["page"]), reverse=True)
        return usable[: self._bounded_limit(limit, 12, 2, 30)]

    def health(self) -> dict[str, Any]:
        with self._connect() as connection:
            counts = {table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in ("documents", "pages", "chunks", "facts", "term_pairs")}
            version = connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0]
        return {
            **counts,
            "schema_version": int(version),
            "data_dir": str(self.data_dir),
            "retrieval": self.retrieval_backend_name(),
            "semantic_index": self._semantic_status(counts["chunks"]),
        }

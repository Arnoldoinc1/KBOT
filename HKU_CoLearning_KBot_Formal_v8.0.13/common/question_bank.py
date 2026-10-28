"""Teacher question bank: student pick + reserved teacher upsert.

Item schema for ``upsert_items`` / ``POST /question_bank/items`` body rows:

Required:
  - chapter_id (str)
  - question_type (true_false | mcq | matching | fill_blank | short_answer)
  - question (str)

Recommended:
  - topic (str; empty matches any when student leaves topic blank)
  - options_or_pairs (dict or JSON object string) with type-specific keys:
      true_false/mcq: options, correct_index
      matching: left, right, correct_mapping
      fill_blank: answer
      short_answer: reference or answer; optional key_points
  - correct_answer, explanation, question_fingerprint

Optional provenance: chapter, citations_json / citations, source_document,
source_page, source_excerpt, source_chunk_id, knowledge_key, fact_key,
fact_summary, is_active (default true).

Teammates own upload UI / CSV parsing; call ``upsert_items`` from that path.
"""

from __future__ import annotations

import hashlib
import json
import random
import uuid
from typing import Any

from common.models import TeacherQuestionBankItem, db


VALID_TYPES = {"true_false", "mcq", "matching", "fill_blank", "short_answer"}


def _loads(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def _dumps(value: Any) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("{") or raw.startswith("["):
            return raw
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def quiz_payload_from_item(item: TeacherQuestionBankItem) -> dict[str, Any] | None:
    """Rebuild a submit-ready quiz dict from a teacher bank row."""
    payload = _loads(item.options_or_pairs, {})
    if not isinstance(payload, dict):
        payload = {}
    question = str(item.question or "").strip()
    if not question:
        return None
    quiz: dict[str, Any] = {
        "type": str(item.question_type or ""),
        "question": question,
        "explanation": str(item.explanation or ""),
    }
    for key in ("options", "correct_index", "left", "right", "correct_mapping", "answer", "reference", "key_points"):
        if key in payload:
            quiz[key] = payload[key]
    quiz_type = quiz["type"]
    if quiz_type in {"true_false", "mcq"} and not quiz.get("options"):
        return None
    if quiz_type == "matching" and (not quiz.get("left") or not quiz.get("right")):
        return None
    if quiz_type == "fill_blank" and "answer" not in quiz:
        return None
    if quiz_type == "short_answer" and not (quiz.get("reference") or quiz.get("answer")):
        return None
    return quiz


def _fingerprint_for(row: dict[str, Any]) -> str:
    existing = str(row.get("question_fingerprint") or "").strip()
    if existing:
        return existing[:80]
    basis = "|".join(
        [
            str(row.get("chapter_id") or "").strip(),
            str(row.get("question_type") or "").strip(),
            str(row.get("topic") or "").strip().lower(),
            str(row.get("question") or "").strip(),
        ]
    )
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:80]


def pick_question(
    chapter_id: str,
    quiz_type: str,
    topic: str = "",
    used_fingerprints: list[Any] | None = None,
) -> TeacherQuestionBankItem | None:
    """Prefer an active teacher-bank question before AI generation.

    With a topic: same chapter + type + case-insensitive topic.
    With empty topic: any active item for chapter + type (random among unused).
    """
    chapter_id = str(chapter_id or "").strip()
    quiz_type = str(quiz_type or "").strip()
    if not chapter_id or quiz_type not in VALID_TYPES:
        return None

    used = {str(item) for item in (used_fingerprints or []) if item}
    rows = (
        TeacherQuestionBankItem.query.filter_by(
            chapter_id=chapter_id,
            question_type=quiz_type,
            is_active=True,
        )
        .order_by(TeacherQuestionBankItem.created_at.desc())
        .limit(200)
        .all()
    )
    topic_norm = str(topic or "").strip().lower()
    candidates: list[TeacherQuestionBankItem] = []
    for row in rows:
        fingerprint = str(row.question_fingerprint or "")
        if fingerprint and fingerprint in used:
            continue
        if quiz_payload_from_item(row) is None:
            continue
        row_topic = str(row.topic or "").strip().lower()
        if topic_norm and row_topic != topic_norm:
            continue
        candidates.append(row)
    if not candidates:
        return None
    if topic_norm:
        return candidates[0]
    return random.choice(candidates)


def upsert_items(rows: list[dict[str, Any]], uploaded_by: str = "") -> int:
    """Insert or update teacher bank items. Returns number of rows written.

    Matching key: ``question_fingerprint`` within the same ``chapter_id`` +
    ``question_type``. Missing fingerprints are derived from chapter/type/topic/question.
    """
    if not isinstance(rows, list):
        raise ValueError("rows must be a list of question objects")
    written = 0
    uploader = str(uploaded_by or "").strip()[:128]
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("each item must be an object")
        chapter_id = str(raw.get("chapter_id") or "").strip()
        question_type = str(raw.get("question_type") or "").strip()
        question = str(raw.get("question") or "").strip()
        if not chapter_id or question_type not in VALID_TYPES or not question:
            raise ValueError(
                "each item requires chapter_id, a valid question_type, and question"
            )
        fingerprint = _fingerprint_for(raw)
        options = raw.get("options_or_pairs", {})
        citations = raw.get("citations_json", raw.get("citations", []))
        existing = (
            TeacherQuestionBankItem.query.filter_by(
                chapter_id=chapter_id,
                question_type=question_type,
                question_fingerprint=fingerprint,
            )
            .order_by(TeacherQuestionBankItem.created_at.desc())
            .first()
        )
        if existing is None:
            existing = TeacherQuestionBankItem(
                id=uuid.uuid4().hex,
                chapter_id=chapter_id,
                question_type=question_type,
                question_fingerprint=fingerprint,
            )
            db.session.add(existing)

        existing.chapter = str(raw.get("chapter") or existing.chapter or "")[:256]
        existing.topic = str(raw.get("topic") or "")[:256]
        existing.question = question
        existing.options_or_pairs = _dumps(options)
        existing.correct_answer = str(raw.get("correct_answer") or "")
        existing.explanation = str(raw.get("explanation") or "")
        existing.citations_json = _dumps(citations if citations is not None else [])
        existing.source_document = str(raw.get("source_document") or "")[:255]
        page = raw.get("source_page")
        existing.source_page = int(page) if page is not None and str(page).strip() != "" else None
        existing.source_excerpt = str(raw.get("source_excerpt") or "")
        existing.source_chunk_id = str(raw.get("source_chunk_id") or "")[:160]
        existing.knowledge_key = str(raw.get("knowledge_key") or "")[:160]
        existing.fact_key = str(raw.get("fact_key") or "")[:80]
        existing.fact_summary = str(raw.get("fact_summary") or "")[:500]
        if uploader:
            existing.created_by = uploader
        elif not existing.created_by:
            existing.created_by = ""
        if "is_active" in raw:
            existing.is_active = bool(raw.get("is_active"))
        else:
            existing.is_active = True if existing.is_active is None else bool(existing.is_active)

        if quiz_payload_from_item(existing) is None:
            raise ValueError(
                f"item fingerprint={fingerprint} is missing type-specific answer fields in options_or_pairs"
            )
        written += 1

    db.session.commit()
    return written

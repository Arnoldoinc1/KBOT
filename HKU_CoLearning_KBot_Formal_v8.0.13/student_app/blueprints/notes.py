from __future__ import annotations

import json

from flask import Blueprint, jsonify, render_template, request, session

from common.auth import student_login_required
from common.knowledge_client import KnowledgeServiceError
from common.models import NotesQARecord, db
from common.notes_engine import answer_notes
from student_app.services import agent_router, knowledge_client


bp = Blueprint("notes", __name__)


@bp.get("/notes")
@student_login_required
def notes_page():
    chapters, error = [], ""
    try:
        chapters = knowledge_client().chapters()
    except KnowledgeServiceError:
        error = "Course materials are temporarily unavailable."
    return render_template("notes.html", chapters=chapters, knowledge_error=error)


@bp.post("/api/notes/ask")
@student_login_required
def ask_notes():
    data = request.get_json(silent=True) or {}
    question = str(data.get("question") or "").strip()
    chapter_id = str(data.get("chapter_id") or "").strip()
    if not (3 <= len(question) <= 1000) or not chapter_id:
        return jsonify({"ok": False, "error": "Enter a question and select a course chapter."}), 400
    try:
        search = knowledge_client().search(question, chapter_id, 8, {})
    except KnowledgeServiceError:
        return jsonify({"ok": False, "error": "Course materials are temporarily unavailable."}), 503
    result = answer_notes(question, search.get("results", []), agent_router(), session["student_username"])
    chapter = result["citations"][0].get("chapter", "") if result["citations"] else ""
    db.session.add(NotesQARecord(
        student_name=session["student_username"], chapter_id=chapter_id, chapter=chapter, question=question,
        answer=result["answer"], citations_json=json.dumps(result["citations"], ensure_ascii=False),
        insufficient_information=result["insufficient_information"], answering_source=result["answering_source"], source=result["answering_source"],
    ))
    db.session.commit()
    return jsonify({"ok": True, "answer": result["answer"], "citations": result["citations"], "insufficient_information": result["insufficient_information"]})


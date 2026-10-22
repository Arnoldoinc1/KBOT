from flask import Blueprint, render_template, session, url_for

from common.auth import student_login_required
from common.feedback_builder import build_record_review
from common.models import NotesQARecord, StudentQARecord
from common.quiz_flow import current_type


bp = Blueprint("history", __name__)


@bp.get("/history")
@student_login_required
def history_page():
    username = session["student_username"]
    exercise_records = StudentQARecord.query.filter_by(student_name=username).order_by(StudentQARecord.created_at.desc()).all()
    exercises = [build_record_review(record) for record in exercise_records]
    notes = NotesQARecord.query.filter_by(student_name=username).order_by(NotesQARecord.created_at.desc()).all()
    if session.get("chapter_id") and not session.get("quiz_complete"):
        back_to_quiz_url = url_for("exercise.quiz_page", quiz_type=current_type(session.get("quiz_current_type")))
        back_to_quiz_label = "Back to Quiz"
    else:
        back_to_quiz_url = url_for("exercise.setup_page")
        back_to_quiz_label = "Back to Exercise"
    return render_template(
        "history.html",
        exercises=exercises,
        notes=notes,
        back_to_quiz_url=back_to_quiz_url,
        back_to_quiz_label=back_to_quiz_label,
        history_page_active=True,
    )

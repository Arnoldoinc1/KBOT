from __future__ import annotations

from werkzeug.middleware.proxy_fix import ProxyFix

# Support both recommended module startup (python -m package.run) and
# VS Code/direct-file startup (python package/app.py) on Windows.
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from common.config import apply_overrides, coze_quiz_types, coze_runtime_enabled, database_url, env, env_bool, env_float, env_int, service_secret
from common.knowledge_client import KnowledgeServiceError
from common.models import db
from common.schema_compat import ensure_legacy_schema
from student_app.blueprints import auth, exercise, history, notes, portal
from student_app.services import agent_router, knowledge_client


BUILD_VERSION = "student-app-8.0.13"


def create_app(overrides: dict | None = None, enabled_modules: set[str] | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=0, x_proto=0, x_host=0, x_port=0, x_prefix=1)
    app.logger.setLevel(logging.INFO)
    config = {
        "SECRET_KEY": service_secret("STUDENT_SECRET_KEY"), "SQLALCHEMY_DATABASE_URI": database_url(),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False, "KNOWLEDGE_SERVICE_URL": env("KNOWLEDGE_SERVICE_URL", "http://127.0.0.1:5100"),
        "KNOWLEDGE_READ_KEY": (env("KNOWLEDGE_READ_KEY") or "local-read-key-change-before-deployment"), "KNOWLEDGE_TIMEOUT": env_float("KNOWLEDGE_TIMEOUT", 15, 2, 120),
        "COZE_ENABLED": coze_runtime_enabled(), "COZE_API_BASE": env("COZE_API_BASE", "https://api.coze.com"), "COZE_TOKEN": env("COZE_TOKEN"),
        "COZE_QUIZ_TOKEN": env("COZE_QUIZ_TOKEN"), "COZE_GRADING_TOKEN": env("COZE_GRADING_TOKEN"), "COZE_NOTES_TOKEN": env("COZE_NOTES_TOKEN"),
        "COZE_QUIZ_BOT_ID": env("COZE_QUIZ_BOT_ID"), "COZE_GRADING_BOT_ID": env("COZE_GRADING_BOT_ID"), "COZE_NOTES_BOT_ID": env("COZE_NOTES_BOT_ID"),
        "COZE_TIMEOUT": env_float("COZE_TIMEOUT", 25, 5, 120), "COZE_STREAM_ENABLED": env_bool("COZE_STREAM_ENABLED", True),
        "COZE_QUIZ_TIMEOUT": env_float("COZE_QUIZ_TIMEOUT", env_float("COZE_TIMEOUT", 25, 5, 120), 5, 120),
        "COZE_GRADING_TIMEOUT": env_float("COZE_GRADING_TIMEOUT", env_float("COZE_TIMEOUT", 25, 5, 120), 5, 120),
        "COZE_NOTES_TIMEOUT": env_float("COZE_NOTES_TIMEOUT", env_float("COZE_TIMEOUT", 25, 5, 120), 5, 120),
        "COZE_CIRCUIT_FAILURES": env_int("COZE_CIRCUIT_FAILURES", 3, 1, 20),
        "COZE_CIRCUIT_COOLDOWN": env_float("COZE_CIRCUIT_COOLDOWN", 60, 5, 900),
        "GENERATION_LOCK_TTL": env_float("GENERATION_LOCK_TTL", 90, 15, 600),
        "DEMO_USER": env("DEMO_USER", "rukizhao"), "DEMO_PASS": env("DEMO_PASS", "zhaoruoqi"),
        "SESSION_COOKIE_PATH": env("SESSION_COOKIE_PATH", "/"),
        "SESSION_COOKIE_NAME": "kbot_student_session", "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": env("SESSION_COOKIE_SAMESITE", "Lax"),
        "SESSION_COOKIE_SECURE": env_bool("SESSION_COOKIE_SECURE", env("KBOT_ENV", "development").casefold() == "production"),
        "TESTING": False,
    }
    app.config.update(apply_overrides(config, overrides))
    db.init_app(app)
    modules = enabled_modules if enabled_modules is not None else {item.strip() for item in env("STUDENT_MODULES", "exercise,notes,history").split(",") if item.strip()}
    app.config["ENABLED_STUDENT_MODULES"] = modules
    app.register_blueprint(auth.bp)
    app.register_blueprint(portal.bp)
    if "exercise" in modules:
        app.register_blueprint(exercise.bp)
    if "notes" in modules:
        app.register_blueprint(notes.bp)
    if "history" in modules:
        app.register_blueprint(history.bp)

    with app.app_context():
        db.create_all()
        ensure_legacy_schema(db)

    @app.get("/health")
    def health():
        status = {"ok": True, "service": "student", "build": BUILD_VERSION, "database": False, "knowledge": False}
        try:
            db.session.execute(text("SELECT 1"))
            status["database"] = True
        except SQLAlchemyError:
            status["ok"] = False
        try:
            knowledge_client().health()
            status["knowledge"] = True
        except KnowledgeServiceError:
            status["ok"] = False
        status["coze_enabled"] = bool(app.config.get("COZE_ENABLED"))
        router = agent_router()
        status["agents"] = {kind.value: router.config(kind).configured for kind in router.configs}
        status["agent_circuits"] = router.circuit_state()
        status["quiz_agent_types"] = sorted(coze_quiz_types()) if status["coze_enabled"] else []
        return jsonify(status), 200 if status["ok"] else 503

    @app.get("/api/build-info")
    def build_info():
        return jsonify({"ok": True, "service": "student", "build": BUILD_VERSION, "modules": sorted(modules), "agent_routing": "quiz/grading/notes-separated", "coze_enabled": bool(app.config.get("COZE_ENABLED")), "quiz_agent_types": sorted(coze_quiz_types())})

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"ok": False, "error": "Page not found."}), 404

    @app.errorhandler(500)
    def internal_error(_error):
        app.logger.exception("Unhandled student application error")
        return jsonify({"ok": False, "error": "The request could not be completed."}), 500
    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host=env("STUDENT_HOST", "127.0.0.1"),
        port=env_int("STUDENT_PORT", 8000, 1, 65535),
        debug=False,
    )

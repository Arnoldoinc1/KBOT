from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED_PROJECT_FILES = (
    "common/config.py",
    "common/models.py",
    "knowledge_service/repository.py",
    "student_app/blueprints/exercise.py",
    "teacher_app/templates/login.html",
    "teacher_app/kahoot_template.xlsx",
)
REQUIRED_PACKAGES = {
    "flask": "Flask",
    "flask_login": "Flask-Login",
    "flask_sqlalchemy": "Flask-SQLAlchemy",
    "sqlalchemy": "SQLAlchemy",
    "requests": "requests",
    "dotenv": "python-dotenv",
    "pypdf": "pypdf",
    "docx": "python-docx",
    "pymysql": "PyMySQL",
    "openpyxl": "openpyxl",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", default="all", choices=("all", "knowledge", "teacher", "student"))
    args = parser.parse_args()

    print(f"[KBot] Project root: {ROOT}")
    print(f"[KBot] Python: {sys.executable}")
    print(f"[KBot] Python version: {sys.version.split()[0]}")
    print(f"[KBot] Requested service: {args.service}")

    missing_files = [name for name in REQUIRED_PROJECT_FILES if not (ROOT / name).is_file()]
    if missing_files:
        print("[KBot ERROR] This is not a complete KBot project folder.")
        print("[KBot ERROR] A HOTFIX_OVERLAY ZIP cannot be run by itself.")
        for name in missing_files:
            print(f"  missing: {name}")
        print("Extract the complete HKU_CoLearning_KBot_Formal_v8.0.13.zip and run from its root folder.")
        return 3

    missing_packages = [display for module, display in REQUIRED_PACKAGES.items() if importlib.util.find_spec(module) is None]
    if missing_packages:
        print("[KBot ERROR] Required Python packages are missing:")
        for name in missing_packages:
            print(f"  - {name}")
        print("Run INSTALL_WINDOWS.bat once, then retry.")
        return 4

    env_file = ROOT / ".env"
    if env_file.is_file():
        print("[KBot] Root .env: found")
    else:
        print("[KBot WARNING] Root .env was not found. Copy .env.example to .env and fill it in.")

    if not os.environ.get("APP_SECRET_KEY", "").strip() and env_file.is_file():
        # python-dotenv is intentionally loaded by common.config below.
        from common.config import env
        if not env("APP_SECRET_KEY"):
            print("[KBot WARNING] APP_SECRET_KEY is blank. A local fallback will be used; set a real value before deployment.")

    from common.config import coze_quiz_types, coze_runtime_enabled, database_url, env, env_source, resolve_path

    deployment_mode = env("KBOT_ENV", "development").casefold().strip() or "development"
    resolved_database_url = database_url()
    print(f"[KBot] Deployment mode: {deployment_mode}")
    print(f"[KBot] Database driver: {resolved_database_url.split(':', 1)[0]}")
    print(f"[KBot] Docker MySQL volume: {env('MYSQL_VOLUME_NAME', 'edu_qa_mysql_data')}")
    print(f"[KBot] Knowledge URL: {env('KNOWLEDGE_SERVICE_URL', 'http://127.0.0.1:5100')}")

    if deployment_mode == "production":
        production_errors: list[str] = []
        if resolved_database_url.casefold().startswith("sqlite"):
            production_errors.append("DATABASE_URL must use shared MySQL rather than SQLite.")
        secret = env("APP_SECRET_KEY")
        if len(secret) < 32 or "change_me" in secret.casefold() or "replace" in secret.casefold():
            production_errors.append("APP_SECRET_KEY must be a real random secret of at least 32 characters.")
        for key_name in ("KNOWLEDGE_ADMIN_KEY", "KNOWLEDGE_READ_KEY"):
            key_value = env(key_name)
            if len(key_value) < 16 or "change_me" in key_value.casefold() or "replace" in key_value.casefold() or key_value.startswith("local-"):
                production_errors.append(f"{key_name} must be replaced with a private deployment key.")
        if env("ALLOW_TEACHER_REGISTRATION", "false").casefold() in {"1", "true", "yes", "on"}:
            production_errors.append("ALLOW_TEACHER_REGISTRATION must be false after teacher accounts are provisioned.")
        if env("LEGACY_TEACHER_COMPAT", "false").casefold() in {"1", "true", "yes", "on"}:
            production_errors.append("LEGACY_TEACHER_COMPAT must be false to prevent legacy teacher seeding.")
        if production_errors:
            print("[KBot ERROR] Production preflight rejected unsafe configuration:")
            for item in production_errors:
                print(f"  - {item}")
            print("Start from .env.production.example and replace every CHANGE_ME value.")
            return 5

    coze_enabled = coze_runtime_enabled()
    print(f"[KBot] Coze runtime: {'enabled' if coze_enabled else 'disabled (local fallback mode)'}")
    quiz_types = ', '.join(sorted(coze_quiz_types())) if coze_enabled else ''
    print(f"[KBot] Quiz Agent exercise types: {quiz_types or '(none)'}")
    print(
        "[KBot] Coze timeouts: "
        f"quiz={env('COZE_QUIZ_TIMEOUT', env('COZE_TIMEOUT', '25'))}s; "
        f"grading={env('COZE_GRADING_TIMEOUT', env('COZE_TIMEOUT', '25'))}s; "
        f"notes={env('COZE_NOTES_TIMEOUT', env('COZE_TIMEOUT', '25'))}s"
    )
    print(
        "[KBot] Coze circuit breaker: "
        f"failures={env('COZE_CIRCUIT_FAILURES', '3')}; "
        f"cooldown={env('COZE_CIRCUIT_COOLDOWN', '60')}s"
    )
    def semantic_stack_ready(model_path: str, enabled: str) -> bool:
        return (
            enabled.casefold() in {'1', 'true', 'yes', 'on'}
            and resolve_path(model_path).is_dir()
            and importlib.util.find_spec('chromadb') is not None
            and importlib.util.find_spec('sentence_transformers') is not None
        )

    if args.service in {'all', 'knowledge'}:
        knowledge_model_path = env('KNOWLEDGE_EMBEDDING_MODEL_PATH', 'models/bge-base-en-v1.5')
        backend = 'chroma+rrf' if semantic_stack_ready(
            knowledge_model_path,
            env('KNOWLEDGE_CHROMA_ENABLED', 'true'),
        ) else 'sqlite-lexical'
        print(f"[KBot] Knowledge RAG retrieval: {backend}")

    if args.service in {'all', 'teacher'}:
        model_path = env('TEACHER_SEMANTIC_MODEL_PATH') or env(
            'TEACHER_EMBEDDING_MODEL_PATH',
            'models/bge-base-en-v1.5',
        )
        chroma_ready = semantic_stack_ready(model_path, env('TEACHER_CHROMA_ENABLED', 'true'))
        backend = 'chroma+rrf' if chroma_ready else 'hybrid-sparse-vector'
        print(f"[KBot] Teacher record search: {backend}")
    shared_token = env('COZE_TOKEN')
    for label, token_name, bot_name in (
        ('Quiz', 'COZE_QUIZ_TOKEN', 'COZE_QUIZ_BOT_ID'),
        ('Grading', 'COZE_GRADING_TOKEN', 'COZE_GRADING_BOT_ID'),
        ('Notes', 'COZE_NOTES_TOKEN', 'COZE_NOTES_BOT_ID'),
    ):
        token_value = env(token_name) or shared_token
        token_source = env_source(token_name) if env(token_name) else env_source('COZE_TOKEN')
        bot_value = env(bot_name)
        configured = bool(coze_enabled and token_value and bot_value)
        print(
            f"[KBot] {label} Agent: {'configured' if configured else 'not configured'}; "
            f"token_source={token_source}; bot_id_source={env_source(bot_name)}"
        )
    if not env_file.is_file() and not coze_enabled:
        print("[KBot] No root .env: bundled SQLite data and deterministic local fallbacks will be used.")
        print("[KBot] To call Coze, copy .env.example to .env, fill the credentials, and keep COZE_ENABLED=true.")
    print("[KBot] Startup preflight passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

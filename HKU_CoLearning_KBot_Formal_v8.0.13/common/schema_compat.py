from __future__ import annotations

from sqlalchemy import inspect, text

# Columns introduced after the v6.2 shared database.  Adding them in-place keeps
# existing users and student history available instead of creating a new DB.
COLUMNS: dict[str, dict[str, str]] = {
    "users": {"created_at": "DATETIME"},
    "student_qa_records": {
        "chapter_id": "VARCHAR(160) NOT NULL DEFAULT ''",
        "generation_source": "VARCHAR(32) NOT NULL DEFAULT 'local_fallback'",
        "grading_source": "VARCHAR(32) NOT NULL DEFAULT 'local'",
        "citations_json": "TEXT",
        "source_document": "VARCHAR(255) NOT NULL DEFAULT ''",
        "source_page": "INTEGER",
        "source_pages_json": "TEXT",
        "source_excerpt": "TEXT",
        "source_chunk_id": "VARCHAR(160) NOT NULL DEFAULT ''",
        "knowledge_key": "VARCHAR(160) NOT NULL DEFAULT ''",
        "fact_key": "VARCHAR(80) NOT NULL DEFAULT ''",
        "fact_summary": "VARCHAR(500) NOT NULL DEFAULT ''",
        "question_fingerprint": "VARCHAR(80) NOT NULL DEFAULT ''",
        "diversity_exhausted": "BOOLEAN NOT NULL DEFAULT 0",
    },
    "notes_qa_records": {
        "insufficient_information": "BOOLEAN NOT NULL DEFAULT 0",
        "answering_source": "VARCHAR(32) NOT NULL DEFAULT 'local_fallback'",
    },
    "quiz_sessions": {
        "used_chunks_json": "TEXT",
        "used_pages_json": "TEXT",
        "used_facts_json": "TEXT",
        "used_fingerprints_json": "TEXT",
        "current_quiz_json": "TEXT",
        "generation_failures_json": "TEXT",
        "skipped_types_json": "TEXT",
        "exhausted_count": "INTEGER NOT NULL DEFAULT 0",
    },
}

BACKFILLS = (
    ("student_qa_records", "citations_json", "[]"),
    ("student_qa_records", "source_pages_json", "[]"),
    ("quiz_sessions", "used_chunks_json", "[]"),
    ("quiz_sessions", "used_pages_json", "[]"),
    ("quiz_sessions", "used_facts_json", "[]"),
    ("quiz_sessions", "used_fingerprints_json", "[]"),
    ("quiz_sessions", "current_quiz_json", "{}"),
    ("quiz_sessions", "generation_failures_json", "{}"),
    ("quiz_sessions", "skipped_types_json", "[]"),
)


def ensure_legacy_schema(db) -> list[str]:
    """Upgrade a v6.2 database in place without altering account hashes/data."""
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    changes: list[str] = []
    for table, definitions in COLUMNS.items():
        if table not in table_names:
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, definition in definitions.items():
            if name in existing:
                continue
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
            changes.append(f"{table}.{name}")

    # Refresh after ALTER because a table may have been created by db.create_all.
    inspector = inspect(db.engine)
    columns_by_table = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in inspector.get_table_names()
    }
    for table, column, value in BACKFILLS:
        if column in columns_by_table.get(table, set()):
            db.session.execute(
                text(f"UPDATE {table} SET {column}=:value WHERE {column} IS NULL OR {column}=''"),
                {"value": value},
            )
    if "created_at" in columns_by_table.get("users", set()):
        db.session.execute(text("UPDATE users SET created_at=CURRENT_TIMESTAMP WHERE created_at IS NULL"))
    db.session.commit()
    return changes

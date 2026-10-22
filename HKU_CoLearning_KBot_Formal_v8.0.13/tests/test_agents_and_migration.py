from __future__ import annotations

import json
import os
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

from common.coze_transport import AgentConfig, AgentKind
from common.grading_engine import grade_short_answer, normalize_grading
from common.notes_engine import answer_notes, normalize_notes


class StaticRouter:
    def __init__(self, kind, content):
        self.kind = kind
        self.content = content

    def config(self, kind):
        configured = AgentKind(kind) == self.kind
        return AgentConfig(AgentKind(kind), "https://api.test", "token" if configured else "", "bot" if configured else "")

    def request(self, kind, _prompt, _user):
        assert AgentKind(kind) == self.kind
        return type("Response", (), {"content": self.content})()


def test_grading_agent_schema_clamps_score_and_filters_citations():
    raw = json.dumps({"is_correct": "true", "score": "120", "reasoning": "According to [Reference 1], the answer is supported.", "correct_answer": "GPS", "citations": [1, 99], "insufficient_evidence": "false"})
    result = normalize_grading(raw, "GPS", 1)
    assert result["score"] == 100 and result["citations"] == [1]


def test_short_answer_routes_to_grading_agent():
    raw = json.dumps({"is_correct": True, "score": 90, "reasoning": "Supported by [Reference 1].", "correct_answer": "GPS is satellite navigation.", "citations": [1], "insufficient_evidence": False})
    router = StaticRouter(AgentKind.GRADING, raw)
    result = grade_short_answer({"question": "What is GPS?", "reference": "GPS is satellite navigation."}, "It is satellite navigation.", [{"source_file": "notes.pdf", "section": "GPS", "page": 62, "excerpt": "GPS is satellite navigation."}], router, "student")
    assert result["grading_source"] == "coze_grading_agent"


def test_notes_agent_validates_reference_ids_and_never_returns_quiz_json():
    refs = [{"reference_id": 1, "source_file": "notes.pdf", "chapter": "Chapter 3", "section": "GPS", "page": 62, "excerpt": "GPS is satellite navigation.", "chunk_id": "c1", "knowledge_key": "k1"}]
    normalized = normalize_notes('{"answer":"GPS is satellite navigation.","used_reference_ids":[1,5],"insufficient_information":false}', refs)
    assert normalized["used_reference_ids"] == [1]
    chunks = [{"source_file": "notes.pdf", "chapter": "Chapter 3", "section": "GPS", "page": 62, "text": "GPS is satellite navigation.", "chunk_id": "c1", "knowledge_key": "k1"}]
    router = StaticRouter(AgentKind.NOTES, '{"type":"mcq","question":"Wrong task"}')
    result = answer_notes("What is GPS?", chunks, router, "student")
    assert result["answering_source"] == "local_fallback"
    assert "type" not in result["answer"]


def test_legacy_sqlite_migration_preserves_account_and_history(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    legacy_hash = generate_password_hash("legacy-pass")
    connection.executescript("""
      CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username VARCHAR(80) UNIQUE NOT NULL, password_hash VARCHAR(256) NOT NULL, name VARCHAR(80) NOT NULL DEFAULT '', role VARCHAR(20) NOT NULL DEFAULT 'student');
      CREATE TABLE student_qa_records (id VARCHAR(64) PRIMARY KEY, student_name VARCHAR(128) NOT NULL, chapter VARCHAR(128) DEFAULT '', question_type VARCHAR(32) NOT NULL, topic VARCHAR(256) DEFAULT '', question TEXT NOT NULL, answer TEXT NOT NULL, options_or_pairs TEXT, correct_answer TEXT, is_correct BOOLEAN DEFAULT 0, score INTEGER DEFAULT 0, ai_feedback TEXT, teacher_feedback TEXT, explanation TEXT, source VARCHAR(16) DEFAULT 'coze', teacher_score INTEGER, teacher_verified BOOLEAN DEFAULT 0, verified_by VARCHAR(128) DEFAULT '', verified_at VARCHAR(32) DEFAULT '', time VARCHAR(32) DEFAULT '', update_time VARCHAR(32) DEFAULT '', created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
      INSERT INTO student_qa_records(id,student_name,question_type,question,answer) VALUES('legacy-record','legacy_student','mcq','Old question','Old answer');
    """)
    connection.execute(
        "INSERT INTO users(username,password_hash,name,role) VALUES(?,?,?,?)",
        ("legacy_student", legacy_hash, "Legacy Student", "student"),
    )
    connection.commit(); connection.close()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    from scripts.migrate_db import migrate
    changes = migrate()
    connection = sqlite3.connect(database)
    account = connection.execute("SELECT username,password_hash FROM users WHERE username='legacy_student'").fetchone()
    assert account[0] == "legacy_student"
    assert account[1] == legacy_hash
    assert check_password_hash(account[1], "legacy-pass")
    assert connection.execute("SELECT id FROM student_qa_records WHERE id='legacy-record'").fetchone()[0] == "legacy-record"
    columns = {row[1] for row in connection.execute("PRAGMA table_info(student_qa_records)")}
    assert {"grading_source", "fact_key", "citations_json"} <= columns
    connection.close()


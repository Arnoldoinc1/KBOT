#!/usr/bin/env sh
set -eu
python scripts/migrate_db.py
python -m knowledge_service.run & KNOWLEDGE_PID=$!
python -m teacher_app.run & TEACHER_PID=$!
python -m student_app.run & STUDENT_PID=$!
trap 'kill $KNOWLEDGE_PID $TEACHER_PID $STUDENT_PID 2>/dev/null || true' INT TERM EXIT
wait


#!/usr/bin/env sh
set -eu
python scripts/migrate_db.py
exec python -m student_app.run

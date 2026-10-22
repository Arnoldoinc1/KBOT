#!/usr/bin/env sh
set -eu
python scripts/migrate_db.py
exec python -m teacher_app.run

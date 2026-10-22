from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.models import User, db
from teacher_app.app import create_app


parser = argparse.ArgumentParser(description="Create or reset a teacher account in the shared database.")
parser.add_argument("username")
parser.add_argument("--name", default="Teacher")
args = parser.parse_args()
password = getpass.getpass("Teacher password (6+ characters): ")
if len(password) < 6:
    raise SystemExit("Password must contain at least 6 characters.")
app = create_app({"SEED_DEMO_TEACHER": False, "LEGACY_TEACHER_COMPAT": False})
with app.app_context():
    user = User.query.filter_by(username=args.username).first()
    if user is None:
        user = User(username=args.username, name=args.name, role="teacher", password_hash="")
        db.session.add(user)
    user.name, user.role = args.name, "teacher"
    user.set_password(password)
    db.session.commit()
print(f"Teacher account ready: {args.username}")


from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config import database_url
from common.models import db
from common.schema_compat import ensure_legacy_schema
from student_app.app import create_app


def migrate() -> list[str]:
    app = create_app({"SQLALCHEMY_DATABASE_URI": database_url(), "TESTING": True}, enabled_modules=set())
    with app.app_context():
        db.create_all()
        return ensure_legacy_schema(db)


if __name__ == "__main__":
    changed = migrate()
    print(f"Database migration complete. URL type={database_url().split(':',1)[0]}; columns added={len(changed)}")
    for item in changed:
        print(f"  added {item}")

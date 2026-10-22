from __future__ import annotations

# Lists account metadata only. Password hashes are never printed or changed.
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from common.config import database_url


def safe_database_label(value: str) -> str:
    try:
        return make_url(value).render_as_string(hide_password=True)
    except Exception:
        return "configured database"


def main() -> int:
    url = database_url()
    print(f"[KBot] Database: {safe_database_label(url)}")
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as connection:
            if "users" not in inspect(connection).get_table_names():
                print("[KBot] The users table does not exist in this database.")
                return 2
            rows = connection.execute(
                text("SELECT id, username, name, role FROM users ORDER BY id")
            ).mappings().all()
    except Exception as exc:
        print(f"[KBot ERROR] Could not read the configured database: {exc.__class__.__name__}: {exc}")
        return 1

    if not rows:
        print("[KBot] No accounts were found in the configured database.")
        return 2

    print(f"[KBot] Accounts found: {len(rows)}")
    print(" ID | ROLE      | USERNAME                         | NAME")
    print("----+-----------+----------------------------------+------------------------------")
    for row in rows:
        print(f"{str(row['id']):>3} | {str(row.get('role') or '')[:9]:<9} | {str(row.get('username') or '')[:32]:<32} | {str(row.get('name') or '')[:30]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.config import env, env_int
from .app import create_app


app = create_app()

if __name__ == "__main__":
    app.run(host=env("TEACHER_HOST", "127.0.0.1"), port=env_int("TEACHER_PORT", 5000, 1, 65535), debug=False)


from __future__ import annotations

import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from knowledge_service.app import create_app as create_knowledge_app


class LiveServer:
    def __init__(self, app):
        self.server = make_server("127.0.0.1", 0, app, threaded=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.thread.join(timeout=5)


@pytest.fixture
def knowledge_server(tmp_path):
    app = create_knowledge_app({
        "TESTING": True, "KNOWLEDGE_DATA_DIR": str(tmp_path / "knowledge"),
        "KNOWLEDGE_ADMIN_KEY": "admin-test", "KNOWLEDGE_READ_KEY": "read-test",
    })
    with LiveServer(app) as server:
        yield server


@pytest.fixture
def real_pdf():
    return Path(__file__).resolve().parents[1] / "test_data" / "Ch-3_Enabling_Technologies_2025.pdf"


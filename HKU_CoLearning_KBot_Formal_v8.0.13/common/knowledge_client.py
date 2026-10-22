from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter


class KnowledgeServiceError(RuntimeError):
    pass


class KnowledgeClient:
    def __init__(self, base_url: str, read_key: str = "", admin_key: str = "", timeout: float = 15.0, session=None):
        self.base_url = str(base_url or "").rstrip("/")
        self.read_key = read_key
        self.admin_key = admin_key
        self.timeout = float(timeout)
        self.session = session or requests.Session()
        adapter = HTTPAdapter(max_retries=0)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _headers(self, admin: bool) -> dict[str, str]:
        return {"X-Knowledge-Admin-Key" if admin else "X-Knowledge-Read-Key": self.admin_key if admin else self.read_key}

    def _request(self, method: str, path: str, *, admin: bool = False, **kwargs) -> dict[str, Any]:
        if not self.base_url:
            raise KnowledgeServiceError("Knowledge Service URL is not configured.")
        try:
            response = self.session.request(
                method, f"{self.base_url}{path}", headers={**self._headers(admin), **kwargs.pop("headers", {})},
                timeout=kwargs.pop("timeout", self.timeout), **kwargs,
            )
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise KnowledgeServiceError("Knowledge Service is unavailable.") from exc
        if not response.ok or not payload.get("ok"):
            raise KnowledgeServiceError(str(payload.get("error") or "Knowledge Service request failed."))
        return payload

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def chapters(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/chapters").get("chapters", [])

    def search(
        self,
        query: str,
        chapter_id: str,
        limit: int = 8,
        used: dict | None = None,
        topic_mode: bool = False,
        neighbor_pages: int = 0,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/search",
            json={
                "query": query,
                "chapter_id": chapter_id,
                "limit": limit,
                "used": used or {},
                "topic_mode": bool(topic_mode),
                "neighbor_pages": max(0, min(5, int(neighbor_pages))),
            },
        )

    def matching_candidates(self, query: str, chapter_id: str, limit: int = 12) -> list[dict[str, Any]]:
        return self._request("POST", "/api/matching-candidates", json={"query": query, "chapter_id": chapter_id, "limit": limit}).get("candidates", [])

    def documents(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/admin/documents", admin=True).get("documents", [])

    def upload(self, data: bytes, filename: str, uploaded_by: str = "") -> dict[str, Any]:
        return self._request(
            "POST", "/api/admin/documents", admin=True,
            files={"file": (Path(filename).name, io.BytesIO(data))}, data={"uploaded_by": uploaded_by},
            timeout=max(60.0, self.timeout),
        )["document"]

    def delete(self, document_id: str) -> None:
        self._request("DELETE", f"/api/admin/documents/{document_id}", admin=True)


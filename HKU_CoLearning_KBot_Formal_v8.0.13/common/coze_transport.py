from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

try:
    import requests
    from requests.adapters import HTTPAdapter
    RequestFailure = requests.RequestException
except ImportError:  # permits dependency diagnostics and pure-core offline tests
    requests = None
    HTTPAdapter = None
    RequestFailure = OSError

from .config import coze_runtime_enabled, env, env_bool, env_float
from .json_recovery import StructuredOutputError, parse_json_like


class AgentKind(str, Enum):
    QUIZ = "quiz"
    GRADING = "grading"
    NOTES = "notes"


class CozeTransportError(RuntimeError):
    """Internal transport failure. Its message must not be returned to students."""


@dataclass(frozen=True)
class AgentConfig:
    kind: AgentKind
    api_base: str
    token: str
    bot_id: str
    timeout: float = 25.0
    stream: bool = True

    @property
    def configured(self) -> bool:
        return bool(self.token.strip() and self.bot_id.strip())


@dataclass(frozen=True)
class CozeResponse:
    content: str
    agent: AgentKind
    bot_id: str
    chat_id: str = ""
    conversation_id: str = ""
    recovered_from_persisted_message: bool = False


def _agent_token(kind: AgentKind, shared: str) -> str:
    return env(f"COZE_{kind.value.upper()}_TOKEN", shared)


def configs_from_env() -> dict[AgentKind, AgentConfig]:
    enabled = coze_runtime_enabled()
    shared_token = env("COZE_TOKEN") if enabled else ""
    base = env("COZE_API_BASE", "https://api.coze.com")
    timeout = env_float("COZE_TIMEOUT", 25.0, 5.0, 120.0)
    stream = env_bool("COZE_STREAM_ENABLED", True)
    return {
        AgentKind.QUIZ: AgentConfig(AgentKind.QUIZ, base, _agent_token(AgentKind.QUIZ, shared_token) if enabled else "", env("COZE_QUIZ_BOT_ID") if enabled else "", timeout, stream),
        AgentKind.GRADING: AgentConfig(AgentKind.GRADING, base, _agent_token(AgentKind.GRADING, shared_token) if enabled else "", env("COZE_GRADING_BOT_ID") if enabled else "", timeout, stream),
        AgentKind.NOTES: AgentConfig(AgentKind.NOTES, base, _agent_token(AgentKind.NOTES, shared_token) if enabled else "", env("COZE_NOTES_BOT_ID") if enabled else "", timeout, stream),
    }


class CozeAgentRouter:
    def __init__(
        self,
        configs: dict[AgentKind, AgentConfig] | None = None,
        session: Any | None = None,
        *,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ):
        self.configs = configs or configs_from_env()
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_seconds = max(1.0, float(cooldown_seconds))
        self._failures: dict[AgentKind, int] = {kind: 0 for kind in AgentKind}
        self._open_until: dict[AgentKind, float] = {kind: 0.0 for kind in AgentKind}
        if session is None and requests is None:
            raise RuntimeError("The requests package is required for Coze transport.")
        self.session = session or requests.Session()
        # A task makes one create-chat call. HTTP-level retries are deliberately disabled.
        if HTTPAdapter is not None and hasattr(self.session, "mount"):
            adapter = HTTPAdapter(max_retries=0)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)

    def config(self, kind: AgentKind | str) -> AgentConfig:
        key = AgentKind(kind)
        return self.configs[key]

    @staticmethod
    def _headers(config: AgentConfig, stream: bool | None = None) -> dict[str, str]:
        use_stream = config.stream if stream is None else stream
        return {
            "Authorization": f"Bearer {config.token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if use_stream else "application/json",
        }

    @staticmethod
    def _data(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        return payload.get("data") if isinstance(payload.get("data"), dict) else payload

    @classmethod
    def _ids(cls, payload: Any) -> tuple[str, str]:
        data = cls._data(payload)
        chat_id = str(data.get("chat_id") or data.get("id") or "")
        conversation_id = str(data.get("conversation_id") or "")
        return chat_id, conversation_id

    @classmethod
    def _message_items(cls, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        data = payload.get("data", payload)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("messages", "items", "list"):
                items = data.get(key)
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
        return []

    @classmethod
    def extract_answer(cls, payload: Any) -> str:
        if isinstance(payload, str):
            return payload.strip()
        containers = [payload, cls._data(payload)] if isinstance(payload, dict) else []
        for container in containers:
            if not isinstance(container, dict):
                continue
            for key in ("answer", "content", "output", "text"):
                value = container.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        answers: list[str] = []
        for message in cls._message_items(payload):
            if str(message.get("role") or "").casefold() != "assistant":
                continue
            if str(message.get("type") or "answer").casefold() not in {"answer", ""}:
                continue
            content = str(message.get("content") or "").strip()
            if content:
                answers.append(content)
        return max(answers, key=len) if answers else ""

    @staticmethod
    def _complete_structured(content: str) -> bool:
        try:
            parse_json_like(content)
            # parse_json_like repairs truncation, so separately require a real final bracket.
            stripped = str(content or "").strip().rstrip("`").strip()
            return stripped.endswith("}") or stripped.endswith("]")
        except (StructuredOutputError, ValueError, TypeError):
            return False

    @classmethod
    def parse_sse(cls, lines: Iterable[bytes | str]) -> tuple[list[str], str, str]:
        completed: list[str] = []
        delta_by_message: dict[str, list[str]] = {}
        all_deltas: list[str] = []
        chat_id = ""
        conversation_id = ""
        named_event = ""
        for raw in lines:
            line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            line = line.strip()
            if not line:
                continue
            if line.startswith("event:"):
                named_event = line[6:].strip()
                continue
            if not line.startswith("data:"):
                continue
            body = line[5:].strip()
            if body in {"[DONE]", '"[DONE]"'}:
                break
            try:
                envelope = json.loads(body)
            except json.JSONDecodeError:
                continue
            event = str(envelope.get("event") or envelope.get("event_type") or named_event or "")
            data = envelope.get("data") if isinstance(envelope.get("data"), dict) else envelope
            event_chat, event_conversation = cls._ids(envelope)
            chat_id = chat_id or event_chat
            conversation_id = conversation_id or event_conversation
            if event.endswith(("failed", "requires_action", "canceled", "cancelled")):
                raise CozeTransportError("Coze stream reported a terminal failure.")
            if not event.startswith("conversation.message"):
                continue
            if str(data.get("role") or "").casefold() != "assistant":
                continue
            if str(data.get("type") or "answer").casefold() not in {"answer", ""}:
                continue
            content = str(data.get("content") or "")
            message_id = str(data.get("id") or "answer")
            if event.endswith(".delta"):
                delta_by_message.setdefault(message_id, []).append(content)
                all_deltas.append(content)
            elif event.endswith(".completed") and content:
                completed.append(content)
        completed.extend("".join(parts) for parts in delta_by_message.values() if parts)
        if all_deltas:
            completed.append("".join(all_deltas))
        unique = list(dict.fromkeys(item.strip() for item in completed if item.strip()))
        return unique, chat_id, conversation_id

    def _messages(self, config: AgentConfig, conversation_id: str, chat_id: str) -> str:
        response = self.session.get(
            f"{config.api_base.rstrip('/')}/v3/chat/message/list",
            headers=self._headers(config, False),
            params={"conversation_id": conversation_id, "chat_id": chat_id},
            timeout=(5, min(15.0, config.timeout)),
        )
        response.raise_for_status()
        return self.extract_answer(response.json())

    def _poll_persisted(self, config: AgentConfig, conversation_id: str, chat_id: str) -> str:
        deadline = time.monotonic() + config.timeout
        status = ""
        while time.monotonic() < deadline:
            response = self.session.get(
                f"{config.api_base.rstrip('/')}/v3/chat/retrieve",
                headers=self._headers(config, False),
                params={"conversation_id": conversation_id, "chat_id": chat_id},
                timeout=(5, min(15.0, config.timeout)),
            )
            response.raise_for_status()
            payload = response.json()
            direct = self.extract_answer(payload)
            if direct:
                return direct
            data = self._data(payload)
            status = str(data.get("status") or "").casefold()
            if status in {"completed", "succeeded"}:
                break
            if status in {"failed", "requires_action", "canceled", "cancelled"}:
                raise CozeTransportError("Coze chat ended without a usable answer.")
            time.sleep(0.45)
        saved = self._messages(config, conversation_id, chat_id)
        if saved:
            return saved
        raise CozeTransportError(f"Coze produced no persisted answer (status={status or 'unknown'}).")

    def _request_once(self, kind: AgentKind | str, prompt: str, user_id: str) -> CozeResponse:
        config = self.config(kind)
        if not config.configured:
            raise CozeTransportError(f"The {config.kind.value} Agent is not configured.")
        task_user = f"{str(user_id or 'student')[:48]}-{uuid.uuid4().hex[:12]}"
        payload = {
            "bot_id": config.bot_id,
            "user_id": task_user,
            "stream": config.stream,
            # Needed only for message-list recovery; Coze Agent Memory remains disabled.
            "auto_save_history": True,
            "additional_messages": [
                {"role": "user", "type": "question", "content": prompt, "content_type": "text"}
            ],
        }
        try:
            response = self.session.post(
                f"{config.api_base.rstrip('/')}/v3/chat",
                headers=self._headers(config),
                json=payload,
                timeout=(5, config.timeout),
                stream=config.stream,
            )
            response.raise_for_status()
            content_type = str(response.headers.get("content-type", "")).casefold()
            if config.stream and "event-stream" in content_type:
                candidates, chat_id, conversation_id = self.parse_sse(response.iter_lines())
                complete = [item for item in candidates if self._complete_structured(item)]
                if complete:
                    return CozeResponse(max(complete, key=len), config.kind, config.bot_id, chat_id, conversation_id)
                if chat_id and conversation_id:
                    saved = self._messages(config, conversation_id, chat_id)
                    if saved:
                        return CozeResponse(saved, config.kind, config.bot_id, chat_id, conversation_id, True)
                if candidates:
                    return CozeResponse(max(candidates, key=len), config.kind, config.bot_id, chat_id, conversation_id)
                raise CozeTransportError("Coze stream contained no assistant answer.")

            result = response.json()
            if isinstance(result, dict) and result.get("code") not in (None, 0, "0"):
                raise CozeTransportError("Coze rejected the request.")
            direct = self.extract_answer(result)
            chat_id, conversation_id = self._ids(result)
            if direct:
                return CozeResponse(direct, config.kind, config.bot_id, chat_id, conversation_id)
            if chat_id and conversation_id:
                saved = self._poll_persisted(config, conversation_id, chat_id)
                return CozeResponse(saved, config.kind, config.bot_id, chat_id, conversation_id, True)
            raise CozeTransportError("Coze returned neither content nor persistent message identifiers.")
        except (RequestFailure, OSError, ValueError, json.JSONDecodeError) as exc:
            raise CozeTransportError(f"{config.kind.value} Agent transport failed.") from exc

    def circuit_open(self, kind: AgentKind | str) -> bool:
        key = AgentKind(kind)
        until = self._open_until.get(key, 0.0)
        if until and time.monotonic() >= until:
            self._open_until[key] = 0.0
            self._failures[key] = 0
            return False
        return bool(until and time.monotonic() < until)

    def _record_success(self, kind: AgentKind) -> None:
        self._failures[kind] = 0
        self._open_until[kind] = 0.0

    def _record_failure(self, kind: AgentKind) -> None:
        count = self._failures.get(kind, 0) + 1
        self._failures[kind] = count
        if count >= self.failure_threshold:
            self._open_until[kind] = time.monotonic() + self.cooldown_seconds

    def circuit_state(self) -> dict[str, dict[str, float | int | bool]]:
        now = time.monotonic()
        state: dict[str, dict[str, float | int | bool]] = {}
        for kind in AgentKind:
            open_until = self._open_until.get(kind, 0.0)
            remaining = max(0.0, open_until - now) if open_until else 0.0
            state[kind.value] = {
                "open": bool(remaining > 0),
                "failures": int(self._failures.get(kind, 0)),
                "retry_after_seconds": round(remaining, 3),
            }
        return state

    def request(self, kind: AgentKind | str, prompt: str, user_id: str) -> CozeResponse:
        key = AgentKind(kind)
        # A missing configuration is a deployment choice, not a transport
        # outage, so it must not consume the circuit-breaker failure budget.
        if not self.config(key).configured:
            raise CozeTransportError(f"The {key.value} Agent is not configured.")
        if self.circuit_open(key):
            raise CozeTransportError(
                f"The {key.value} Agent circuit is temporarily open after repeated transport failures."
            )
        try:
            response = self._request_once(key, prompt, user_id)
        except CozeTransportError:
            self._record_failure(key)
            raise
        self._record_success(key)
        return response

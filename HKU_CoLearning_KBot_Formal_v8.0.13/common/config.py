from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - reported by startup diagnostics
    load_dotenv = None


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"


def _dotenv_keys(path: Path) -> set[str]:
    """Read only key names so diagnostics can report where values came from.

    Values are deliberately not parsed or logged here.  This small parser is
    sufficient for the conventional KEY=value lines used by KBot's .env file.
    """
    if not path.is_file():
        return set()
    keys: set[str] = set()
    try:
        for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if key.startswith("export "):
                key = key[7:].strip()
            if key:
                keys.add(key)
    except OSError:
        return set()
    return keys


# Capture the process environment before python-dotenv adds root-file values.
# This lets startup diagnostics distinguish a Windows/system environment value
# from a value supplied by the project .env without exposing either secret.
_PROCESS_ENV_KEYS = set(os.environ)
_ENV_FILE_KEYS = _dotenv_keys(ENV_PATH)

# The single root .env is optional and never overwrites process/service values.
if load_dotenv is not None and ENV_PATH.is_file():
    load_dotenv(ENV_PATH, override=False)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_source(name: str) -> str:
    """Return a non-secret source label for one configuration variable."""
    if name in _PROCESS_ENV_KEYS and os.environ.get(name, "").strip():
        return "process_environment"
    if name in _ENV_FILE_KEYS and os.environ.get(name, "").strip():
        return "root_env_file"
    return "default_or_blank"


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def env_int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def env_float(name: str, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def coze_quiz_types() -> set[str]:
    """Return exercise types that should call the external Quiz Agent.

    Objective types already have deterministic, course-grounded constructors.
    The production default sends MCQ and Short Answer generation to Coze.
    Deterministic constructors remain authoritative fallbacks, while True/False,
    Matching and Fill Blank avoid unnecessary external latency. Set ``COZE_QUIZ_TYPES=all`` to restore Agent calls for every
    type, provide a comma-separated subset, or use ``none`` for local generation.
    """
    valid = {"true_false", "mcq", "matching", "fill_blank", "short_answer"}
    aliases = {
        "tf": "true_false", "truefalse": "true_false", "true/false": "true_false",
        "multiple_choice": "mcq", "multiple-choice": "mcq",
        "fillblank": "fill_blank", "fill-blank": "fill_blank",
        "shortanswer": "short_answer", "short-answer": "short_answer",
    }
    raw = env("COZE_QUIZ_TYPES", "mcq,short_answer").casefold().strip()
    if raw in {"all", "*"}:
        return valid
    if raw in {"none", "off", "local", "false", "0"}:
        return set()
    selected: set[str] = set()
    for item in raw.split(","):
        value = aliases.get(item.strip(), item.strip())
        if value in valid:
            selected.add(value)
    return selected or {"mcq", "short_answer"}


def coze_runtime_enabled() -> bool:
    """Decide whether external Coze calls are allowed for this process.

    ``COZE_ENABLED=auto`` is the safe compatibility default:
    - a project root .env exists -> credentials in that file may enable Coze;
    - no project .env -> KBot runs as an offline/local-fallback demo, even if
      stale COZE_* values happen to exist in the Windows user environment.

    Environment-only deployments remain supported by setting
    ``COZE_ENABLED=true`` explicitly in the process/service environment.
    """
    raw = env("COZE_ENABLED", "auto").casefold()
    if raw in {"1", "true", "yes", "on", "y", "enabled", "agent"}:
        return True
    if raw in {"0", "false", "no", "off", "n", "disabled", "local"}:
        return False
    return ENV_PATH.is_file()


def resolve_path(value: str | Path, default: Path | None = None) -> Path:
    raw = str(value or "").strip()
    path = Path(raw) if raw else (default or ROOT_DIR)
    return path if path.is_absolute() else ROOT_DIR / path


def database_url() -> str:
    default_path = ROOT_DIR / "data" / "shared" / "kbot.db"
    raw = env("DATABASE_URL", f"sqlite:///{default_path.as_posix()}")
    if raw.startswith("sqlite:///") and not raw.startswith("sqlite:////"):
        path = resolve_path(raw.removeprefix("sqlite:///"), default_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"
    return raw


def app_secret() -> str:
    """Return the root secret with v6.2 environment-name compatibility."""
    return (
        env("APP_SECRET_KEY")
        or env("FLASK_SECRET_KEY")
        or env("SECRET_KEY")
        or "local-development-secret-change-before-deployment"
    )


def service_secret(specific_name: str) -> str:
    return env(specific_name) or app_secret()


def apply_overrides(config: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, Any]:
    if overrides:
        config.update(overrides)
    return config

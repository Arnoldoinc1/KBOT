from __future__ import annotations

import ast
import json
import re
from typing import Any


class StructuredOutputError(ValueError):
    """Raised when model text cannot be recovered into a JSON-like value."""


def strip_fences(text: object) -> str:
    value = str(text or "").strip().lstrip("\ufeff")
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)(?:```|$)", value, re.IGNORECASE)
    return (fenced.group(1) if fenced else value).strip()


def balanced_values(text: str) -> list[str]:
    values: list[str] = []
    for start, opening in enumerate(text):
        if opening not in "{[":
            continue
        stack: list[str] = []
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char in "{[":
                stack.append(char)
            elif char in "}]":
                if not stack or (stack[-1], char) not in {("{", "}"), ("[", "]")}:
                    break
                stack.pop()
                if not stack:
                    values.append(text[start : index + 1])
                    break
    return values


def close_truncated_json(text: str) -> str:
    value = strip_fences(text)
    starts = [position for position in (value.find("{"), value.find("[")) if position >= 0]
    if not starts:
        return value
    value = value[min(starts) :]
    stack: list[str] = []
    in_string = False
    escaped = False
    for char in value:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char in "}]" and stack and (stack[-1], char) in {("{", "}"), ("[", "]")}:
            stack.pop()
    if escaped:
        value = value[:-1]
    if in_string:
        value += '"'
    value = re.sub(r",\s*$", "", value)
    value = re.sub(r":\s*$", ': ""', value)
    for opening in reversed(stack):
        value += "}" if opening == "{" else "]"
    return value


def parse_json_like(raw: object) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    text = strip_fences(raw)
    repaired = close_truncated_json(text)
    candidates = [text, repaired, *balanced_values(text)]
    decoder = json.JSONDecoder()
    list_fallback: list[Any] | None = None
    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        parsers = (json.loads, ast.literal_eval)
        for parser in parsers:
            try:
                value = parser(candidate)
            except (json.JSONDecodeError, ValueError, SyntaxError, TypeError):
                continue
            if isinstance(value, dict):
                return value
            if isinstance(value, list) and list_fallback is None:
                list_fallback = value
        for index, char in enumerate(candidate):
            if char not in "{[":
                continue
            try:
                value, _ = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
            if isinstance(value, list) and list_fallback is None:
                list_fallback = value
    if list_fallback is not None:
        return list_fallback
    raise StructuredOutputError("No recoverable JSON value was found.")


def clamp_int(value: object, minimum: int, maximum: int, default: int = 0) -> int:
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value or "").strip().casefold()
    if normalized in {"true", "yes", "y", "1", "correct"}:
        return True
    if normalized in {"false", "no", "n", "0", "incorrect"}:
        return False
    return default


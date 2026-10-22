from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Iterable


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'_-]*")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "is", "it",
    "of", "on", "or", "that", "the", "this", "to", "what", "when", "where", "which", "who", "why",
    "with", "can", "could", "would", "according", "notes", "explain", "describe",
    # Natural learner topic cues are search intent, not subject matter.
    "definition", "meaning", "define", "working",
}


def tokens(value: object) -> list[str]:
    output: list[str] = []
    for token in TOKEN_RE.findall(str(value or "")):
        token = token.casefold()
        if len(token) > 5 and token.endswith("ing"):
            token = token[:-3]
        elif len(token) > 4 and token.endswith("ed"):
            token = token[:-2]
        elif len(token) > 3 and token.endswith("s"):
            token = token[:-1]
        if token and token not in STOPWORDS:
            output.append(token)
    return output


def lexical_score(query: object, document: object) -> float:
    query_terms = tokens(query)
    document_terms = tokens(document)
    if not query_terms or not document_terms:
        return 0.0
    query_counts = Counter(query_terms)
    document_counts = Counter(document_terms)
    intersection = sum(min(count, document_counts.get(term, 0)) for term, count in query_counts.items())
    coverage = intersection / max(1, sum(query_counts.values()))
    phrase = " ".join(query_terms)
    phrase_bonus = 1.0 if phrase and phrase in " ".join(document_terms) else 0.0
    density = min(1.0, intersection / max(2.0, math.sqrt(len(document_terms))))
    return min(1.0, 0.72 * coverage + 0.18 * density + 0.10 * phrase_bonus)


def fingerprint(value: object) -> str:
    normalized = " ".join(tokens(value))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def jaccard(left: object, right: object) -> float:
    a, b = set(tokens(left)), set(tokens(right))
    return len(a & b) / len(a | b) if a and b else 0.0


def diverse_rank(items: list[dict], limit: int, used: dict | None = None) -> tuple[list[dict], bool]:
    used = used or {}
    used_chunks = set(map(str, used.get("chunks", [])))
    used_pages = [int(value) for value in used.get("pages", []) if str(value).isdigit()]
    used_facts = set(map(str, used.get("facts", [])))
    selected: list[dict] = []
    remaining = list(items)
    unused_exists = any(str(item.get("chunk_id")) not in used_chunks for item in remaining)
    while remaining and len(selected) < limit:
        best = None
        best_score = -999.0
        for item in remaining:
            score = float(item.get("relevance", 0.0))
            chunk_id = str(item.get("chunk_id") or "")
            page = int(item.get("page") or 0)
            fact_keys = set(map(str, item.get("fact_keys", [])))
            if chunk_id in used_chunks:
                score -= 0.55
            if page and used_pages:
                score -= 0.24 if page == used_pages[-1] else (0.08 if page in used_pages else 0.0)
            if fact_keys and fact_keys <= used_facts:
                score -= 0.36
            if selected:
                similarity = max(jaccard(item.get("text"), chosen.get("text")) for chosen in selected)
                score -= 0.34 * similarity
                if any(page and page == int(chosen.get("page") or 0) for chosen in selected):
                    score -= 0.16
            if score > best_score:
                best, best_score = item, score
        if best is None:
            break
        best = dict(best)
        best["selection_score"] = round(best_score, 6)
        selected.append(best)
        remaining.remove(next(item for item in remaining if item is best or item.get("chunk_id") == best.get("chunk_id")))
    exhausted = bool(used_chunks) and not unused_exists
    return selected, exhausted


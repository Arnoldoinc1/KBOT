from __future__ import annotations

from dataclasses import dataclass

from common.quiz_engine import QUIZ_TYPES
from common.quiz_parser import canonical_type


@dataclass(frozen=True)
class FlowTransition:
    current_type: str
    next_type: str | None
    completed: bool
    advanced: bool


def current_type(value: object) -> str:
    normalized = canonical_type(value or "true_false")
    return normalized if normalized in QUIZ_TYPES else "true_false"


def request_matches_current(requested: object, current: object) -> bool:
    return current_type(requested) == current_type(current)


def transition(current: object, is_correct: bool) -> FlowTransition:
    active = current_type(current)
    if active == "short_answer":
        return FlowTransition(active, None, True, False)
    if not is_correct:
        return FlowTransition(active, active, False, False)
    index = QUIZ_TYPES.index(active)
    next_type = QUIZ_TYPES[index + 1]
    return FlowTransition(active, next_type, False, True)


def skip_transition(current: object) -> FlowTransition:
    """Advance after an explicitly audited unavailable-stage skip.

    This is used only when generation recovery has failed and no active quiz is
    present.  It prevents a learner being trapped forever at one type while
    keeping normal correct/incorrect progression server-authoritative.
    """
    active = current_type(current)
    if active == "short_answer":
        return FlowTransition(active, None, True, True)
    index = QUIZ_TYPES.index(active)
    return FlowTransition(active, QUIZ_TYPES[index + 1], False, True)

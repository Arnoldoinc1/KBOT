from __future__ import annotations

import re
from typing import Any

from knowledge_service.retrieval import lexical_score

from .coze_transport import AgentKind, CozeAgentRouter, CozeTransportError
from .json_recovery import coerce_bool, parse_json_like
from .quiz_parser import clean_text


NOT_FOUND = "I could not find this information in the uploaded course notes."


def references_from_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, 1):
        output.append({
            "reference_id": index, "source_file": chunk.get("source_file", ""),
            "chapter": chunk.get("chapter", ""), "section": chunk.get("section", ""), "page": chunk.get("page"),
            "excerpt": clean_text(chunk.get("text"))[:850], "chunk_id": chunk.get("chunk_id", ""),
            "knowledge_key": chunk.get("knowledge_key", ""), "score": chunk.get("relevance", 0),
        })
    return output


def notes_prompt(question: str, references: list[dict[str, Any]]) -> str:
    context = "\n\n".join(
        f"[Reference {item['reference_id']}] File={item['source_file']} | Chapter={item['chapter']} | Section={item['section']} | Page={item['page']}\n{item['excerpt']}"
        for item in references
    )
    return f"""TASK: Answer one student's question.
Use ALLOWED REFERENCES as the primary course context when they are relevant. You may use your general knowledge to interpret fragmentary or incomplete note text, connect implied facts, or answer when the retrieved references are insufficient.
For questions asking for conditions, assumptions, requirements, components, or factors, check ALL relevant references and include each distinct supported condition. Do not confuse a prerequisite with an advantage, disadvantage, consequence, or example. If the references give only a partial list, say which parts the notes support and identify any extra explanation as general knowledge.
For mathematics, preserve the meaning and direction of conditional probabilities. Never invent a formula or guess a symbol missing from an extracted slide. If equation text is corrupt or incomplete, explain only the relationship supported by readable words, and acknowledge a missing formula when necessary.
Do not invent filenames, pages, quotations, or reference IDs. Cite only reference IDs that genuinely contributed to the answer; if the answer comes only from general knowledge, use an empty used_reference_ids list.
Set insufficient_information=true only when you cannot provide a useful answer at all.
STUDENT QUESTION: {question}
ALLOWED REFERENCE IDS: {[item['reference_id'] for item in references]}

ALLOWED REFERENCES:
{context}

Return only this JSON schema:
{{"answer":"concise answer","used_reference_ids":[1],"insufficient_information":false}}
"""


def normalize_notes(raw: object, references: list[dict[str, Any]]) -> dict[str, Any]:
    payload = parse_json_like(raw)
    if not isinstance(payload, dict):
        raise ValueError("Notes output is not an object.")
    allowed = {item["reference_id"] for item in references}
    used: list[int] = []
    value = payload.get("used_reference_ids", payload.get("citations", []))
    for item in value if isinstance(value, list) else []:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if number in allowed and number not in used:
            used.append(number)
    insufficient = coerce_bool(payload.get("insufficient_information"), False)
    answer = clean_text(payload.get("answer"))
    if insufficient:
        answer, used = NOT_FOUND, []
    elif not answer:
        raise ValueError("Notes answer lacks a valid answer.")
    return {"answer": answer, "used_reference_ids": used, "insufficient_information": insufficient}


def local_notes_answer(question: str, references: list[dict[str, Any]]) -> dict[str, Any]:
    candidates: list[tuple[float, str, int]] = []
    for reference in references:
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", reference["excerpt"]):
            sentence = clean_text(sentence).strip("•–- ")
            score = lexical_score(question, sentence)
            if len(sentence) >= 30 and score > 0:
                candidates.append((score, sentence, reference["reference_id"]))
    candidates.sort(reverse=True)
    if not candidates or candidates[0][0] < 0.18:
        return {"answer": NOT_FOUND, "used_reference_ids": [], "insufficient_information": True}
    chosen = candidates[:3]
    answer_parts: list[str] = []
    used: list[int] = []
    for _, sentence, reference_id in chosen:
        if sentence not in answer_parts:
            answer_parts.append(sentence)
        if reference_id not in used:
            used.append(reference_id)
    return {"answer": " ".join(answer_parts), "used_reference_ids": used, "insufficient_information": False}


def answer_notes(question: str, chunks: list[dict[str, Any]], router: CozeAgentRouter, user_id: str) -> dict[str, Any]:
    references = references_from_chunks(chunks)
    result = None
    source = "local_fallback"
    if router.config(AgentKind.NOTES).configured:
        try:
            response = router.request(AgentKind.NOTES, notes_prompt(question, references), user_id)
            result = normalize_notes(response.content, references)
            source = "coze_notes_agent"
        except (CozeTransportError, ValueError):
            result = None
    if result is None:
        result = local_notes_answer(question, references)
    used = set(result["used_reference_ids"])
    result["citations"] = [item for item in references if item["reference_id"] in used]
    result["answering_source"] = source
    return result


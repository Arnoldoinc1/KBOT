from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from common.coze_transport import AgentConfig, AgentKind
from common.feedback_builder import build_detailed_feedback
from common.grading_engine import grade_short_answer, local_semantic_grade, normalize_grading
from common.quiz_engine import FocusFact, generate_quiz, local_quiz, validate_grounding
from knowledge_service.document_parser import fact_sentences, parse_document, split_chunks


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "test_data" / "Ch-3_Enabling_Technologies_2025.pdf"


class StaticRouter:
    def __init__(self, quiz_content: str = "", grading_content: str = ""):
        self.quiz_content = quiz_content
        self.grading_content = grading_content

    def config(self, kind):
        key = AgentKind(kind)
        configured = bool(self.quiz_content if key == AgentKind.QUIZ else self.grading_content if key == AgentKind.GRADING else "")
        return AgentConfig(key, "https://api.test", "token" if configured else "", "bot" if configured else "")

    def request(self, kind, _prompt, _user):
        key = AgentKind(kind)
        content = self.quiz_content if key == AgentKind.QUIZ else self.grading_content
        return type("Response", (), {"content": content})()


def page_chunks(page_number: int) -> list[dict]:
    pages = parse_document(PDF.read_bytes(), PDF.name)
    output: list[dict] = []
    for index, chunk in enumerate(split_chunks(pages)):
        if chunk["page"] != page_number:
            continue
        chunk.update(
            {
                "source_file": PDF.name,
                "chunk_id": f"p{page_number}-{index}",
                "knowledge_key": f"k{page_number}-{index}",
                "facts": [
                    {"text": text, "fact_key": f"p{page_number}-f{fact_index}"}
                    for fact_index, text in enumerate(fact_sentences(chunk["text"]))
                ],
            }
        )
        output.append(chunk)
    return output


def focus_for(chunks: list[dict], phrase: str = "") -> FocusFact:
    for chunk in chunks:
        for fact in chunk.get("facts", []):
            if not phrase or phrase.casefold() in fact["text"].casefold():
                return FocusFact(fact["text"], fact["fact_key"], chunk)
    raise AssertionError("No focus fact was found")


class ShortAnswerGenerationTests(unittest.TestCase):
    def test_page_19_question_names_definition_and_three_lbs_types(self):
        chunks = page_chunks(19)
        focus = focus_for(chunks, "location-based service")
        quiz, citations = local_quiz("short_answer", focus, chunks, [], "LBS")
        self.assertEqual(len(quiz["key_points"]), 4)
        self.assertIn("Pull:", quiz["reference"])
        self.assertIn("Push:", quiz["reference"])
        self.assertIn("Tracking:", quiz["reference"])
        self.assertIn("define location-based service", quiz["question"].casefold())
        self.assertIn("Pull", quiz["question"])
        self.assertIn("Push", quiz["question"])
        self.assertIn("Tracking", quiz["question"])
        self.assertNotIn("points about LBS", quiz["question"])
        self.assertEqual(len(citations), 4)
        validate_grounding(quiz, chunks, [], focus)

    def test_long_application_list_is_not_arbitrarily_cut_to_four(self):
        chunks = page_chunks(20)
        focus = focus_for(chunks, "Receiving alerts")
        quiz, _citations = local_quiz("short_answer", focus, chunks, [], "LBS")
        self.assertEqual(len(quiz["key_points"]), 1)
        self.assertIn("Receiving alerts", quiz["question"])
        self.assertNotIn("4 points", quiz["question"])

    def test_page_22_preserves_all_three_bullet_relations(self):
        chunks = page_chunks(22)
        focus = focus_for(chunks, "restrict results")
        quiz, _citations = local_quiz("short_answer", focus, chunks, [], "LBS")
        self.assertEqual(len(quiz["key_points"]), 3)
        self.assertTrue(any("filter" in point.casefold() for point in quiz["key_points"]))
        self.assertTrue(any("pointer" in point.casefold() for point in quiz["key_points"]))
        self.assertTrue(any("area alarm" in point.casefold() for point in quiz["key_points"]))

    def test_agent_short_answer_is_completed_from_server_evidence(self):
        chunks = page_chunks(19)
        response = json.dumps(
            {
                "type": "short_answer",
                "question": "What is LBS?",
                "key_points": ["Only the first point."],
                "reference": "Only the first point.",
                "explanation": "Only the first point.",
            }
        )
        with patch.dict(os.environ, {"COZE_QUIZ_TYPES": "all"}):
            generated = generate_quiz(
                "short_answer",
                "LBS",
                {"results": chunks},
                [],
                {},
                StaticRouter(quiz_content=response),
                "student",
            )
        self.assertEqual(generated.generation_source, "coze_quiz_agent")
        self.assertEqual(len(generated.quiz["key_points"]), 4)
        self.assertIn("Tracking:", generated.quiz["explanation"])
        self.assertIn("define location-based service", generated.quiz["question"].casefold())
        self.assertIn("Pull", generated.quiz["question"])
        self.assertIn("Push", generated.quiz["question"])
        self.assertIn("Tracking", generated.quiz["question"])
        self.assertNotEqual(generated.quiz["question"], "What is LBS?")

    def test_page_12_gyroscope_uses_three_principles_not_application_as_fourth(self):
        chunks = page_chunks(12)
        focus = focus_for(chunks, "Spinning Motion")
        quiz, citations = local_quiz("short_answer", focus, chunks, [], "gyroscope")
        self.assertEqual(len(quiz["key_points"]), 3)
        self.assertIn("Spinning Motion", quiz["question"])
        self.assertIn("Conservation of Angular Momentum", quiz["question"])
        self.assertIn("Precession", quiz["question"])
        self.assertNotIn("four principles", quiz["question"].casefold())
        self.assertNotIn("Applications:", quiz["reference"])
        self.assertEqual(len(citations), 3)
        validate_grounding(quiz, chunks, [], focus)


class ShortAnswerGradingTests(unittest.TestCase):
    def setUp(self):
        self.points = [
            "Pull means the customer initiates the positioning request.",
            "Push means the provider initiates the positioning request.",
            "Tracking means either party requests the terminal location.",
        ]
        self.reference = " ".join(f"({index}) {point}" for index, point in enumerate(self.points, 1))

    def test_backend_recalculates_score_from_every_key_point(self):
        raw = json.dumps(
            {
                "is_correct": True,
                "score": 100,
                "reasoning": "The answer covers two required points but omits the third point. The result is therefore incomplete.",
                "correct_answer": "shortened answer",
                "key_point_results": [
                    {"index": 1, "credit": 100, "comment": "The Pull point is fully covered."},
                    {"index": 2, "credit": 100, "comment": "The Push point is fully covered."},
                    {"index": 3, "credit": 0, "comment": "The Tracking point is not addressed."},
                ],
                "citations": [1, 2, 3],
                "insufficient_evidence": False,
            }
        )
        result = normalize_grading(raw, self.reference, 3, self.points)
        self.assertEqual(result["score"], 67)
        self.assertNotEqual(result["score"], 100)
        self.assertEqual(result["correct_answer"], self.reference)
        self.assertEqual(len(result["key_point_results"]), 3)

    def test_obvious_full_coverage_cannot_be_undergraded_by_agent(self):
        points = [
            "Spinning Motion: A gyroscope consists of a wheel or rotor that spins rapidly around its axis, generating angular momentum.",
            "Conservation of Angular Momentum: The gyroscope resists changes to its rotational axis, maintaining its position even when external forces are applied.",
            "Precession: When an external torque acts on the tilted gyroscope, its axis moves in a circular path around the vertical.",
        ]
        answer = " ".join(points)
        raw = json.dumps({
            "is_correct": False,
            "score": 63,
            "reasoning": "The first three points are present, but the response is only partly complete.",
            "correct_answer": "shortened",
            "key_point_results": [
                {"index": 1, "credit": 75, "comment": "The first point is fully explained."},
                {"index": 2, "credit": 75, "comment": "The second point is fully explained."},
                {"index": 3, "credit": 75, "comment": "The third point is fully explained."},
            ],
            "citations": [1, 2, 3],
            "insufficient_evidence": False,
        })
        result = normalize_grading(raw, " ".join(points), 3, points, answer)
        self.assertEqual(result["score"], 100)
        self.assertTrue(result["is_correct"])
        self.assertTrue(all(item["credit"] == 100 for item in result["key_point_results"]))

    def test_incomplete_feedback_is_rejected(self):
        raw = json.dumps(
            {
                "is_correct": False,
                "score": 0,
                "reasoning": "Your answer differs from the notes. According to the course material, an LBS",
                "correct_answer": self.reference,
                "key_point_results": [
                    {"index": 1, "credit": 0, "comment": "The Pull point is not addressed."},
                    {"index": 2, "credit": 0, "comment": "The Push point is not addressed."},
                    {"index": 3, "credit": 0, "comment": "The Tracking point is not addressed."},
                ],
                "citations": [1],
                "insufficient_evidence": False,
            }
        )
        with self.assertRaises(ValueError):
            normalize_grading(raw, self.reference, 3, self.points)

    def test_incomplete_agent_feedback_falls_back_to_complete_local_result(self):
        raw = json.dumps(
            {
                "is_correct": False,
                "score": 0,
                "reasoning": "According to the course material, an LBS",
                "correct_answer": "short",
                "key_point_results": [],
                "citations": [],
                "insufficient_evidence": False,
            }
        )
        quiz = {
            "type": "short_answer",
            "question": "Explain three LBS interaction types.",
            "key_points": self.points,
            "reference": self.reference,
        }
        result = grade_short_answer(
            quiz,
            self.points[0],
            [{"source_file": "notes.pdf", "section": "LBS", "page": 19, "excerpt": point} for point in self.points],
            StaticRouter(grading_content=raw),
            "student",
        )
        self.assertEqual(result["grading_source"], "local_fallback")
        self.assertTrue(result["reasoning"].endswith("."))
        self.assertEqual(len(result["key_point_results"]), 3)

    def test_one_of_three_points_cannot_receive_full_marks(self):
        result = local_semantic_grade(self.points[0], self.reference, 3, self.points)
        self.assertLess(result["score"], 60)
        self.assertNotEqual(result["score"], 100)

    def test_legacy_single_score_contract_remains_available(self):
        raw = json.dumps(
            {
                "is_correct": True,
                "score": 90,
                "reasoning": "The answer is semantically equivalent to the reference answer.",
                "correct_answer": self.reference,
                "citations": [1],
                "insufficient_evidence": False,
            }
        )
        result = normalize_grading(raw, self.reference, 1)
        self.assertEqual(result["score"], 90)
        self.assertEqual(result["key_point_results"], [])

    def test_teacher_audit_feedback_contains_rubric_and_point_results(self):
        quiz = {
            "type": "short_answer",
            "question": "Explain the three points.",
            "key_points": self.points,
            "reference": self.reference,
            "explanation": self.reference,
        }
        result = {
            "is_correct": False,
            "score": 33,
            "reasoning": "The response covers only one of the three required course-note points.",
            "correct_answer": self.reference,
            "key_point_results": [
                {"index": 1, "credit": 100, "comment": "The Pull point is fully covered."},
                {"index": 2, "credit": 0, "comment": "The Push point is not addressed."},
                {"index": 3, "credit": 0, "comment": "The Tracking point is not addressed."},
            ],
            "grading_source": "coze_grading_agent",
        }
        feedback = build_detailed_feedback(
            quiz,
            self.points[0],
            result,
            [{"source_file": "notes.pdf", "section": "LBS", "page": 19, "excerpt": point} for point in self.points],
        )
        self.assertIn("Required key points:", feedback)
        self.assertIn("Key-point assessment:", feedback)
        self.assertIn("3. 0/100", feedback)
        self.assertIn("Reference answer:", feedback)

    def test_student_javascript_renders_key_point_assessment(self):
        source = (ROOT / "student_app" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('makeNode("h4", "Key-point assessment")', source)
        self.assertIn("result.key_point_results", source)


if __name__ == "__main__":
    unittest.main()

# v8.0.8 Demo Regression Test Report

## Purpose

This report records the checks performed for the three failures observed during demo recording: stale topic reuse, intermittent GPS Fill Blank failure, and True/False answers always appearing as True.

## Executed checks

### Source and syntax

- `python -m compileall -q common knowledge_service student_app teacher_app tests scripts`: passed.
- `node --check student_app/static/app.js`: passed.

### Dependency-light automated suites

- `python scripts/run_core_tests.py`: 38/38 passed.
- `python -m unittest -v tests.test_feedback_and_kahoot tests.test_short_answer_quality`: 25/25 passed.

The core suite includes:

- a real-PDF regression that repeats MCQ generation before Fill Blank;
- a True/False balance test across different session seeds; and
- an Agent-contract test proving that an Agent response cannot ignore the backend's required True/False index.

### Bundled knowledge database probe

The probe opened `data/knowledge/knowledge.db` and used the packaged Chapter 3 index.

1. Sixteen independent GPS quiz-session seeds generated both answer indices `{0, 1}`.
2. Five GPS flows were run with zero, one, two, three and four extra MCQ retries before Matching and Fill Blank. Every flow reached a grounded Fill Blank item.
3. The former page-78 failure was reproduced conceptually with the fact about conversion by an appropriate geodetic transformation. The corrected extractor formed a blank with answer `geodetic transformation`.
4. `linear algebra` returned zero relevant chunks, while `LBS` and `GPS` returned valid course-note chunks.

## Route regression added

`tests/test_http_integration.py::test_invalid_first_topic_does_not_lock_or_override_the_next_topic` verifies both:

- an invalid `linear algebra` attempt followed by a valid `GPS` attempt; and
- recovery from a simulated already-open v8.0.7 session whose stale `quiz_topic` is `linear algebra`.

The test also verifies that a valid topic becomes locked only after successful generation.

## Environment limitations

The complete Flask HTTP suite was not executed here because Flask and Werkzeug are not installed in this container. Live Coze was not called because deployment credentials are not included. MySQL/Docker, Windows batch files and browser interaction must still be checked in the deployment environment.

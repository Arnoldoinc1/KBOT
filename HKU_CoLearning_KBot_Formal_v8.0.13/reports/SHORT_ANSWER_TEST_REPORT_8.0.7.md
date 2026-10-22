# v8.0.7 Short Answer Quality Test Report

## Regression evidence

The bundled lecture PDF was parsed with the production document parser.

- Page 19 (`What’s is Location Base Service`) produced four required points: definition, Pull, Push and Tracking.
- Page 20 contains an open application list. The fallback did not select an arbitrary first four; it narrowed the question to the chosen `Receiving alerts` point.
- Page 22 (`Values of LBS`) produced all three explicit bullet relations: filter, pointer and area alarm.

## Grading checks

- Agent-declared score 100 with point credits 100, 100 and 0 was recalculated to 67.
- The complete server reference replaced a shortened `correct_answer` returned by the Agent.
- Incomplete reasoning ending with `According to the course material, an LBS` was rejected.
- The rejected Agent result entered the local fallback and returned complete reasoning plus one result for every key point.
- A response covering one of three required points did not receive full marks.
- The legacy no-key-point grading contract still accepted the previous single-score schema.

## Display and persistence checks

- Student JavaScript contains the post-submit `Key-point assessment` renderer.
- Detailed teacher feedback contains required key points, per-point credits/comments and the full reference answer.
- `key_points` is persisted in the existing JSON payload; no schema migration is needed.

## Automated results

- `PYTHONPATH=. python tests/test_short_answer_quality.py`: 11/11 passed.
- `PYTHONPATH=. python tests/test_feedback_and_kahoot.py`: 14/14 passed.
- `PYTHONPATH=. python tests/test_core.py`: 35/35 passed.
- `node --check student_app/static/app.js`: passed.
- `python -m compileall`: passed.

The container did not run live Coze or browser HTTP acceptance because deployment credentials and the full Flask runtime were not available.

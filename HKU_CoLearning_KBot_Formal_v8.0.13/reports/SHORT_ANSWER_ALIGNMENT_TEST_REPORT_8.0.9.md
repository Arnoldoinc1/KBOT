# v8.0.9 Short Answer Alignment Test Report

## Failure reproduced

Topic: `mobile communication`

Observed question: `According to the course notes, state and explain the 4 points about mobile communication.`

Observed rubric source: page 19, `What’s is Location Base Service`, containing the LBS definition plus Pull, Push and Tracking.

The old validator accepted the item because the rubric sentences were grounded somewhere in the PDF. It did not prove that those sentences answered the generated question.

## Executed regression checks

### Topic scope

Using the real 90-page Chapter 3 PDF:

- `mobile communication` detected the outline range pages 31–60.
- Every returned quiz chunk was within pages 31–60.
- Page 42 was available to the Short Answer selector.
- Page 19 was excluded.
- `LBS` detected pages 17–30.
- `linear algebra` returned no results.

### Five-stage route-style probe

The probe generated True/False, MCQ, Matching and Fill Blank first and recorded their coverage history. The Short Answer search then retained fact history while relaxing whole-page penalties.

Result:

- selected page: 42;
- selected section: `Network structure`;
- question: `According to the course notes, name and explain the 4 components listed under Network structure?`;
- key-point count: 4;
- expected labels: BSS, NSS, GPRS Core Network and OSS;
- citation pages: `{42}`;
- grounding and question/rubric alignment validation: passed.

### Cross-topic rejection

A valid LBS rubric was deliberately paired with the question `state and explain the 4 points about mobile communication`. Validation rejected it with `The Short Answer question does not match its course-note rubric.`

### Automated suite results

- `python -m compileall -q .`: passed.
- `python tests/test_core.py`: 41/41 passed.
- `python tests/test_short_answer_quality.py`: 11/11 passed.
- `python tests/test_feedback_and_kahoot.py`: 14/14 passed.
- `node --check student_app/static/app.js`: passed.

`tests/test_agents_and_migration.py` and the Flask HTTP suite were not executed because Werkzeug/Flask are unavailable in this container.

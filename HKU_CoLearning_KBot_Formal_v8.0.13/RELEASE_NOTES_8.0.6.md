# HKU Co-Learning KBot 8.0.6

## Scope

This is a narrow follow-up to v8.0.5. It does not alter quiz generation, grading thresholds, Agent routing, five-stage progression, Knowledge retrieval, authentication, database schema or answer privacy.

## Student-facing corrections

- My History no longer prints the complete teacher/audit feedback block. It shows question type, question, student answer, result, score, options and correct option/answer. Existing teacher feedback remains visible when present.
- The Quiz result card now includes an answer review with the original question, all options, the student's selection and the correct option before the automatic redirect.
- Generation source, grading source, citations and service metadata remain stored for teachers but are not exposed in the student review model.

## Kahoot MCQ export correction

The observed export contained True/False but skipped an MCQ whose correct option exceeded Kahoot's 75-character answer limit. v8.0.5 truncated options before comparing the saved correct-answer text. The full correct answer then no longer matched the truncated option, and the row was rejected even though `correct_index` was available.

v8.0.6 resolves the correct option against the complete stored options, tries the saved `correct_index` when text matching fails, and only then truncates answer text for the official XLSX template.

## Coze prompt packaging

The three platform Persona/System Prompts are included at `docs/COZE_AGENT_PROMPTS.md` and `docs/COZE_AGENT_PROMPTS.docx`. These files support reproducible Agent setup. They are not read by the Python runtime; the application continues to send its own dynamic per-request prompt.

## Verification

- Python source compilation.
- Dependency-light feedback, student-review and Kahoot tests.
- Regression test reproducing a long MCQ correct option and confirming it is exported with the saved correct index.
- Official Kahoot workbook save/reopen check.
- Final ZIP CRC and clean-extraction rerun.

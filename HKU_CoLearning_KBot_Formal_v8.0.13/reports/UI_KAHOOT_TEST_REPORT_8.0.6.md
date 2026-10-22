# v8.0.6 Student Review and Kahoot MCQ Regression Report

## Observed workbook

The uploaded `kahoot_quiz_template (2).xlsx` contained one exported True/False row and no MCQ row. The MCQ shown in the screenshots had a correct option longer than Kahoot's 75-character answer limit.

## Root cause

v8.0.5 cleaned and truncated MCQ options to 75 characters before resolving the saved `correct_answer`. The database kept the complete correct option text. When the complete text was compared with the shortened workbook option, it no longer matched. Because the exporter chose the non-empty text answer before the saved `correct_index`, it did not try the valid index fallback and skipped the MCQ.

## Correction

- Resolve the answer against complete stored options.
- Try `correct_answer`, then the saved `correct_index`, then detailed-feedback recovery.
- Apply the 75-character Kahoot limit only after the correct option number has been determined.

## Student UI correction

- Quiz submit response includes a student-safe review object containing question type, question, student answer, result, score, all visible options, selected option and correct option.
- Student History reconstructs the same view from persisted structured fields.
- Generation source, grading source, citations, source excerpts and the full audit feedback remain stored for Teacher App but are not rendered in Student History.

## Prompt packaging

The supplied prompt document is included as `docs/COZE_AGENT_PROMPTS.docx`. The equivalent Markdown file remains at `docs/COZE_AGENT_PROMPTS.md`.

## Executed checks

- `python -m compileall`: passed.
- `node --check student_app/static/app.js`: passed.
- All Student Jinja templates compiled: passed.
- `python -m unittest -v tests.test_feedback_and_kahoot`: 14/14 passed.
- Long-option MCQ regression: exported as row 10 with correct answer number 4.
- Corrected workbook inspected after save/reopen: both True/False and MCQ rows present.
- Full Flask/HTTP suite not run in this container because Werkzeug and Flask-SQLAlchemy are unavailable.

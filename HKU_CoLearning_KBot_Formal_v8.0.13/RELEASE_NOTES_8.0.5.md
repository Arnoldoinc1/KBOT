# HKU Co-Learning KBot 8.0.5 Release Notes

## Scope

This patch is based on v8.0.4 and changes only post-submission feedback persistence, feedback display formatting and Kahoot export recovery. It does not change quiz generation, grading decisions, the five-stage transition rules, answer privacy, Knowledge Service retrieval, Coze routing, authentication or database schema.

## Complete feedback records

After a student submits an answer, `student_qa_records.ai_feedback` now contains a self-contained record:

- question type and question text;
- student answer and result/score;
- True/False or MCQ options, selected option, correct option and remaining incorrect options;
- submitted and correct Matching pairs;
- Fill Blank correct answer;
- Short Answer reference answer;
- existing grading comment and explanation;
- source file, section, page and a bounded excerpt;
- generation and grading source labels.

The existing structured columns are retained. `options_or_pairs` now also keeps the post-submission canonical fields needed to reconstruct each type (`correct_index`, mappings, fill answer and short-answer reference). No migration is required because the column already stores JSON text.

## Kahoot export recovery

Kahoot export remains limited to True/False and MCQ because those are the question forms supported by the bundled official spreadsheet workflow.

The exporter now resolves data in this order:

1. options and correct answer from the existing structured record fields;
2. zero-based `correct_index` from the stored canonical payload;
3. options and correct option recovered from `[KBot Detailed Feedback v1]`;
4. the pre-existing legacy fallback that parses options embedded in the question text.

Malformed records are still skipped rather than causing an HTTP 500 response. Matching, Fill Blank and Short Answer are not silently converted into incompatible Kahoot rows.

## Display-only adjustment

Teacher record details and Student History preserve line breaks in the detailed feedback. No navigation or editing behavior was changed.

## Verification performed in this build environment

- Python compilation of the complete source tree: passed.
- Dedicated detailed-feedback and Kahoot recovery tests: 11/11 passed.
- Official `kahoot_template.xlsx` populated, saved and reopened with `openpyxl`: passed.
- ZIP CRC and clean-extraction verification: performed for the final archive.

The full Flask HTTP suite could not be rerun in this container because Flask, Flask-SQLAlchemy and Werkzeug are not installed and package download is unavailable. The original v8.0.4 test report remains in `reports/TEST_REPORT.md`; the new patch tests are dependency-light and are included in `tests/test_feedback_and_kahoot.py`.

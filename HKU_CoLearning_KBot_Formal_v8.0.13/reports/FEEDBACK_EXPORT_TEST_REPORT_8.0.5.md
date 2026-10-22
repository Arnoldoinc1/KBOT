# Feedback and Kahoot Export Patch Test Report — 8.0.5

## Changed code paths

- `common/feedback_builder.py`
- `student_app/blueprints/exercise.py`
- `teacher_app/kahoot_export.py`
- feedback line-break display in Teacher detail and Student History

## Test coverage

`python -m unittest -v tests.test_feedback_and_kahoot`

11 tests passed:

1. True/False feedback contains both options and the correct option.
2. MCQ feedback contains all four options, correct/selected markers and other options.
3. Matching feedback contains submitted and correct pairs.
4. Fill Blank feedback contains the canonical answer.
5. Short Answer feedback contains the reference answer.
6. MCQ export recovers from detailed feedback when structured options are absent.
7. Recovery accepts a combined correct-and-selected marker.
8. Structured fields remain the primary export source.
9. Stored zero-based `correct_index` is converted correctly for Kahoot.
10. True/False export recovers the correct option from detailed feedback.
11. Unsupported Matching, Fill Blank and Short Answer records are not forced into the Kahoot template.

## Environment limitation

The container lacks Flask, Flask-SQLAlchemy and Werkzeug, and cannot download packages. Therefore the complete HTTP integration suite was not rerun here. All Python files were compiled, and the modified export path was executed against the bundled official XLSX template using the installed `openpyxl` package.

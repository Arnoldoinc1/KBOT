# HKU Co-Learning KBot 8.0.4 Release Notes

## Student exercise corrections

The generation endpoint now returns a public quiz projection only. Correct indexes, matching mappings, fill answers, short-answer references, explanations and citations stay server-side until the attempt is submitted.

MCQ validation now rejects:

- the mechanical stem `Which course-note term correctly completes this statement?`;
- blank-completion MCQs;
- headings, generic isolated words and question fragments as options;
- unmatched PDF quotation marks;
- options not present in supplied course notes;
- a correct option that does not test the selected focus fact.

The local fallback now parses same-slide bullet groups and term-definition relationships before using a fact-based fallback. For the reported LBS page, it asks a normal function question about the area-alarm role instead of presenting `Use`, `Class discussions: What`, or a truncated search-result clause as options.

References are cleared when a new question is generated and rendered only after grading. The result card displays feedback, reference answer and explanation, followed by the verified file/section/page/excerpt cards. Automatic continuation waits eight seconds and an immediate Continue link is also available.

History now exposes **Back to Quiz** when a flow is unfinished and **Back to Exercise** after the flow is complete.

## Teacher Kahoot correction

The previous simplified CSV implementation was removed from `/export_kahoot`. The route now:

- bundles the original Kahoot `.xlsx` template;
- uses `openpyxl` to populate rows beginning at row 9;
- exports MCQ and True/False records;
- accepts old option formats and letter/index/text answer forms;
- skips malformed records instead of aborting the export;
- truncates Kahoot question/answer fields to template limits;
- logs internal errors and serves the blank template instead of exposing a generic Flask 500 page.

`openpyxl>=3.1,<4` is included in `requirements.txt` and checked by `CHECK_SETUP.bat`.

## Preserved behavior

- Original v6.2 Teacher login, registration and dashboard templates remain byte-for-byte unchanged.
- Student and Teacher HKU Moodle-style shells remain in place.
- One-topic sequential flow remains server-enforced.
- Existing accounts, history and named MySQL volume compatibility are unchanged.
- Knowledge Service remains API-only.

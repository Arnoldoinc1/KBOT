# HKU Co-Learning KBot 8.0.4 Test Report

Build date: 2026-07-22

## Scope of this correction

This release corrects four reported runtime/learning-flow defects:

1. malformed or fragmentary LBS MCQs;
2. course-note answers/references exposed before submission and weak post-submit feedback;
3. no direct History-to-Quiz navigation;
4. Teacher `Export Kahoot Template` returning an internal error.

It preserves the v8.0.3 authentication/database compatibility, original Teacher UI, Student HKU Moodle shell, one-topic sequential state machine and API-only Knowledge Service.

## Executed build-tree checks

### Compilation and static structure

Commands executed:

```text
python -m compileall -q .
node --check student_app/static/app.js
```

Results:

```text
Python files inspected by AST       44
Python parse errors                  0
Duplicate top-level definitions      0
Duplicate route+method definitions   0
app.view_functions overrides         0
FINAL PATCH/monkey-patch markers     0
JavaScript syntax                    PASS (Node v22.16.0)
Jinja templates parsed               11/11
```

### Original Teacher interface preservation

The three v8.0.4 Teacher templates still match the v6.2 originals byte-for-byte:

| File | SHA-256 |
|---|---|
| `teacher_app/templates/login.html` | `0488f9be8dea7d0f90ad82b57a80cca46d3ec172caa7a2b9435ed7649ac8ac25` |
| `teacher_app/templates/register.html` | `9ea002e7e12c117ed1c8bbb2e0ada564413f4150356ed64fab46a542422eeeea` |
| `teacher_app/templates/dashboard.html` | `42c6d936a290ebe73f41e5768d040502cdc7ea0d114e9b0bcb06ec342c2aab2a` |

### Core and real-PDF test suite

Command executed:

```text
python scripts/run_core_tests.py
```

Result:

```text
35 tests run
35 passed
0 failures
0 errors
```

Executed coverage includes:

- full, fenced, prefixed and truncated JSON recovery;
- Matching aliases and 0/1-based mappings;
- stream completion and persisted-message recovery;
- Quiz, Grading and Notes tasks routed to three Bot IDs;
- bounded Agent/network failure and local fallback;
- grading and Notes citation allowlists;
- real 90-page PDF parsing and persistent Knowledge repository;
- five-type cross-page diversity;
- rejection of the exact reported malformed Coze MCQ shape;
- grounded local LBS area-alarm MCQ generation;
- answer/citation privacy contract before submission;
- post-submit reference-answer/citation rendering contract;
- History Back-to-Quiz contract;
- official Kahoot template XLSX generation and reload;
- malformed Kahoot-record skipping;
- safe Kahoot export route/fallback contract;
- original Teacher template hashes and dashboard routes;
- v6.2 account/history schema migration preservation;
- server-enforced sequential quiz transitions;
- Windows launcher and direct-entrypoint static contracts.

## MCQ regression evidence

### Reported bad output now rejected

A mock Quiz Agent returned the reported form:

```text
Which course-note term correctly completes this statement? _____ ...
Options: Use / Class discussions: What / truncated clause fragments
```

`validate_grounding` rejected it and `generate_quiz` performed one grounded local fallback. The test confirmed that the visible MCQ:

- ends with a question mark;
- does not use the mechanical completion stem;
- contains four course-note-grounded options;
- does not contain `Use` or `Class discussions: What`.

### Real LBS page-22 fallback

Using the actual uploaded Chapter 3 PDF and the page-22 focus fact, the local fallback generated:

```text
Question:
Which function is associated with “Use as a definer/launcher for area alarm” in the course notes?

Correct option:
i.e. to launch a pre-defined activity (e.g. send a MSMS) with customer enters/leaves a certain area
```

The other options are course-note functions/statements and the MCQ passed grounding validation. The old fragment-completion question is no longer emitted.

### Sequential LBS MCQ example

In a normal LBS sequence after True/False, the selected page-26 fact produced:

```text
Which item is listed under “Business Model (Willingness to pay)” in the course notes?
```

The correct option was `Enterprise users are more willing to pay a higher fee`; distractors were sibling interoperability items from the same slide rather than malformed headings.

## Answer/reference privacy and feedback

Static/API contract checks confirmed:

- generation returns `_public_quiz(generated.quiz)`;
- pre-submit payloads omit `correct_index`, `correct_mapping`, `answer`, `reference`, `explanation` and `citations`;
- the complete draft remains server-side in `quiz_sessions.current_quiz_json`;
- the browser clears old citations when generating a question;
- after submission, the result displays feedback, reference answer and explanation;
- only the submit response renders file, section, page and excerpt cards;
- the continuation delay is eight seconds and an immediate Continue link is available.

The HTTP integration test was updated to read answer keys from the server-side test database rather than from the public browser payload.

## History navigation

The History blueprint and templates were checked for:

- **Back to Quiz** when `chapter_id` exists and the flow is unfinished;
- return to the server-authoritative current question type;
- **Back to Exercise** when no active unfinished flow exists;
- a visible page button and matching header navigation link.

## Kahoot XLSX export

The bundled `teacher_app/kahoot_template.xlsx` was loaded with `openpyxl`. A valid MCQ and a malformed legacy record were supplied to the exporter.

Results:

```text
Valid questions written             1
Malformed records skipped           1
Official header retained            PASS
Question written at row 9            PASS
Correct answer index written         2
Saved BytesIO reopened by openpyxl   PASS
```

The Teacher route statically confirms:

- it calls `build_kahoot_xlsx`;
- it downloads `kahoot_quiz_template.xlsx` with the XLSX MIME type;
- it logs generation failures;
- it serves the bundled blank template rather than returning a generic Flask 500 page;
- `openpyxl>=3.1,<4` is present in `requirements.txt` and startup checks.

## Packaged Knowledge database

The bundled Knowledge database was rebuilt from the real PDF using the stricter parser rather than carrying the earlier malformed term pairs.

```text
PRAGMA integrity_check   ok
documents                1
pages                    90
chunks                   86
facts                    268
term_pairs               53
bad reported term forms  0
schema_version            3
```

### GPS diversity trace

| Type | Page | Knowledge key | Fact key | Visible question/concept |
|---|---:|---|---|---|
| True/False | 62 | `K-475ea910a491186f9c22e1b9` | `F-04795ec79b32be3454899d45` | GPS satellite-based navigation capability |
| MCQ | 79 | `K-6f5cd9b61f35285e134be144` | `F-a559cc0a5021517ba5c552d3` | Multipath definition |
| Matching | 63 | `K-f17dc0f2cb0a572d73b17591` | `F-1b28a9c218a08c3f63f8fa89` | GPS receiver/system context; pairs from GPS component pages |
| Fill Blank | 85 | `K-295a5d6623829e953c5c13c8` | `F-b7fc77f9f4891a9c9bd8d82c` | BeiDou interoperability with GPS/GNSS |
| Short Answer | 72 | `K-f700df353a90b599a7802ce3` | `F-c07343ecbc910c0209aef455` | GPS satellites and orbital spares |

Five question types used five different pages, knowledge keys and fact keys.

## Checks not executed in this build environment

### Flask HTTP integration

The build environment lacks Flask, Flask-Login, Flask-SQLAlchemy and Werkzeug. The HTTP tests compile, but were not executed. No claim of a live three-process Flask pass is made.

### Live Docker/MySQL

Docker is unavailable in this environment. Compose/database compatibility was statically checked only. No live MySQL or Docker command was executed.

### Windows batch execution

The build host has no `cmd.exe`. `.bat` scripts were inspected but not double-clicked or run on Windows.

### Live Coze API

No deployment Token/Bot IDs were used. Coze transport and three-Agent routing were mock-tested only.

## Deployment-machine acceptance checks

1. Copy the working root `.env` into the v8.0.4 root.
2. If Docker MySQL is stopped and `DATABASE_URL` uses it, run `docker compose up -d mysql`; otherwise do not create another MySQL container.
3. Run `CHECK_SETUP.bat`; confirm `openpyxl` and the Kahoot template are present.
4. Run `CHECK_ACCOUNTS.bat`; confirm expected users.
5. Run `START_ALL.bat` and press `Ctrl+F5` in both applications.
6. Generate an LBS MCQ and confirm no blank-completion stem or fragment options appear.
7. Confirm no course-note reference appears before Submit.
8. Submit and confirm reference answer, explanation, source filename, section, page and excerpt appear.
9. Open My History during an unfinished flow and use Back to Quiz.
10. In Teacher App, click Export Kahoot Template and open the downloaded `.xlsx` file.
11. Execute the full live three-Agent and MySQL acceptance sequence described in the README.

## Archive regression

A release-candidate archive was created after removing `.env`, `__pycache__` and `.pyc` files.

```text
candidate ZIP entries                  99
candidate ZIP CRC/integrity            PASS
real .env entries                      0
cache/pyc entries                      0
clean extraction Python compilation   PASS
clean extraction JavaScript syntax    PASS
clean extraction core suite           35/35 PASS
clean extraction Knowledge integrity  ok
clean extraction Kahoot XLSX reload   PASS
```

After this report and final build metadata were frozen, the final named ZIP was rebuilt and subjected to the same ZIP-integrity, clean-extraction compilation, JavaScript, 35-test, Knowledge SQLite and Kahoot XLSX regression sequence.

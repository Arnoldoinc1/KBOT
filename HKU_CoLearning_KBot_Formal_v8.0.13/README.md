# HKU Co-Learning KBot 8.0.13

HKU Co-Learning KBot runs as three independent services:

| Service | Default address | Purpose |
|---|---|---|
| Knowledge Service | `http://127.0.0.1:5100` | API-only persistent course-file parsing, indexing and retrieval |
| Teacher App | `http://127.0.0.1:5000` | Original HKU Moodle-style Teacher UI, course-material management, records, feedback and export |
| Student App | `http://127.0.0.1:8000` | HKU Moodle-style registration/login, Session Setup, sequential exercises, Notes QA and History |

The Knowledge Service is not a third user-facing website. Teachers manage files through Teacher App; Student App reads the independent service. Teacher App can be stopped without removing already uploaded course knowledge.

## 8.0.13 knowledge-bearing Fill Blank validation

- Fill Blank answers must now be knowledge-bearing course concepts, components, measurements, named roles or crucial properties. Articles, prepositions, conjunctions, pronouns, auxiliary verbs and other function words such as `for`, `to`, `the`, `of`, `in`, `and`, `is` and `only` are rejected even when they occur verbatim in the notes.
- The backend restores the answer into the blank and verifies that the completed sentence matches both the supplied notes and the selected focus fact. A grammatically valid but educationally meaningless Agent item therefore falls back to deterministic local construction.
- The local constructor ranks candidates by educational value. In the reported GPS sentence it selects `receiver`, producing `requires a _____ only`, rather than blanking `For` or merely removing the broad topic name.
- The recommended final routing remains `COZE_QUIZ_TYPES=mcq,short_answer`, so Fill Blank is deterministic in normal deployment. The stricter validator still protects installations that set `COZE_QUIZ_TYPES=all`.
- The Quiz Agent platform prompt has been updated in both Markdown and DOCX. No database migration is required.

See `RELEASE_NOTES_8.0.13.md` and `reports/FILL_BLANK_QUALITY_TEST_REPORT_8.0.13.md`.

## 8.0.12 production resilience and Teacher hybrid search

- Recommended final routing is `COZE_QUIZ_TYPES=mcq,short_answer`: the language-heavy MCQ and Short Answer generation stages use the Quiz Agent; True/False, Matching and Fill Blank use faster deterministic grounded constructors. All five types retain local recovery.
- Generate is idempotent while an unsubmitted draft exists. Duplicate tabs/requests share one atomic generation job and receive the same saved question.
- A second generation pass expands retrieval, permits evidence reuse and disables another Agent call. If a supported topic still cannot produce a safe type, the learner can use an audited server-authorised skip instead of becoming stuck.
- Submission has an emergency local-grading boundary, so an Agent/parser failure cannot leave an ungradeable active draft forever.
- Per-Agent timeouts and a circuit breaker bound repeated Coze outages.
- Teacher record search is restored from SQL keyword-only matching to hybrid exact keyword + BM25 + TF-IDF sparse-vector + character n-gram + acronym expansion. A local SentenceTransformer model is optional for dense semantics.
- Use `.env.production.example` for deployment. Production preflight rejects SQLite, placeholder keys, public teacher registration and legacy default-teacher seeding.

See `RELEASE_NOTES_8.0.12.md` and `reports/RESILIENCE_AND_HYBRID_SEARCH_TEST_REPORT_8.0.12.md`.

## 8.0.11 faster five-stage generation and Short Answer grading correction

- The default quiz-generation policy is now `COZE_QUIZ_TYPES=mcq`. MCQ still demonstrates the external Quiz Agent, while True/False, Matching, Fill Blank and Short Answer use deterministic constructors grounded in the retrieved course notes. This removes four avoidable Coze waits from a normal five-stage demo.
- Use `COZE_QUIZ_TYPES=all` to retain the old all-Agent generation behaviour, a comma-separated subset to choose specific types, or `COZE_QUIZ_TYPES=none` for the fastest fully local quiz generation while keeping the configured Grading and Notes Agents available.
- Repeated browser auto-generation for an already active draft now reuses the same saved question instead of starting a duplicate Agent request. Retrieval limits and prompt evidence are also smaller and type-specific.
- Student logs now include a request ID, generation start/reuse/success/rejection, generation source, per-stage timing, and Short Answer grading timing/source.
- Static CSS/JavaScript URLs use the `8.0.11` cache version so an upgrade cannot silently keep the old `8.0.5` browser assets.
- The gyroscope slide is now represented correctly as three principles—Spinning Motion, Conservation of Angular Momentum and Precession—plus a separate applications bullet. The applications line is no longer mislabelled as a fourth principle.
- Short Answer grading uses only `0`, `50` or `100` per rubric point. A backend lexical guardrail upgrades obvious Agent under-marking when the learner clearly states the required course-note point; it never lowers a semantic Agent judgment.
- Republish the AI Grading Agent with the v8.0.11 prompt for consistent per-point output. The backend guardrail still protects the reported gyroscope case before republishing. No database migration is required.

See `RELEASE_NOTES_8.0.11.md` and `reports/PERFORMANCE_AND_SHORT_ANSWER_GRADING_TEST_REPORT_8.0.11.md`.

## 8.0.10 no-`.env`, speed and GPS True/False correction

- The project can start without `.env` because the ZIP includes a local SQLite application database, a persistent Knowledge index, matching local service keys and deterministic fallbacks. This is an offline/local demo, not proof that Coze is active.
- `COZE_ENABLED` now controls external calls. In the default `auto` mode, no root `.env` means local fallback mode, even if stale `COZE_*` variables exist in Windows. Set `COZE_ENABLED=true` explicitly for an environment-only deployment.
- Startup diagnostics identify whether Agent configuration came from the root `.env`, process environment, or defaults without printing secrets.
- GPS True/False no longer selects fragments such as `Based on the CDMA principle.` and no longer creates the invalid meta-statement `The course notes do not state that...`. False questions are limited to one bounded numeric, negation or antonym change.
- Student generation logs now show retrieval, term, generation and total timings together with the generation source.
- No database migration is required.

See `RELEASE_NOTES_8.0.10.md` and `reports/ENV_AND_TRUE_FALSE_REGRESSION_TEST_REPORT_8.0.10.md`.

## Coze Agent prompts included in this ZIP

The three fixed platform Persona/System Prompts are included in both:

- `docs/COZE_AGENT_PROMPTS.md`
- `docs/COZE_AGENT_PROMPTS.docx`

The Python application also builds a separate dynamic prompt for each request. The files above are required when creating or reconfiguring the three Agents in Coze, but the running application does not read the DOCX at runtime. When upgrading from v8.0.7, republish the Quiz Agent with the v8.0.8 prompt so it follows the runtime True/False target; otherwise the backend will reject a mismatched Agent item and use its grounded local fallback.

## 8.0.9 Short Answer question/rubric alignment correction

- Topic-mode quiz retrieval now uses a reliable course-outline heading as a page-range boundary when one is available. In the bundled deck, `mobile communication` is limited to pages 31–60 instead of drifting to the earlier LBS section because of the word `mobile`.
- Short Answer has its own focus selector that prefers one complete two-to-four-item labelled list from a single section.
- The displayed question, private key points, reference answer and explanation must now describe the same section/list. A vague or cross-topic Coze question is replaced or rejected even when its answer sentences individually occur somewhere in the notes.
- For the reported example, the corrected question uses the four GSM `Network structure` components on page 42. Page 19 remains usable for a separate explicit question that asks for the LBS definition and the Pull, Push and Tracking types.
- No database migration and no Coze platform-prompt republish are required. The runtime dynamic prompt and server-side validator enforce the correction.

See `RELEASE_NOTES_8.0.9.md` and `reports/SHORT_ANSWER_ALIGNMENT_TEST_REPORT_8.0.9.md`.

## 8.0.8 Demo reliability corrections

- A failed out-of-scope topic is no longer written into the quiz session. The latest topic remains editable until retrieval and question validation succeed, including recovery from an already-open v8.0.7 session that contains a stale invalid topic.
- Fill Blank fallback no longer depends on one selected fact. If that fact has no safe one-to-three-word answer, the backend searches other topic-relevant facts and recognises lower-case technical noun phrases such as `geodetic transformation`.
- True/False is no longer hard-coded or prompt-biased toward True. The backend deterministically assigns either `correct_index: 0` or `correct_index: 1` per quiz session, constructs a bounded false variant when required, and rejects an Agent response that ignores the target.
- The Quiz Generation Coze platform prompt must be replaced with the v8.0.8 version and republished. AI Grading and Notes prompts keep their previous contracts.
- No database migration is required. Existing accounts, history, five-stage progression, Notes QA, teacher review and Kahoot export remain compatible.

See `RELEASE_NOTES_8.0.8.md` and `reports/DEMO_REGRESSION_TEST_REPORT_8.0.8.md`.

## 8.0.7 Short Answer completeness and rubric correction

- Short Answer now stores an explicit private list of required course-note key points.
- Small finite bullet groups are kept complete; the supplied page-19 LBS slide uses definition, Pull, Push and Tracking as four separate marking points.
- Long open lists are not cut to an arbitrary first four; the fallback asks a narrower question instead.
- The Grading Agent must assess every required point, and the backend recalculates the score from the per-point credits.
- Incomplete reasoning or incomplete point comments are rejected and replaced by the safe local fallback.
- The post-submit screen shows a Key-point assessment, full reference answer, complete explanation and source cards.
- The Quiz and Grading Coze platform prompts must be replaced with the v8.0.7 versions and republished.
- Other question types, flow control, Notes QA, database schema and Kahoot export are unchanged.

See `RELEASE_NOTES_8.0.7.md` and `reports/SHORT_ANSWER_TEST_REPORT_8.0.7.md`.

## Previous 8.0.6 student review and Kahoot MCQ export correction

- Student History now shows a concise answer record instead of the full internal audit feedback.
- The post-submit Quiz screen shows the question, all options, the student selection and the correct option.
- Teacher-side audit feedback remains complete and unchanged for review and recovery.
- Kahoot export now resolves the correct MCQ index before applying Kahoot's 75-character answer limit, fixing long-option MCQs that were previously skipped.
- The three Coze Agent prompts are included as both Markdown and DOCX.

See `RELEASE_NOTES_8.0.6.md` for the exact scope and verification.

## Previous 8.0.5 detailed feedback and Kahoot recovery fix

- Saves a complete post-submission feedback record for all five question types.
- MCQ and True/False feedback includes the question, every option, the student selection, the correct option, the remaining incorrect options, explanation and course-note references.
- Matching feedback records both submitted and correct pairs. Fill Blank and Short Answer retain the canonical answer/reference answer.
- Persists the canonical post-submission question payload, including `correct_index`, mappings, fill answer and short-answer reference, in the existing `options_or_pairs` field.
- Keeps Kahoot export limited to True/False and MCQ, as required by the bundled official spreadsheet template.
- Kahoot export uses structured fields first, then recovers options and the correct answer from detailed feedback when a migrated or legacy record is incomplete.
- Preserves line breaks in Teacher record details and Student History so the expanded feedback remains readable.

See `RELEASE_NOTES_8.0.5.md` for the exact scope and verification.

## Previous 8.0.4 corrections

- Rejects malformed Coze MCQs such as sentence-completion stems with headings or fragments as options.
- Rebuilds local MCQ fallback around real course-note concepts, bullet relationships and complete facts.
- Keeps `correct_index`, mappings, answers, explanations and citations on the server until submission.
- Shows the reference answer, explanation, file, section, page and excerpt only after grading.
- Keeps post-answer feedback visible for eight seconds and provides an immediate Continue link.
- Adds **Back to Quiz** to History while a sequential flow is active.
- Restores real Kahoot `.xlsx` generation using the bundled official template and `openpyxl`.
- Skips malformed legacy records during Kahoot export and serves a safe blank template instead of a generic 500 page if generation fails.
- Retains every v8.0.3 account, original Teacher UI and server-enforced quiz-flow compatibility correction.

The earlier changes remain documented in `RELEASE_NOTES_8.0.4.md`.

## Root `.env`

All services read one `.env` beside `START_ALL.bat`. Use `.env.example` for local development or `.env.production.example` as the final deployment baseline. The required Coze variables are:

```dotenv
COZE_ENABLED=true
COZE_API_BASE=https://api.coze.com
COZE_TOKEN=
COZE_QUIZ_BOT_ID=
COZE_GRADING_BOT_ID=
COZE_NOTES_BOT_ID=
COZE_QUIZ_TYPES=mcq,short_answer
COZE_TIMEOUT=25
COZE_QUIZ_TIMEOUT=25
COZE_GRADING_TIMEOUT=30
COZE_NOTES_TIMEOUT=30
COZE_CIRCUIT_FAILURES=3
COZE_CIRCUIT_COOLDOWN=60
```

The three Agents may share one Token. Their platform Knowledge Auto-call and Memory must remain off because references are supplied by the application.

## Windows startup

1. Extract this complete ZIP into a new folder.
2. Copy the working `.env` from v8.0.3 into the new root.
3. Run `CHECK_SETUP.bat`.
4. Run `CHECK_ACCOUNTS.bat` if using the shared MySQL account database.
5. Run `START_ALL.bat`.
6. Press `Ctrl+F5` once in Teacher and Student pages after upgrading.

`START_ALL.bat` starts the three Python services. It does not create or start a stopped Docker container.

### What `docker compose up -d mysql` does

This command starts only the `mysql` service declared in `docker-compose.yml` and leaves it running in the background (`-d`). It is needed only when:

- `DATABASE_URL` points to Docker MySQL; and
- that MySQL container is not already running.

It is not necessary before every KBot start. If `START_ALL.bat` already works and `CHECK_ACCOUNTS.bat` shows the expected MySQL accounts, the container is already available. If `DATABASE_URL` is SQLite, Docker MySQL is not involved.

Never use `docker compose down -v` when old accounts/history must be preserved because `-v` removes named volumes.

## Exercise behavior

The Student server stores one topic and enforces:

```text
True/False -> MCQ -> Matching -> Fill Blank -> Short Answer
```

A correct answer advances. An incorrect answer remains on the same type. The progress display is not a navigation control, and edited URLs/API payloads cannot skip a type.

Before submission, the browser receives only visible question fields. The answer key and citations remain in `quiz_sessions.current_quiz_json`. After submission, the response includes feedback, reference answer, explanation and verified Knowledge Service citations.

## Kahoot export

Teacher App `/export_kahoot` reads MCQ and True/False records from the shared database, resolves old/new answer encodings, writes the bundled `teacher_app/kahoot_template.xlsx`, and downloads `kahoot_quiz_template.xlsx`.

If the setup check reports `openpyxl` missing, run:

```bat
INSTALL_WINDOWS.bat
```

## Useful commands

```bat
CHECK_SETUP.bat
CHECK_ACCOUNTS.bat
START_ALL.bat
```

Manual MySQL start only when required:

```bat
docker compose up -d mysql
```

Direct service startup from the project root:

```bat
D:\Python3.11.9\python.exe -m knowledge_service.run
D:\Python3.11.9\python.exe -m teacher_app.run
D:\Python3.11.9\python.exe -m student_app.run
```

## Tests

Core and real-PDF tests:

```bash
python scripts/run_core_tests.py
```

Full integration tests, when development dependencies are installed:

```bash
pytest -q
```

The final test report distinguishes executed core/real-PDF/XLSX checks from unexecuted live Windows, Docker/MySQL, Flask HTTP and Coze tests.

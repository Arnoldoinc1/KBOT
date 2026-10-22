# HKU Co-Learning KBot v8.0.12 Release Notes

## Production routing

The recommended final routing is:

- True/False: deterministic course-grounded constructor;
- MCQ: Quiz Agent, with deterministic local recovery;
- Matching: deterministic term-pair constructor;
- Fill Blank: deterministic fact/term constructor;
- Short Answer generation: Quiz Agent, with section-alignment validation and deterministic local recovery;
- Short Answer grading: Grading Agent, with local semantic and emergency fallbacks;
- Notes QA: Notes Agent, with course-grounded local fallback.

Set `COZE_QUIZ_TYPES=mcq,short_answer`. This keeps the language-heavy tasks on the Quiz Agent without making every objective stage wait for an external request.

## Active-question idempotency and concurrency

- Clicking **Generate** again while a valid unsubmitted question exists returns that same server-side draft.
- Multiple tabs or duplicate auto-generation requests share an atomic generation marker. One request owns generation; the others receive HTTP 202 and poll for the same saved result.
- A stale marker can be reclaimed after `GENERATION_LOCK_TTL` so a terminated worker cannot trap the session permanently.

## Exhaustion and anti-stall recovery

- Primary generation uses normal diversity exclusions and the configured Agent routing.
- If it cannot create a valid item, a second pass expands retrieval, permits reuse of previously covered course evidence, and uses the deterministic local constructor without another Agent call.
- If course evidence exists but both passes fail, the UI offers **Retry generation** and an audited **Skip unavailable type** action. The server, not the browser, advances the fixed sequence.
- Out-of-scope topics cannot be skipped as if they were course content; the topic input remains editable.
- Unexpected grading failures receive a final deterministic local grading attempt. A corrupted legacy draft is cleared and becomes retryable/skippable rather than remaining active forever.

New additive Quiz Session fields record generation failures and skipped stages. Existing SQLite/MySQL accounts and learning records are preserved by the compatibility migration.

## Coze latency and outage control

- Production defaults use per-Agent timeouts: Quiz 25 seconds, Grading 30 seconds and Notes 30 seconds.
- After three consecutive transport failures, a per-Agent circuit breaker opens for 60 seconds. During the cooldown, requests immediately use the existing local fallback instead of repeatedly waiting for a failing external service.
- Student `/health` reports Agent configuration and circuit state.

## Teacher record search restoration

The Teacher `/search` endpoint no longer performs SQL substring matching only. It now combines:

- exact and substring keyword matching;
- BM25 token relevance;
- TF-IDF sparse-vector cosine similarity;
- character n-gram similarity for minor spelling variation;
- acronym/long-form expansion such as GPS ↔ Global Positioning System and LBS ↔ Location-Based Service.

An optional local SentenceTransformer model can add dense semantic similarity. Install `requirements-semantic.txt` and set `TEACHER_SEMANTIC_MODEL_PATH` to an existing local model directory. The application never downloads a model during a web request.

## Deployment safeguards

- `.env.production.example` contains the recommended routing, MySQL, Agent timeouts, circuit breaker and secure account settings.
- `KBOT_ENV=production` makes startup preflight reject SQLite, placeholder secrets, public teacher registration and legacy default-teacher seeding.
- Production mode enables secure session cookies by default.

## Verification completed

- Python `compileall`: passed for common, Knowledge, Student, Teacher, scripts and tests.
- Student JavaScript and Teacher inline JavaScript: passed `node --check`.
- Core regression suite: 48/48 passed.
- Short Answer, feedback and Kahoot suites: 27/27 passed.
- Real 90-page course PDF exhaustion probe: all five types generated grounded local-recovery questions even when all retrieved facts/chunks/pages were marked used.
- Hybrid search probes passed for keywords, acronym/long-form equivalence, paraphrases, student names and a spelling error.
- Circuit-breaker probe confirmed that an open circuit makes no additional network call.

Full Flask HTTP, live Coze, Windows CMD and live MySQL/Docker execution require the deployment environment and credentials and were not executed in the build container.

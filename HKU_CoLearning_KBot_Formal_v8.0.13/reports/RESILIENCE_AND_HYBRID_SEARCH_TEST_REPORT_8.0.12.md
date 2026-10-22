# v8.0.12 Resilience and Hybrid Search Test Report

## Scope

This revision tested the boundaries most likely to interrupt a live five-stage session: duplicate generation, simultaneous requests, depleted diversity history, malformed Agent output, external-service failures, grading failure and teacher search regression.

## Results

### Repeated and concurrent Generate

A valid `current_quiz_json` draft is idempotent: repeated Generate calls return its public projection and quiz ID. An atomic temporary marker prevents two workers/tabs from paying for or overwriting two Agent results. Polling requests receive the saved result. Stale ownership expires after a configured TTL.

### Evidence exhaustion

The production path first attempts normal diversity-aware generation. The recovery path clears exclusion history for retrieval, expands the candidate count and forces the grounded local constructor. A real-PDF probe pre-marked every retrieved GPS knowledge key, chunk, page and fact as used. True/False, MCQ, Matching, Fill Blank and Short Answer still generated and passed grounding validation.

When a type is structurally impossible even after recovery, the server records the reason and permits an explicit audited skip. The browser cannot invoke skip before recovery, while an active question exists, during generation, or for an out-of-scope topic.

### External Agent failures

Per-Agent timeout configuration bounds waiting. A circuit-breaker test used a session that always raised a network error. After the configured threshold, the next request was rejected locally and the network-call counter did not increase. Existing generation, grading and Notes functions then use their local fallback paths.

### Grading failures

The normal Short Answer grader already falls back after Coze transport or schema errors. v8.0.12 adds a final emergency boundary around submission. An unexpected exception invokes deterministic local grading; if the saved draft itself is corrupted, it is cleared and the learner receives retry/skip controls instead of a permanently active ungradeable question.

### Teacher search

The previous `/search` route used SQL `ILIKE` only. The revised route ranked record objects with exact keyword, BM25, TF-IDF sparse vectors, character n-grams and acronym expansion. Tests returned the intended records for `GPS`, `global positioning system`, `satellite navigation`, `locatoin based service`, and a student name, while rejecting an unrelated cafeteria query. Optional dense similarity is enabled only from a local model path.

## Automated checks

- Core: 48/48 passed.
- Short Answer/Feedback/Kahoot: 27/27 passed.
- Python compilation: passed.
- Student and Teacher JavaScript syntax: passed.

## Environment boundary

The build container did not contain Flask/Werkzeug runtime packages and had no live Coze credentials, Windows CMD, browser or MySQL/Docker service. Therefore full HTTP concurrency, live Agent latency and Windows service-launch acceptance remain deployment checks rather than claimed build-container results.

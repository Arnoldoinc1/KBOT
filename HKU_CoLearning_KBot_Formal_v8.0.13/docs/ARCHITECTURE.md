# Architecture decisions

## Service boundaries

Knowledge Service owns course files and derived knowledge. It uses its own SQLite database even when Teacher and Student share MySQL. Teacher App uses only Knowledge admin APIs. Student App uses only read/search APIs. No route imports or process-global Chroma object crosses a service boundary.

The application database owns identities, quiz sessions, exercise submissions, Notes QA history, AI feedback, source metadata, and teacher feedback. Teacher and Student use the same `DATABASE_URL`.

## Request paths

Exercise generation: Student authentication → Knowledge multi-candidate search → session-aware focus selection → Quiz Agent once → strict parse/grounding validation → local grounded fallback when necessary → server-side draft and coverage history.

Exercise grading: server-side draft → objective local grader or separate Grading Agent → score/citation validation → conservative local fallback → shared record.

Notes QA: Student question → Knowledge multi-candidate search → separate Notes Agent → allowed-reference validation → evidence-only local summary/not-found fallback → shared history with backend citations.

## Trust boundaries

- Course text is untrusted data in dynamic prompts.
- Coze output is untrusted input and must be parsed, normalized, grounded, and citation-filtered.
- Client-submitted answers never contain the correct key; the current question draft is stored server-side.
- The Student service never receives `KNOWLEDGE_ADMIN_KEY`.
- Platform Memory and platform Knowledge are disabled; persisted chat messages exist only to recover the current API response.

## Local fallbacks

Fallbacks do not invent course facts. True/False uses a stored fact. Fill Blank removes an exact stored term. MCQ requires four terms present in retrieved notes. Matching requires same-category stored term-definition pairs. Short Answer uses a stored fact as its reference. Notes selects relevant sentences from retrieved excerpts or returns the explicit not-found message.


## Authentication and legacy data

The `users` table remains shared. v6.2 Werkzeug password hashes are not rewritten. The compatibility migration only adds missing fields and backfills new metadata. Docker Compose explicitly attaches `edu_qa_mysql_data`, while `CHECK_ACCOUNTS.bat` confirms which account rows are visible through the configured `DATABASE_URL`.

Teacher and Student use separate cookie names, preventing cross-port session collisions on the same hostname.

## Server-enforced exercise flow

The browser does not select question types. The server stores the current type and one topic in the signed Student session and stores the current question draft in `quiz_sessions`. Generation requests for a type other than the active type are rejected. A correct answer advances one step; an incorrect answer keeps the same step. Editing the URL redirects back to the active type. The progress display is non-interactive.

## Knowledge Service presentation

Knowledge Service is API-only. `/` and `/health` are JSON status endpoints rather than a separate user application. Teacher App owns the visible upload/delete controls; Student App receives only the read key.

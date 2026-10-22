HKU CO-LEARNING KBOT 8.0.13 — WINDOWS START
============================================================

1. Extract this COMPLETE ZIP into a new folder.
2. Choose the runtime mode:
   - Final production routing: start from .env.production.example and use
     COZE_ENABLED=true with COZE_QUIZ_TYPES=mcq,short_answer.
   - Local development: copy .env.example to .env.
   - All quiz types through the Quiz Agent: set COZE_QUIZ_TYPES=all (slower and
     less resilient; not the recommended production policy).
   - Fully local troubleshooting: set COZE_ENABLED=false.
3. Run CHECK_SETUP.bat and read the Coze/runtime source lines.
4. Run CHECK_ACCOUNTS.bat when using the shared MySQL database.
5. Run START_ALL.bat.
6. Press Ctrl+F5 once in both browser applications.

DOCKER MYSQL
------------
START_ALL.bat starts Knowledge, Teacher and Student Python services. It does
not start a stopped Docker container.

Run this only when DATABASE_URL uses Docker MySQL and MySQL is not running:

  docker compose up -d mysql

The command starts only MySQL in the background. It is not needed every time
when the container is already running. Never run docker compose down -v when
old accounts/history must be retained.

OPEN:
  Teacher App:  http://127.0.0.1:5000/
  Student App:  http://127.0.0.1:8000/
  Knowledge:    http://127.0.0.1:5100/health

STUDENT EXERCISE
----------------
Enter one topic. The server enforces:

  True/False -> MCQ -> Matching -> Fill Blank -> Short Answer

Answers and course-note references are hidden before submission. After
submission, the page shows feedback, the reference answer, explanation,
source file, section, page and excerpt. History has Back to Quiz while the
flow remains active.

KAHOOT
------
Export Kahoot Template now downloads a real .xlsx file from the bundled
Kahoot template. CHECK_SETUP.bat verifies openpyxl and the template. If a
package is missing, run INSTALL_WINDOWS.bat once.


NO .ENV BEHAVIOUR
-----------------
Without a root .env, the bundled SQLite databases, Knowledge index and local
fallbacks allow the system to start. START_ALL.bat now reports this as local
fallback mode. It does not mean the three Coze Agents are active.


8.0.13 FILL BLANK QUALITY + 8.0.12 RESILIENCE / SEARCH
---------------------------------
The startup check prints Agent routing, timeouts, circuit-breaker settings and
the Teacher record-search backend. Duplicate Generate clicks reuse one draft.
Generation exhaustion triggers local evidence reuse and then an audited Skip
option, rather than trapping the learner. Teacher record search combines
keywords and vector ranking. Fill Blank now rejects grammar/function-word answers and verifies that the
restored sentence tests the selected course fact. Press Ctrl+F5 after upgrading
so the 8.0.13 static assets are loaded.

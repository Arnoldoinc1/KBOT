HKU Co-Learning KBot — V5 Exercise Quality Patch
==================================================
Apply to: your currently working V4 installation (the V4 parser and
pdfplumber dependency must already be installed).  The V5 cumulative
patch is also supplied for users starting with the original matching
project version; it includes all V2/V3/V4 and V5 edited files.

IMPORTANT: Back up the current project before overwriting.  Do not
delete or replace .env, a database, vector indexes or teacher history.

V5 code changes
---------------
1. common/quiz_engine.py
  * For an explicit definition topic, prefer the requested definition even
    after another exercise has used it.  Do not switch a lamp-definition
    Short Answer into a point-source question just to avoid repetition.
  * Split a clearly expressed pair of independent characteristics into
    two marking points (e.g. "point source is infinitely small" and "emits
    light evenly in all directions").  Do not blindly split all "and"s.
  * Combine duplicate same-page citations for the two traits.
  * Reject Fill Blank sources drawn from numbered PPT summaries/outlines,
    and generic answers such as "Making" or "possible". Prefer supported
    technical concepts, e.g. "luminaire" or "fluorescent coatings".
  * For Matching, prefer a trusted labelled glossary such as GPS Components.
    Otherwise build distinct source-grounded pairs from the requested
    topic's nearby pages, refusing to invent missing definitions.  Avoid
    treating lists of four terms as one concept. Bayes-risk examples can
    use conditional risk / loss function / minimum error-rate classifier.
  * Improve the awkward local MCQ stem for "In building services, the lamp".
2. knowledge_service/repository.py and knowledge_service/app.py
  * New optional neighbor_pages parameter (default ZERO) to retrieve a
    small set of adjacent pages only when Matching requires it.
    Existing PDF parser, embeddings and ordinary Q&A retrieval unchanged.
3. common/knowledge_client.py, student_app/blueprints/exercise.py
  * Request nearest-page support only for Matching. Normal search for
    every other exercise and Notes Q&A stays unchanged.
4. tests/test_core.py
  * Seven V5 regression tests for the reported errors, rubric partial
    credit, topic alignment, glossary fallback and API compatibility.

Coze prompts
------------
NO manual Coze edits or republishing needed for this patch.
Quiz Agent uses the existing platform prompt; only the dynamic request
and backend topic validation change. The existing Grading Agent already
supports per-key-point partial credit. Old recorded grades are unchanged;
only newly generated questions use the corrected rubrics.

Windows upgrade from V4
-----------------------
1. Stop all three Student, Teacher and Knowledge Service windows.
2. Extract KBot_v5_patch_on_top_of_v4.zip into KBot's project root,
   preserving its common/, student_app/, knowledge_service/ and tests/
   subdirectories. Accept overwrite for the included source files only.
3. Restart START_ALL.bat. No pip install, database reset, re-upload, or
   Coze Publish required. Keep the V4 pdfplumber dependency installed.
4. Open a NEW Student quiz session and test Bayes risk Matching; definition
   of lamp Fill Blank and Short Answer; and point-source two-point grading.
5. When a source genuinely has fewer than three reliable matching pairs,
   the service may still safely return unavailable. It never fills gaps
   with invented definitions. Very damaged math formulas are still rejected.

Regression result in container: 69 tests run, 68 passed, one pre-existing
unrelated teacher/dashboard.html SHA assertion failed. The actual teacher
file is byte-identical to V4. Live Coze API was not invoked in this test.

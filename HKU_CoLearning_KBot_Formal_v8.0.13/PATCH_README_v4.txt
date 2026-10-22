HKU Co-Learning KBot — v4 legacy-math PDF repair
====================================================

THIS IS A PATCH, NOT A STANDALONE FULL PROJECT.
- KBot_v4_patch_on_top_of_v3.zip: use on the already installed v3 project.
- KBot_v4_cumulative_patch.zip: use over a matching original/v2/v3 project.

Critical discovery confirmed against the user's exact 51-page Bayes PDF:
- requirements.txt previously installed pypdf but NOT pdfplumber.
- Missing pdfplumber silently activated pypdf fallback; pypdf extracted
  page 23 as 'Choose i thatmaximizes ...' with broken Symbol-font glyphs.
- The newly required pdfplumber reader retains word boundaries and
  decodes supported SymbolMT Greek/math glyphs (e.g., omega, alpha, lambda,
  equal, less-than) using font-aware mapping.
- Unrecoverable private-use glyphs, damaged math fragments and certain
  unrelated topic matches are rejected before student-facing quiz output.
- When pdfplumber is absent, unreadable legacy-math PDFs fail with an
  actionable error instead of silently populating a corrupt course index.

CHANGED FILES
- requirements.txt: adds pdfplumber>=0.11,<1.
- knowledge_service/document_parser.py: font-aware PDF text extraction;
  fail closed for PUA-heavy PDFs when pdfplumber is missing.
- common/quiz_engine.py: reject damaged or incomplete technical phrases
  in True/False and MCQ; tighten short-topic evidence matching while
  preserving real topic-scoped outline pages.
- tests/test_core.py: four new regression tests.

MANDATORY DEPLOY STEPS ON WINDOWS
1. Stop Knowledge, Teacher and Student services; back up source files.
2. Unzip into the KBot root preserving directory structure. Do NOT
   delete or overwrite .env, SQLite, MySQL or vector-store data.
3. Run INSTALL_WINDOWS.bat again. This now installs pdfplumber. You can
   verify it with: python -m pip show pdfplumber
4. Restart with START_ALL.bat.
5. IN TEACHER UI: DELETE THE OLD INDEXED BAYES PDF, THEN UPLOAD THE SAME
   51-PAGE PDF AGAIN. An upload with the exact same SHA256 is a duplicate
   and will not rebuild the preexisting index. Keep the original file
   safely on your computer. This step only affects Bayes notes; reupload
   other existing documents only if they have the same legacy-font issue.
6. In Student UI, start a NEW quiz session after the Bayes reupload.
   Test 'Bayes risk' True/False and 'Bayes decision rule' MCQ.

NO COZE PROMPT CHANGES in v4. Keep your published v3 Quiz and Notes
Agent prompts. AI Grading Agent also stays unchanged.

LIMITATIONS
- Source-page formula indices may still be interleaved by the legacy
  PDF layout. This patch does not reconstruct missing equations or invent
  math. It prefers rejecting a bad question to displaying corrupt text.
- The cleanest long-term fix for equation-heavy lecture notes is a
  verified, editable, Unicode-text companion prepared from the actual
  slides (not simply renaming .doc to .docx).
- Local reproduction: the uploaded Bayes PDF indexed as 51 pages and
  1 course chapter; Bayes risk T/F was generated on p17 with readable
  alpha notation. MCQ for 'Bayes decision rule' can still return
  unavailable when there is no safely extractable correct option; this
  is safer than the previously displayed gibberish.
- Not tested against the user's live Coze Agent or personal database.
- Full local test suite: 62 tests, one PRE-EXISTING unrelated teacher
  dashboard SHA256 assertion failure; no teacher file changed in v4.

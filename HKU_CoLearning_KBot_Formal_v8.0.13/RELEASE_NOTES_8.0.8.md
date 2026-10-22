# HKU Co-Learning KBot 8.0.8

## Scope

This release fixes three failures found while recording the Student Bot demonstration: a stale out-of-scope topic, an intermittent GPS Fill Blank dead end, and True/False questions that were biased to True. It does not change the database schema, account compatibility, five-stage progression, Notes QA, teacher feedback, or Kahoot export.

## 1. Topic recovery after an out-of-scope attempt

### Reproduced cause

In v8.0.7, `/api/exercise/generate` copied the first submitted topic into `session["quiz_topic"]` before Knowledge retrieval and question validation completed. When `linear algebra` returned no relevant course-note content, the invalid topic was already stored. Later requests containing `LBS` or `GPS` were ignored because the backend treated the stale session value as locked.

### Correction

- The route now distinguishes a submitted topic from a validated, locked topic.
- A topic is locked only after a grounded question has been generated and saved, or after the quiz session contains established coverage history from an earlier successful question.
- Failed retrieval does not write `quiz_topic`.
- An already-open v8.0.7 session with a stale invalid first topic is automatically repairable: the next submitted topic is used when no successful grounded generation exists.
- Once the first valid question succeeds, the topic remains locked for the later MCQ, Matching, Fill Blank and Short Answer stages as before.

## 2. Intermittent Fill Blank fallback failure

### Reproduced cause

The local Fill Blank constructor previously examined only the single history-aware focus fact chosen for that attempt. After several earlier questions or retries, GPS could select a valid fact such as:

`The coordinates are then converted by the appropriate geodetic transformation to the local coordinate set.`

That fact was relevant and complete, but the previous extractor did not recognise the lower-case technical phrase `geodetic transformation`. It therefore raised `The notes do not contain a safe distinctive term for fill_blank fallback.` and left the learner at the same stage.

### Correction

- Fill Blank extraction now recognises safe one-to-three-word lower-case technical noun phrases, while continuing to reject generic words and number-only answers.
- If the selected focus fact still cannot form a grounded blank, the backend searches the remaining topic-relevant facts returned by the Knowledge Service, preferring unused facts before controlled reuse.
- The chosen answer must occur verbatim in the supporting fact, and the generated question must contain exactly one visible `_____` blank.
- The fallback still fails safely when the retrieved notes truly contain no suitable answer; it no longer fails merely because one otherwise valid focus fact is not blankable.

## 3. True/False answer balance

### Reproduced cause

The local True/False fallback explicitly returned `correct_index: 0`, and the Quiz Agent dynamic/platform examples also specified index 0. The code therefore made local items True and strongly biased live Agent output toward True.

### Correction

- The backend now calculates a deterministic target of 0 (True) or 1 (False) from the active quiz-session seed, topic and focus fact.
- For a True target, it uses the supported course-note fact.
- For a False target, it creates a bounded contradiction by changing one numeric detail, adding/removing one negation, or using a direct source-denial form as a last resort.
- The explanation always remains the exact supported fact from the notes.
- Grounding validation checks that a false statement stays close to the supported fact instead of introducing an unrelated claim.
- The dynamic prompt states the required target, and an Agent response that returns the opposite index is rejected in favour of the grounded local fallback.

## Coze update required

Replace the Quiz Generation Agent Persona/System Prompt with the v8.0.8 version in:

- `docs/COZE_AGENT_PROMPTS.md`
- `docs/COZE_AGENT_PROMPTS.docx`

Then republish the Quiz Agent to the API channel. The v8.0.7 multi-point AI Grading prompt and the Notes Agent prompt are unchanged.

## Verification

- Complete Python source compilation passed.
- Student JavaScript syntax passed `node --check`.
- Core regression suite passed 38/38 tests.
- Feedback, Student review, Kahoot and Short Answer suites passed 25/25 tests.
- A real bundled `knowledge.db` probe used 16 quiz-session seeds and produced both True and False answer indices.
- Five GPS flows with zero through four additional MCQ retries all reached a valid grounded Fill Blank question. The previously failing page-78 fact now yields `geodetic transformation` as a safe answer.
- Retrieval returned no course-note results for `linear algebra` and valid results for `LBS` and `GPS`; the route now persists only the successful topic.
- The updated prompt DOCX was rendered and visually inspected.

The full Flask HTTP suite could not run in this container because Flask and Werkzeug are unavailable. A route-level regression test was added and should be run in the Windows/deployment environment. Live Coze, browser, MySQL/Docker and Windows command-shell acceptance still require the deployment environment and credentials.

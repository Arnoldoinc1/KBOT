# v8.0.13 Fill Blank Quality Test Report

## Scope

This regression targets the reported GPS item that blanked the preposition `For` instead of a course concept.

## Real-PDF fixture

Source sentence from the packaged 90-page course PDF, GPS Background page 63:

`For the GPS user, the system is passive and requires a receiver only without the requirement to transmit.`

## Executed checks

1. Direct grounding validation rejects answer `For` as a grammar/function word.
2. The deterministic constructor selects `receiver` and produces exactly one blank.
3. Replacing the blank with `receiver` reconstructs the source fact.
4. A simulated configured Quiz Agent returning the invalid `For` JSON is rejected.
5. The same request then completes through `local_fallback` with answer `receiver`.
6. Existing multi-retry Fill Blank recovery still generates a valid item after earlier GPS facts have been consumed.
7. All core tests, Short Answer quality tests, feedback/Kahoot tests and Agent/migration tests are rerun.

## Expected learner-facing item

Question:

`For the GPS user, the system is passive and requires a _____ only without the requirement to transmit.`

Correct answer:

`receiver`

## Interpretation

Source occurrence alone is not educational grounding. A Fill Blank answer must be both present in the notes and knowledge-bearing. The new validation separates those requirements and applies them to both external Agent output and local construction.

## Regression totals

- Core suite: **49/49 passed**.
- Short Answer quality plus feedback/Kahoot suites: **27/27 passed**.
- Function-word probe: **14/14 rejected**.
- Real-PDF local fact probe: **97 valid Fill Blank items**, **24 facts safely unavailable**, **0 invalid generated items**.
- Python compileall: passed.
- Student and Teacher JavaScript syntax: passed.
- Coze/Windows/MySQL live execution was not available in the build container. The Agent/migration and Flask HTTP modules could not be imported because Flask/Werkzeug were unavailable.

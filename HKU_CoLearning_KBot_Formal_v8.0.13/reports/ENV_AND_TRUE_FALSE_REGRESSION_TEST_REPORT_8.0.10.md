# v8.0.10 Environment and True/False Regression Report

## Reproduced v8.0.9 defect

Using the packaged real Knowledge index, topic `gps`, a False-target session, and no configured Agent selected page 86 / section `BDS Ranging signal`:

- focus: `Based on the CDMA principle.`
- generated fallback: `The course notes do not state that based on the CDMA principle.`
- result: `QuizValidationError: The false statement is not a bounded contradiction of the course-note fact.`

## v8.0.10 result

The True/False selector rejected the fragment and selected the complete page-62 GPS Background fact. Both True and False targets passed grounding validation across multiple session seeds.

The False version changed one bounded detail by inserting `not`; it did not use a meta-claim.

## Configuration probes

1. Root `.env` absent, stale `COZE_TOKEN` and `COZE_QUIZ_BOT_ID` present in the process environment, `COZE_ENABLED` unset:
   - `coze_runtime_enabled() == False`
   - token source reported as `process_environment`
   - runtime remained local fallback mode.

2. Root `.env` absent, the same credentials present, `COZE_ENABLED=true`:
   - `coze_runtime_enabled() == True`
   - environment-only deployment remains supported.

## Timing probes

Direct local generation using the packaged SQLite Knowledge index:

- GPS True/False: under 0.1 s total;
- LBS True/False: under 0.1 s total;
- Mobile Communication True/False: under 0.1 s total.

These measurements exclude browser rendering, Windows process startup and external Coze latency.

## Automated checks

- complete Python tree: `compileall` passed;
- core + Short Answer + feedback/Kahoot suites: 68/68 passed through `unittest`;
- new regressions cover the GPS bounded-False path and stale process-environment Coze values;
- JavaScript syntax was checked separately with `node --check` when Node was available;
- full live Coze, Windows CMD and MySQL/Docker acceptance were not executed in the container.

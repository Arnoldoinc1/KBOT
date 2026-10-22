# HKU Co-Learning KBot v8.0.10

## Scope

This release fixes the GPS True/False generation failure reported during the demo and makes the no-`.env` startup behaviour explicit and auditable.

## 1. Why the project can start without `.env`

The root `.env` has always been optional in the Python configuration layer. When it is absent, KBot can still start because it has local defaults for:

- a bundled SQLite application database at `data/shared/kbot.db`;
- a bundled Knowledge index and uploaded lecture PDF under `data/knowledge/`;
- matching local read/admin keys used by the three local services;
- a local Flask session secret; and
- deterministic local quiz, grading and Notes fallbacks.

Therefore, “the three windows opened and questions appeared” did not prove that Coze was being used.

In v8.0.9, any `COZE_*` values inherited from the Windows user/system environment could silently enable an Agent even when the project folder contained no `.env`. That could make generation unexpectedly slow while the application waited for Coze and then fell back locally.

v8.0.10 adds `COZE_ENABLED`:

- `true`: external Coze calls are allowed;
- `false`: local fallback mode only;
- `auto` (runtime default): Coze is enabled only when a root `.env` exists.

The supplied `.env.example` contains `COZE_ENABLED=true`. An environment-only deployment can still set `COZE_ENABLED=true` explicitly.

`START_ALL.bat` startup checks now report, without exposing secrets:

- whether the root `.env` exists;
- whether Coze runtime is enabled;
- whether each Agent is configured; and
- whether each token/Bot ID came from the root `.env`, the process environment, or a default/blank value.

## 2. GPS True/False failure

The failing v8.0.9 path selected this extracted page-86 fragment as the focus fact:

> Based on the CDMA principle.

When the session target required a False answer, the last-resort constructor produced a meta-statement similar to:

> The course notes do not state that based on the CDMA principle.

That is not a direct contradiction of the fact, and its token overlap was below the validator threshold. The local fallback therefore failed its own validation and the route returned HTTP 422.

v8.0.10 now:

- requires a complete proposition for True/False;
- rejects leading fragments such as `Based on`, `Using`, `Use as`, `By`, `To`, `Originally` and `Unlike`;
- rejects unmatched quotation marks;
- prefers stored facts over sentence fragments extracted from a chunk;
- chooses the True/False target independently from the focus fact;
- when False is required, selects a fact that supports a safe one-detail contradiction;
- permits only a numeric change, one inserted/removed negation, or a bounded antonym pair; and
- removes the previous “the course notes do not state that...” last resort.

For the bundled GPS notes, the corrected fallback uses a complete page-62 fact such as:

- True: `GPS is a satellite based navigation system offering precision navigation capability.`
- False: `GPS is not a satellite based navigation system offering precision navigation capability.`

## 3. Generation speed diagnostics

The Student service now logs separate timings for:

- Knowledge search;
- matching-term retrieval;
- quiz generation; and
- total request time.

The log also reports `source=local_fallback` or `source=coze_quiz_agent`. This makes it clear whether a delay comes from local retrieval or an external Agent call.

With no root `.env`, v8.0.10 enters local fallback mode and does not wait for stale Windows `COZE_*` values. Direct real-index probes for GPS, LBS and Mobile Communication completed in under 0.1 seconds each in the test container; browser/Windows timing will vary.

## Compatibility

- No database migration is required.
- Existing accounts, History, Teacher feedback, Knowledge data and the five-stage flow remain compatible.
- To use Coze, copy `.env.example` to `.env`, fill the token and three Bot IDs, and keep `COZE_ENABLED=true`.
- To run a fast offline demo, omit `.env` or set `COZE_ENABLED=false`.

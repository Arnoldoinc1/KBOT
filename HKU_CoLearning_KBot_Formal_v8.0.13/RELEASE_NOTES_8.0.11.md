# HKU Co-Learning KBot v8.0.11 Release Notes

## Scope

This release addresses two observations from a complete Windows demo of v8.0.10:

1. Quiz generation was functionally successful but unnecessarily slow because all five types waited for the external Quiz Agent.
2. A gyroscope Short Answer was framed and graded as “four principles” even though the course slide contains three principles and a separate applications bullet. A substantially complete learner answer was then under-marked as 63/100.

No database migration is required.

## Generation-performance changes

- Added `COZE_QUIZ_TYPES` routing.
  - Default: `mcq`
  - `all`: old behaviour; all five types call the Quiz Agent
  - `none`: all quiz generation is local and course-grounded
  - comma-separated subset: for example `mcq,short_answer`
- True/False, Matching, Fill Blank and Short Answer use deterministic constructors by default. MCQ remains the default external-Agent demonstration.
- Matching candidate retrieval now runs only for MCQ and Matching, rather than for every type.
- Search limits are type-specific and the Quiz Agent receives a smaller bounded evidence prompt.
- An active saved draft is reused after duplicate auto-generation/reload instead of triggering another Coze request.
- Student generation and submission logs now contain request IDs, source and timing fields.
- Static assets are cache-busted with `?v=8.0.11`.

These changes do not weaken grounding. Every locally constructed item still uses the Knowledge Service results, the same server-side hidden answer fields and the existing grounding validator.

## Gyroscope Short Answer correction

The bundled slide presents:

- Spinning Motion
- Conservation of Angular Momentum
- Precession
- an applications sentence: navigation, UAV stabilisation and golf clubs

The fourth bullet is not another principle. v8.0.11 parses inline `Label: definition` bullets, separates application/example bullets, and generates a three-point question for this slide. A question claiming “four principles” is rejected or reconstructed.

## Grading correction

- The Grading Agent contract now permits only `0`, `50` or `100` for each required point.
- Backend scoring is recalculated from the complete set of point results.
- A deterministic lexical guardrail compares the actual learner answer with each private rubric point. It upgrades an obvious under-marked point but never lowers the Agent's semantic judgment.
- When a rubric point itself is an applications/examples list, stating the listed applications is full coverage; the learner is not required to invent explanations absent from the notes.
- The authoritative reference answer remains the server-side rubric, not a shortened Agent copy.

Republish the AI Grading Agent using `docs/COZE_AGENT_PROMPTS.md` or `.docx` for consistent platform output. The backend correction applies even before republishing.

## Recommended `.env` settings

Balanced live demo:

```dotenv
COZE_ENABLED=true
COZE_QUIZ_TYPES=mcq
COZE_TIMEOUT=35
```

Fastest quiz-generation recording while retaining configured grading and Notes agents:

```dotenv
COZE_ENABLED=true
COZE_QUIZ_TYPES=none
COZE_TIMEOUT=35
```

Old all-Agent generation behaviour:

```dotenv
COZE_QUIZ_TYPES=all
```

## Verification

- Python source-tree compilation passed.
- Student JavaScript syntax check passed.
- Core, Short Answer, feedback and Kahoot regression suite passed 70/70.
- The real packaged gyroscope slide produced a three-point rubric.
- The reported learner answer received 100/100 in the local path.
- A simulated Grading Agent response that returned 63/100 for the same answer was normalised to 100/100 by the backend guardrail.
- Clean ZIP extraction, CRC and post-extraction compilation/tests were performed.

Live Coze latency, Windows browser behaviour and MySQL/Docker remain deployment-environment checks.

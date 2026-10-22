# HKU Co-Learning KBot 8.0.7

## Scope

This release changes only the Short Answer generation, grading, feedback and post-submit display path. True/False, MCQ, Matching, Fill Blank objective behaviour, Notes QA, Knowledge Service ownership, five-stage progression, authentication, database schema and Kahoot export are unchanged.

## Problem reproduced

The previous Short Answer path had two related weaknesses:

1. A broad question could be generated from one focus sentence even when the same slide contained several finite course-note points. The stored reference answer then covered only one point, so the grading contract did not clearly state whether the other valid points were required.
2. A structurally valid Grading Agent response could contain a reasoning string that ended mid-sentence. Because the JSON itself was complete, the previous parser accepted the incomplete feedback and displayed it to the student.

The real lecture PDF reproduces the first issue on page 19. The slide contains the LBS definition plus Pull, Push and Tracking, while the earlier question/reference pair could retain only the definition.

## Short Answer generation correction

- The backend now builds an explicit private `key_points` rubric from the selected course-note slide or section.
- Finite bullet groups of two to four relations are kept together. Page 19 therefore produces four required points: the LBS definition, Pull, Push and Tracking. Page 22 produces the three Values of LBS relations.
- A long open list is not silently truncated to an arbitrary first four items. When a slide contains many possible examples, the local fallback narrows the question to one specific focus point.
- Multi-point questions explicitly state how many points must be addressed.
- The server reconstructs the full reference answer and explanation from authoritative retrieved evidence. A shortened Agent reference cannot replace it.
- All key points and their citations remain private until submission.

## Short Answer grading correction

- The Grading Agent receives every required key point and must return one `key_point_results` item per point.
- Each point receives 0-100 credit. The backend ignores an inconsistent overall score and recalculates the final score as the arithmetic mean of all point credits.
- One of three required points therefore cannot receive 100; two fully covered points and one missing point produce approximately 67.
- The server uses its complete reference answer as the authoritative correct answer rather than accepting a shortened Agent copy.
- Reasoning and every point comment must be complete sentences. An incomplete tail such as `According to the course material, an LBS` is rejected and the safe local fallback is used.
- The local fallback also scores each explicit key point separately and discounts words shared across all points so repeating a general course term does not count as covering a missing bullet.
- Legacy Short Answer records and the optional Fill Blank semantic path retain the previous single-score contract when no explicit `key_points` rubric is present.

## Student and teacher feedback

After Short Answer submission, the Quiz result card now shows a separate Key-point assessment list with the credit and complete comment for every required point. The existing full reference answer, explanation and course-note references remain visible.

The teacher-side audit feedback now records:

- all required key points;
- each point's credit and comment;
- the complete reference answer;
- the complete explanation and source citations.

No database migration is required. `key_points` continues to be stored inside the existing `options_or_pairs` JSON field.

## Coze update required

The Quiz Generation and AI Grading platform prompts changed. Before live testing, replace the two corresponding Coze Persona/System Prompts with the versions in:

- `docs/COZE_AGENT_PROMPTS.md`
- `docs/COZE_AGENT_PROMPTS.docx`

Then republish those two Agents. The Notes Agent prompt is unchanged. The backend will safely fall back if an old Grading Agent omits the new point results, but updating and republishing the Agents is required for normal live operation.

## Verification

- Complete Python source compilation.
- Student JavaScript syntax check with Node.
- Existing 14/14 feedback, student-review and Kahoot regression tests passed.
- Existing 35/35 core tests passed after correcting the stale Teacher dashboard integrity hash to the already-packaged v8.0.6 dashboard.
- New 11/11 Short Answer quality tests passed.
- Tests use the bundled 90-page lecture PDF and verify pages 19, 20 and 22.
- Prompt DOCX rendered and visually checked.
- Final archive CRC, clean extraction, source compilation and dependency-light test rerun completed.

Live Coze, browser, MySQL/Docker and Windows command-shell acceptance still require the deployment environment and credentials.

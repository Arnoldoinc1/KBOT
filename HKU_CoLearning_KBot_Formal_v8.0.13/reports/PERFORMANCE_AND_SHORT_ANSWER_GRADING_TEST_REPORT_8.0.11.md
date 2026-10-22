# v8.0.11 Performance and Short Answer Grading Test Report

## Reported Windows trace

The v8.0.10 access trace showed a valid server-authoritative sequence:

`setup -> true_false -> mcq -> matching -> fill_blank -> short_answer`

HTTP 200 responses for setup, generation and submission confirmed progression. HTTP 302 from `/` to `/dashboard` and HTTP 304 responses for static files are normal browser behaviour. One generation request returned 409 before a successful retry; v8.0.10 did not print the rejection reason, so the status code alone cannot identify whether it was a state mismatch, an empty retrieval result or a safe validation rejection. v8.0.11 logs the exact reason and a request ID.

The visible waits before successful generation were consistent with repeated external Quiz Agent calls. Submit-to-submit intervals are not valid latency measurements because they include learner reading and typing time.

## Performance implementation checks

- Default `COZE_QUIZ_TYPES=mcq` routes one of five generation steps to Coze.
- `COZE_QUIZ_TYPES=none` routes no quiz-generation steps to Coze while leaving Grading and Notes Agent configuration intact.
- Matching term retrieval is skipped for True/False, Fill Blank and Short Answer.
- Evidence sent to the Quiz Agent is bounded to the focus chunk plus at most three supporting chunks and twelve terms.
- Active-draft reuse prevents duplicate requests after reload or repeated auto-generation.
- Logs include request ID, type, topic, source, search/terms/generation/total timings and Short Answer grading source/timing.

## Gyroscope source interpretation

The page contains three named principles with explanations: Spinning Motion, Conservation of Angular Momentum and Precession. The final bullet lists applications. It is not a fourth principle and should not create a fourth explanatory rubric point.

The revised parser recognised the three inline label-definition relations and excluded the applications line from the principle list. The generated question therefore requests the three principles explicitly.

## Grading regression

Test learner answer:

- accurately states Spinning Motion and angular momentum;
- accurately states conservation of angular momentum;
- accurately explains precession;
- also states the slide's applications.

Expected result: full coverage of the three actual principle points.

Observed checks:

- local point-based grading: 100/100;
- simulated external payload: 63/100 with under-valued point credits;
- backend-normalised result: 100/100;
- every point result is one of 0, 50 or 100;
- reference answer remains the complete private server rubric.

## Automated result

`python -m unittest tests.test_core tests.test_short_answer_quality tests.test_feedback_and_kahoot`

Result: 70 tests passed.

# HKU Co-Learning KBot v8.0.13 Release Notes

## Reported defect

A live Fill Blank item removed the word `For` from this course-note sentence:

`For the GPS user, the system is passive and requires a receiver only without the requirement to transmit.`

The resulting question was grammatically answerable but did not assess a GPS knowledge point.

## Root cause

The Quiz Agent could return any one-to-three-word answer that appeared in the retrieved notes. The v8.0.12 grounding validator checked answer length and source occurrence, but did not distinguish a course concept from an article, preposition, connector or other function word. Consequently, `For` passed the structural and source checks.

The deterministic local constructor did not choose `For`, but it could still prefer the broad topic term `GPS` because stored term pairs were considered before more specific fact-bearing complements.

## Fixes

1. Added a Fill Blank function-word blocklist covering articles, prepositions, conjunctions, pronouns, auxiliaries, introductory connectors and other low-information words.
2. Added a knowledge-bearing answer check for every Agent and local Fill Blank item.
3. Required exactly one visible blank.
4. Restored the answer into the question and verified that the completed sentence is grounded in the retrieved notes and closely matches both the explanation and selected focus fact.
5. Added candidate extraction for fact-bearing complements such as `requires a receiver` and `is passive`.
6. Ranked local candidates by educational value, known-term support, technical form and grammatical relationship to the fact. Broad session-topic words are penalised when a more specific concept exists.
7. Updated the dynamic Quiz prompt and the fixed Coze Quiz Agent prompts in Markdown and DOCX.
8. Added a real-PDF regression that rejects `For`, selects `receiver`, and proves that a bad Agent response is replaced by a grounded local item.

## Result for the reported sentence

The deterministic item is now:

- Question: `For the GPS user, the system is passive and requires a _____ only without the requirement to transmit.`
- Answer: `receiver`

If a Quiz Agent still returns the old `For` item, backend validation rejects it and the learner receives the deterministic `receiver` item instead.

## Deployment

The recommended final setting remains:

```dotenv
COZE_QUIZ_TYPES=mcq,short_answer
```

Under this setting Fill Blank is local and does not wait for the Quiz Agent. Installations using `COZE_QUIZ_TYPES=all` are also protected by the new backend validator. No database migration is required.

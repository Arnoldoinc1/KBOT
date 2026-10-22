# HKU Co-Learning KBot 8.0.9

## Scope

This release corrects a Short Answer alignment failure found during demo review. A generated question asked for “the 4 points about mobile communication”, while its private marking rubric came from the earlier Location Based Services slide. Every stored answer sentence was present somewhere in the PDF, so the old grounding check accepted it even though the question and answer belonged to different subsections.

No database migration is required. The v8.0.8 stale-topic, Fill Blank and True/False fixes remain in place.

## Reproduced cause

The failure was a combination of three behaviours:

1. Lexical retrieval treated a broad topic as a bag of words. For `mobile communication`, pages in the LBS section could score because they repeatedly contain `mobile`.
2. Short Answer used the same single-fact, history-diversity selector as the objective question types. It did not first look for one coherent finite list that could serve as a complete rubric.
3. The backend rebuilt `key_points`, `reference` and `explanation` from course evidence, but it could retain an Agent question merely because it ended with a question mark and mentioned the expected number. It did not test whether the question subject named the same section or labelled items as the rubric.

This was therefore a semantic cross-grounding error, not an unsupported-answer hallucination.

## Corrections

### 1. Outline-aware topic scope

When an uploaded deck exposes a usable contents/outline page, topic-mode retrieval identifies the matching top-level section and restricts quiz candidates to that page range. For the bundled Chapter 3 deck, the detected ranges are:

- Accelerometer and Gyroscope: pages 2–16
- Overview of Location Base Service: pages 17–30
- Mobile communication: pages 31–60
- GPS: pages 61–90

Acronyms such as `LBS` are matched to the corresponding outline heading. If no reliable scope exists, retrieval uses a conservative all-query-word coverage rule rather than accepting a one-word partial match.

### 2. Short Answer-specific focus selection

Short Answer now prefers a complete, coherent group of two to four labelled relations from one slide/section. It rejects an apparently four-point subset when the same slide contains an additional unexplained list item, so a longer list is not silently truncated.

Earlier objective questions may already have used one fact from the page. For the final Short Answer search, page/chunk penalties are relaxed while fact history is retained, allowing the complete rubric page to be selected without discarding diversity information.

### 3. Server-authoritative question/rubric alignment

The backend now constructs an authoritative question from the same section, labels and count as the private key points. An Agent question is retained only when it:

- is a complete question;
- names the relevant section or labelled items;
- asks for the correct number, or explicitly names every labelled item; and
- remains consistent with the retrieved rubric.

Grounding validation applies the same check. A question such as “state and explain the 4 points about mobile communication” is rejected when the rubric is LBS definition/Pull/Push/Tracking or any other unrelated list.

## Corrected bundled-PDF example

For the topic `mobile communication`, the Short Answer fallback now selects page 42, section `Network structure`, and creates:

`According to the course notes, name and explain the 4 components listed under Network structure?`

The private marking points are:

1. Base Station Subsystem: manages radio communication between mobile devices and the network.
2. Network and Switching Subsystem: handles call routing, mobility management and subscriber data management.
3. GPRS Core Network: enables mobile internet and data transmission.
4. Operations support system (OSS): provides network-management and maintenance tools.

All four citations point to page 42. The backend does not add further GSM details unless those details are separately present in the retrieved course evidence.

For page 19 itself, the safe question is no longer the vague “4 points about LBS”. It explicitly asks the learner to define LBS and explain Pull, Push and Tracking, while retaining the definition plus the three interaction types as four private marking points.

## Coze configuration

No Coze platform-prompt republish is required for this release. The stronger instruction is added to the per-request dynamic prompt, and the server independently replaces or rejects a mismatched Agent question. The fixed Quiz, Grading and Notes Agent IDs remain unchanged.

## Verification

- Complete Python source compilation: passed.
- Student JavaScript `node --check`: passed.
- Core suite: 41/41 passed.
- Short Answer quality suite: 11/11 passed.
- Feedback and Kahoot suite: 14/14 passed.
- Real-PDF probe: `mobile communication` was limited to pages 31–60, page 19 was excluded, and the final Short Answer used the four page-42 Network structure points and four page-42 citations.
- `linear algebra` returned no topic-mode results.

The Flask HTTP and agents/migration suites could not be executed in this container because Flask/Werkzeug are unavailable. Live Coze, browser, MySQL/Docker and Windows batch acceptance still require the deployment environment and credentials.

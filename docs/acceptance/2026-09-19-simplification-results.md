# SourcePack 0.4 simplification: measured results

19 September 2026. **Keep this as a small experimental skill. Stop platform expansion.** The saved evidence and recovery workflow work, but these tests found no answer-accuracy or speed advantage over competent direct use of the underlying tools. The repository is already public; this qualifies an experimental update, not general production readiness or user demand.

## What changed

The normal workflow is now `prepare → inspect → finish`, followed by optional `query` or `export`. The host reads a compact view, opens relevant native frames and saves one findings file. It no longer needs to submit irrelevant observations to advance through whole-source tickets. Selected inspection still uses bounded, job-owned leases; originals, legacy APIs and five-minute import limits are retained. Unselected evidence remains uninspected.

A derived caption view removes some rolling repetition without modifying originals. On one retained 74-second source, it reduced 15,399 characters to 4,677. This is a readability result, not an audio-fidelity score: some rolling fragments remain, and original text must be checked for literal quotations. Search adds a labelled partial-term fallback; it is still lexical, not semantic search.

Summarize supplies model-free extraction; yt-dlp and ffmpeg supply video/captions and frame processing. Optional isolated MarkItDown converts documents. The host model supplies understanding. These tools already do much of the work, including visual extraction capabilities in Summarize. SourcePack adds consistent evidence identity, saved observations, validation and resume; it does not merge their internals or make a stronger model. Docling and OCR remain disabled.

## Frozen comparison

Before the runs, a private protocol froze the same six Video-MME questions used in the preceding pilot, two repetitions per condition, document prompts, and a convenience gate. Each video/condition/repetition used a fresh agent context with the same inherited host/model configuration. Exact serving model revision and token accounting were not exposed. Neither condition saw the answer key. The parent scorer did, so scoring is not blinded.

The two short public videos were [History behind Christmas decorations](https://www.youtube.com/watch?v=fFjv93ACGo8) and [A Brief History of Communication](https://www.youtube.com/watch?v=0ay2Qy3wBe8), cases 001 and 007 in the selected annotation subset. Questions came from [Video-MME](https://github.com/MME-Benchmarks/Video-MME) and its [linked annotations](https://huggingface.co/datasets/lmms-eval/Video-MME). Raw questions, keys and captured media stay private. This is six unique questions repeated twice, not twelve independent questions or a general benchmark.

Both conditions received the same acquired source material and had to retain evidence with answers. Acquisition was excluded from elapsed time. Direct agents could use installed local tools freely; skill agents received a standalone copied skill. State for both conditions was placed on the same internal filesystem outside the previously slow Documents location. Full duplicate portable export became optional because the run already retains originals. Earlier timings therefore are not a controlled before/after comparison.

## Results

| Run | Correct answers | Observed seconds |
|---|---:|---:|
| direct-001-r1 | 3/3 | 71.49 |
| direct-001-r2 | 3/3 | 58.12 |
| direct-007-r1 | 3/3 | 56.82 |
| direct-007-r2 | 3/3 | 55.08 |
| skill-001-r1 | 3/3 | 101.60 |
| skill-001-r2 | 3/3 | 91.98 |
| skill-007-r1 | 3/3 | 86.65 |
| skill-007-r2 | 3/3 | 78.59 |

Across video runs, direct tools scored **12/12 in 241.51 seconds**; SourcePack scored **12/12 in 358.82 seconds**. SourcePack was **1.486 times as slow**, about **49% longer**. The predeclared ceiling was 1.5 times direct elapsed time with correct supported answers and recovery preserved. It passes that timing ceiling only marginally; ordinary timing noise could reverse it. There is no statistical significance claim and no evidence of improved reasoning.

The parent opened all 25 distinct cited native images and checked caption support. All selected answer conclusions had supporting evidence, with no missed scored visual fact. Citation existence is mechanically checked separately from semantic support. Two SourcePack answers used the start of a roughly 77-second transcript span for a later sequence claim: the span supports the answer, but the timestamp is broad, not a precise event locator. Automatic captions remain uncertain and were not checked against independent audio. No exhaustive visual recall score is claimed.

| Additional check | Direct tools | SourcePack |
|---|---|---|
| Five small document/text cases | Correct substantive answers; 73.25 s | Correct substantive answers; 99.19 s |
| Fresh-context phone-frame and policy retrieval | Both recovered and reopened; 36.82 s | Both recovered and reopened; 87.99 s |
| Video helper/recording failures | None reported | None reported |
| Document interventions | Existing local XML/text and page-rendering tools | One mistaken question-file path; scan text extraction failed explicitly, then host rendered and inspected page |
| Monetary cost and tokens | Not observable | Not observable; no extra extraction model calls or paid extraction |

The five owned fixtures cover Markdown roles/requirements/unverified claims and an untrusted instruction, PPTX slide locations, a scanned PDF, XLSX requirements and unknown budget units, and DOCX retry policy. These are small synthetic acceptance cases, not evidence of robust arbitrary-document understanding. Both approaches retained supporting files. The scan success depended on installed `pdftoppm` and host image inspection outside SourcePack's text adapter; it does not qualify automatic OCR. Slide text was inspected, not rendered slide appearance. The parent checked the source text and scan page.

Fresh-context SourcePack retrieval found the previously established phone message and reopened its native frame using a labelled partial-term match for `phone message`. The policy query `failed attempts` returned nothing; `failures` succeeded. Direct retrieval also succeeded and was faster. This establishes working persisted retrieval, not a retrieval advantage or paraphrase robustness.

## Verification and review

- Final local suite: **98 tests run, 96 passed, 2 optional live-converter tests skipped**. Those two live document tests were also explicitly enabled and passed separately against the unchanged converter. Existing SQLite fixture ResourceWarnings are non-failing.
- Regression coverage includes bounded selections, unknown/foreign evidence, false quotes, uninspected citations, changed artifacts/views, cancellation, empty findings, changed gaps and idempotent interrupted finish. One regression interrupts after submission but before answer saving, then resumes without duplicate results. Unsaved host reasoning is not recovered.
- Independent code review of implementation commit `607b7c7` found one Important issue: compact inspection omitted core extraction/inspection gaps. It was reproduced with failing tests and repaired. Gap descriptions are now included in the view and saved receipt, and changes invalidate the review ID. No unresolved review blocker remains.
- The agent comparisons used the frozen pre-repair copied implementation. Final gap propagation was tested separately; the paired timings were not rerun or relabelled as measurements of the repaired revision.
- A fresh copy of the final skill ran outside the checkout from an unrelated working directory: real PPTX conversion, reading, finish, identical retry, query and portable export succeeded. The first attempt omitted the private interpreter configuration and failed explicitly; copying the documented per-install configuration corrected it. No dependency was silently installed.
- Skill frontmatter validation and diff whitespace checks passed. GitHub Actions separately checks supported Python versions; consult the PR checks for hosted outcomes.

Private receipts include the frozen protocol, skill hashes, original acquired evidence, answers, timing, findings, follow-up traces, scores and the image audit. Public documentation contains aggregate results and owned fixtures only. Model usage was not free merely because billing was not observable.

## Decision

**Worth sharing as an experimental convenience skill; not worth building into a platform on this evidence.** A reusable evidence folder, honest gaps, structural citation checks and resumable saved work are concrete capabilities. Their convenience may matter when returning to sources, but both direct baselines already answered and recovered correctly. The revised workflow is less cumbersome, yet still slower.

Keep the default small, retain the underlying tools as replaceable dependencies, and stop adding adapters without a real failing use case. Broader investment needs outside users who repeatedly choose it and demonstrate saved effort or fewer evidence mistakes. Automatic skill-trigger precision, other hosts, long-video performance of this new flow, multilingual captions, continuous motion/audio understanding, semantic-search quality and external adoption remain unproved. The earlier long-video results remain historical; they were not repeated here.

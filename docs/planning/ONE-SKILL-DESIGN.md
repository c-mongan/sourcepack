# One SourcePack skill: source understanding with a usable evidence pack

Status: proposed implementation design, grounded in seven pinned source checkouts. No runtime changes are part of this planning commit. Baseline: `b25ca67348ab8a22ffa0e40576517a4e4cabc74d` (47 local tests and hosted checks passed previously).

## User outcome

Give the existing agent a video, webpage or document and a question. The skill acquires the source, reads it, inspects material visuals, checks relevant supporting sources, answers clearly and retains a usable record. A bare source defaults to a thorough explanation with practical steps and limitations. Follow-up questions reuse the pack.

One skill is the public entry point. Extraction, document conversion and storage are small internal adapters. The host chooses what matters and performs semantic/visual judgment; no second LLM orchestrator or service is introduced.

## What the pinned inspection changed

1. The pinned Summarize 0.22.0 runtime returned 1,122 timed segments for the original tutorial when `--timestamps` was supplied. Our invocation omitted it. Use structured timing rather than treating absent timing as an extractor limitation.
2. Our current caption normalization creates 1,122 tiny spans, implying at least 141 eight-span transcript tickets for that source. The earlier short-video forward test did not exercise this cost. Present bounded reading sections with original cue mappings instead.
3. Current acquisition checkpoints only after all acquisition finishes. A video failure can leave a useful transcript inaccessible to `next`. Checkpoint independent stages and allow a usable partial pack.
4. Current video extraction uniformly samples 12 frames per clip. Keep original decoded timestamps, but select a mixture of overview, scene-change and requested-time frames.
5. Current collection exports omit some acquisition originals and leave supporting sources disconnected. Build a root index with a complete manifest and explicit included/omitted artifacts.
6. Docling's `enable_remote_services=False` does not prohibit first-use model downloads. Its `artifacts_path` and dependency/model readiness need explicit configuration.

## Reuse map

Exact commits and inspected file hashes are in [upstream-pins.json](upstream-pins.json).

| Upstream | Adopt | Integration boundary | Avoid |
|---|---|---|---|
| Summarize | Structured timed transcript and established web extraction | External pinned executable; original JSON kept | Another generic extractor or assuming extract means every route is offline |
| claude-video/watch | Transcript-first mode; exact requested moments; scene-aware selection and conservative deduplication | Adapt small selected frame-selection routines if tests prove a benefit; preserve MIT notice for copied code | Importing its setup/account preferences; calculated times presented as decoded PTS; uncapped image batches |
| timharris707/ingest | Per-stage state and readable evidence packet | Adapt state-machine ideas into current workflow; retain our stronger byte hashes | Its mandatory purpose interview, tracker routing, automatic media disposal or Whisper-only quote policy |
| Skill Seekers | Chapter organization, transcript/frame/code alignment | Reproduce the small normalized data boundary; candidate structured importer later | Whole runtime as mandatory dependency; AI-reconstructed code replacing original evidence; heuristic confidence as verification |
| source-to-skill | Organized reference output | Optional explicit downstream action after analysis | Automatically installing source-derived instructions |
| MarkItDown | Basic DOCX/PPTX/XLSX/text-PDF conversion with selected extras | Isolated optional runtime, `MarkItDown(enable_plugins=False).convert_local(...)`; no LLM client | `[all]`, cloud document intelligence, arbitrary plugins, fake PDF page citations from plain Markdown |
| Docling | PDF layout, reading order, tables, page/item provenance and optional OCR | Isolated optional runtime, saved native JSON plus derived Markdown/page images | Silent first-use weights downloads, hosted inference, external plugins, forced use for simple documents |

All seven root licence notices are MIT, including ingest's `LICENSE.md`. That is not a blanket licence for model weights or every dependency. No upstream implementation has been copied in this planning pass. Record exact file, commit, modification and notice before adapting code.

## Routing and user-facing defaults

| Source | Default | Escalation |
|---|---|---|
| YouTube | Captions/metadata first; full-text reading and bounded visual overview | Targeted native frames for relevant settings, diagrams, code or unclear moments |
| Public webpage | Summarize extraction | Existing host browser for incomplete extraction; retain source/route and gap |
| Local UTF-8 text | Existing local adapter | None |
| DOCX/PPTX/XLSX | MarkItDown with format-specific extras | Host visual review of relevant slides/pages where rendering is available |
| PDF | MarkItDown for a text-only question; Docling when layout/tables/scans matter and runtime is ready | Explicit capability gap if requested OCR/layout cannot run; never quietly claim text-only extraction covered the visuals |

`auto` is the normal detail setting. `text` is available for questions requiring no visuals. `deep` increases selected inspection effort within fixed ceilings, not without limit. The host chooses based on the question; the user does not configure a pipeline for every request.

Initial document scope is local files. Downloaded public documents may be passed as local files using existing host retrieval with origin metadata; this release does not invent an authenticated document downloader. One `sourcepack` skill continues to handle all routes.

## Data and compatibility

Retain original input bytes and native producer output. Add `sourcepack.normalized.v1` for derived reading sections and document blocks. Each block contains kind, text, original-source SHA-256, a locator with its coordinate basis, method and any child cue mappings. Transcript groups have at most 1,200 characters; boundaries prefer chapters/sentences and never drop a cue. Original cue times/IDs are retained in the locator or a hashed sidecar. Do not merge genuine repetitions merely because adjacent text overlaps.

For documents, retain native producer JSON when available. MarkItDown-only material is cited by derived heading/paragraph, or PPTX slide marker when verified; it never receives invented page coordinates. Docling-native page numbers, bounding boxes and coordinate origins are preserved. Tables retain structure separately from their Markdown view. Image/page assets remain associated with source and locator.

A normalized importer validates relative artifact paths, hashes, original-source associations and bounded text. It must not execute instructions or follow paths outside the source directory. The engine keeps eight-span/12,000-character tickets and existing result/lease checks. Grouping is a derived representation, not a policy bypass. Existing jobs and leases remain readable unchanged; new grouping changes new job identity via an adapter revision.

Use `sourcepack.run.v2` for new stage-aware runs. A v1 reader supports existing query/export/inspection; acquisition resume requires an explicit copy-on-write upgrade retaining `run.v1.json`. Never overwrite old evidence IDs. Keep SQLite version 2 unless an actually necessary new table requires a separately tested additive migration.

## Acquisition and resume

Stages: metadata, transcript, video, visual-index, documents, supporting-sources, report/export. Each record includes status (`pending`, `ok`, `partial`, `failed`, `skipped`), attempt, extractor/version/options fingerprint, artifact hashes and error/gap. Only reuse matching verified outputs.

Transcript and video failures are independent. `ready_partial` means at least one usable source was imported but a requested capability failed. The overall status cannot become complete because a command exited zero. Retries target a failed stage and retain prior diagnostics. A changed question creates an analysis request within the source snapshot rather than invalidating the original acquisition; changed extraction options invalidate only dependent stages. A refreshed URL creates a new snapshot.

Record the user's question, requested scope and selected source roles so a fresh host knows why the pack exists. Track acquired, presented, reported inspected and cited independently. Inspection remains a model self-report.

## Visual selection and budgets

Keep the core clip bounds: <=300 seconds, <=64 MiB per imported clip, <=12 frames per job. Source acquisition remains <=1 hour and <=256 MiB until a separate change is justified. Use a collection-wide default overview ceiling of 96 frames and a total ceiling of 144 including requested detail, with at most 12 for a very short clip. Enforce remaining budgets before decoding additional candidates.

Overview samples cover the full timeline, including the ending. Scene candidates complement the overview; scene cuts alone miss static settings. User/host-requested timestamps have priority, cannot be silently deduplicated away, and report overflow instead of eviction. Record requested time and actual decoded PTS separately. Record selection reason for every frame.

Contact sheets are navigation artifacts. Their tiles link to evidence IDs, source time and native images; thumbnail viewing does not certify small text. Generate sheets using an optional lightweight image dependency in the media profile, never a hosted renderer. Existing ffmpeg decoding constraints remain intact.

## Documents and optional runtimes

Install only requested profiles: `video`, `documents-basic`, `documents-layout`. Core remains standard-library-only; heavy packages stay in isolated interpreters invoked through JSON argv configuration. Doctor reports actual version, readiness and missing features, not merely executable existence. Installation is a separate explicit operation, not source-triggered.

MarkItDown profile starts with `docx,pptx,xlsx,pdf` extras. The reviewed checkout is prerelease 0.1.8b3, so use its exact commit for the qualification experiment; select and record a release pin only after fixtures pass. Do not silently adopt a mutable branch as a production version.

Docling qualification uses the inspected commit and its locked dependencies. Require an explicitly configured, already-present artifacts directory for layout models. Run with remote services/plugins disabled and offline model settings; test with network blocked, because those flags alone are not a sandbox. OCR defaults off for born-digital text; enable only with an available approved local backend for a source needing OCR. No model download is authorized by this planning request. If weights are absent, exercise the unavailable-capability path and leave live OCR acceptance unproved.

Document budgets: <=64 MiB input, <=200 pages, <=2,000 evidence blocks, <=120 seconds conversion initially. Office archives also require at most 10,000 entries and 256 MiB declared expanded size before converter invocation, plus unsafe-path checks. Enforce actual extraction limits where extraction is used. Where a basic converter cannot report page counts, label that limit unverified rather than claiming enforcement. Do not execute macros or follow external relationships to fetch material. Truncation and skipped pages must be recorded and visible.

## Readable pack and follow-up

The default output contains `index.md`, `answer.md`, `transcript.md` or `document.md`, visual index/sheets when available, source register, observations, gaps, and manifests. File links are relative inside the pack; source links carry video times or document locations. Exports explicitly identify whether originals are included. Default self-contained export includes originals under the existing acquisition budgets; an intentional lightweight export lists omissions and is labelled non-self-contained.

The agent should call prepare, read sections/images, record findings and answer. A `record` convenience command binds annotations to a specific displayed packet and performs the existing small-ticket bookkeeping internally. It cannot claim everything was inspected just because the packet was generated. Unread items require gaps. Existing next/submit remain supported for advanced use.

Supporting sources are selected by the host, at most three directly relevant pages by default. Register them in the root pack with source role and inspected/not-inspected status. Do not recursively ingest video links. Cross-source conclusions cite all necessary sources; existing per-job synthesis contracts are not silently loosened.

## Acceptance and release gates

1. Preserve all current regression tests and copied-skill installation behavior.
2. The 1,122-cue tutorial becomes <=20 text reading packets, with every original cue mapped and no lost words from normalization. Measure packet count rather than promise speed.
3. Simulated media 403 still yields a usable transcript pack; retry does not rerun successful metadata/transcript stages.
4. A brief setting change and a relevant static slide are found by targeted inspection; source PTS and final-scene coverage are tested.
5. DOCX headings, PPTX slide numbers, XLSX sheet identity and simple PDF content survive basic conversion with honest locator labels.
6. Two-column PDF/table/scanned-page fixtures test Docling provenance and visual review; unavailable models produce a clear gap without network downloads.
7. One unfamiliar 20–40-minute tutorial and the document fixture set are exercised through a copied installed skill. Freeze questions first; count interventions and comparable end-to-end time; test an unseen follow-up after restart. No claim of general superiority from this set.
8. Do not call the new routes supported until their relevant live conversion checks pass. Ship basic and layout profiles separately if layout acceptance is blocked by unavailable models.

## Implementation order

First simplify the video workflow and partial recovery. Then introduce the common document import boundary, MarkItDown and optional Docling. Finally validate the single installed skill and update public claims. Keep each milestone independently usable. No dashboard, service, embeddings, multi-agent framework or automatic source-to-skill installation is included.

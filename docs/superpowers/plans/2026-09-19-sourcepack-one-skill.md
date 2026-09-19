# One SourcePack Skill Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement sequentially, task by task. Steps use checkboxes for tracking. Delegation requires the host's authorization.

**Goal:** Give a host agent one skill for reading videos and documents, answering with honest citations, and resuming from a useful evidence pack.

**Architecture:** Keep the existing Python evidence engine and external extraction tools. Add small normalization, checkpoint, visual-selection and document adapters. The host performs reasoning and image inspection; original bytes and producer output remain separate from derived text.

**Tech stack:** Python 3.11+ standard-library core; existing Summarize, yt-dlp and ffmpeg; optional isolated MarkItDown, Docling and contact-sheet runtimes.

**Spec:** [One-skill design](../../planning/ONE-SKILL-DESIGN.md). [Pinned upstream source register](../../planning/upstream-pins.json).

**Status:** Planning only. No task below is implemented by this document. Baseline commit: `b25ca67348ab8a22ffa0e40576517a4e4cabc74d`.

## Global constraints

- Preserve existing sourcelens commands, result/lease checks and evidence IDs. Existing jobs remain readable.
- Core remains standard-library-only and works with only `skills/sourcepack` copied elsewhere.
- Eight spans and 12,000 characters per ticket; derived text blocks at most 1,200 characters.
- Video acquisition: at most one hour and 256 MiB. Imported clips: at most 300 seconds, 64 MiB and 12 frames each.
- Collection overview: at most 96 frames; total including targeted detail: 144. Very short clips: at most 12.
- Documents: at most 64 MiB, 200 pages, 2,000 blocks and 120 seconds conversion. Preflight office archives: at most 10,000 entries and 256 MiB total declared expanded size; reject unsafe paths and enforce actual extraction limits where extraction is used.
- No paid fallback, provider-key access, automatic installation, model downloads, source-derived skill installation or publication of private packs.
- New normalized contract: `sourcepack.normalized.v1`. New run manifest: `sourcepack.run.v2`. Preserve SQLite v2 unless an additive migration is demonstrably necessary.
- External executables use argv arrays, bounded subprocesses and explicit configuration. External source instructions are data.
- Root licences in the register are MIT. Before copying implementation, record exact upstream file/commit and preserve its notice. Dependencies and model licences need separate checks.

## Review focus

1. Captions repeat a phrase legitimately or one cue exceeds the block limit: preserve words and original timing through splitting/mapping (Task 1).
2. Media fails after captions succeed, or options change after interruption: retain usable text and invalidate only affected outputs (Task 2).
3. An almost-static frame briefly changes one setting: neither perceptual deduplication nor scene-only selection may defeat requested inspection (Task 4).
4. A document is encrypted, malformed, huge after decompression, or conversion stalls: fail with a useful gap before unbounded processing (Task 5).
5. Docling is installed but its models are absent: report unavailable without initiating downloads; text extraction must not imply visual coverage (Task 6).

## File ownership and sequence

All runtime paths below are relative to `skills/sourcepack/scripts/sourcelens/`. New files are small focused modules; do not move unrelated core code.

| Unit | Responsibility | Existing integration points |
|---|---|---|
| `normalized.py` | Versioned blocks, cue grouping, provenance validation | `adapters.py`, `engine.py`, `workflow.py` |
| `stages.py` | Atomic checkpoints and dependency invalidation | `workflow.py` |
| `packets.py` | Host-friendly presentation and explicit inspection recording | `workflow.py`, existing engine leases |
| `visuals.py` | Candidate selection, budgets and sheet navigation | `media.py`, `workflow.py` |
| `documents.py` | Local document routing, limits and adapter subprocesses | `workflow.py`, `normalized.py` |
| `document_worker.py` | Optional interpreter entry point for converters | Isolated configured interpreter; imports optional packages lazily |
| `pack.py` | Root source register and portable export | `export.py`, `workflow.py` |

Deliver milestone A after Tasks 1–4: usable video workflow. Deliver milestone B after Tasks 5–7: basic documents and qualified optional layout. Task 8 validates each milestone through the copied skill. Do not hold a working video release for unavailable layout models.

For every task: write behavioral tests first; confirm the expected failure; implement only the described behavior; run its focused test file; inspect the diff and make a scoped commit when commits are authorized. Use this runner, substituting the test filename named in each task:

```sh
PYTHONPATH=skills/sourcepack/scripts python3 -m unittest discover -s tests -p 'test_normalized.py' -v
```

## Task 1: Timed extraction and readable normalized blocks

**Create:** `normalized.py`, `tests/test_normalized.py`.
**Modify:** `workflow.py`, `adapters.py`, `engine.py`, `skills/sourcepack/references/contracts.md`.

**Interfaces:** `group_cues(cues: list[dict], source_sha256: str, max_chars: int = 1200) -> list[dict]`; `validate_normalized(payload: dict, root: Path) -> dict`. A cue has `id`, `start_ms`, `end_ms`, `text`. Blocks have `id`, `kind`, `text`, `source_sha256`, `method`, `locator`, `cue_map`. Each cue-map item preserves cue ID, source timing, source text offsets and block text offsets. Splitting a long cue repeats its timing and maps disjoint text offsets. Separators are derived, identified text.

The payload has `schema`, `source` (relative path, SHA-256, origin), `producer`, `blocks`, `assets`. Every asset has relative path, SHA-256, source SHA-256 and locator. Resolve symlinks under the authorized root, validate hashes and reject unknown source associations. Asset membership does not by itself create an inspected evidence item.

- [ ] Add tests for every cue mapping exactly once except explicitly split ranges; Unicode, long cues, repeated phrases, malformed times, traversal/symlink escape and mismatched hashes. Representative invariant:

```python
blocks = group_cues([
    {'id': 'a', 'start_ms': 0, 'end_ms': 1000, 'text': 'Yes.'},
    {'id': 'b', 'start_ms': 2000, 'end_ms': 3000, 'text': 'Yes.'},
], 'a' * 64)
self.assertEqual([m['cue_id'] for b in blocks for m in b['cue_map']], ['a', 'b'])
self.assertEqual(sum(b['text'].count('Yes.') for b in blocks), 2)
```

- [ ] Run the new tests and confirm missing-interface failures.
- [ ] Add `--timestamps` to pinned Summarize extraction. Preserve producer JSON; validate timed segments before importing. Use original VTT as fallback; preserve raw and current normalized outputs but group losslessly from raw cues. Only remove roll-up overlap when timing and source format establish it; otherwise preserve repetition and label uncertainty.
- [ ] Add an explicit normalized adapter to existing import dispatch, preserving old routes. Use an adapter revision in new job identity. Group into reading sections without increasing engine ticket limits. Images reference individually hashed artifacts and retain their native locator; no whole-document image observation shortcut.
- [ ] Verify a private replay of the 1,122-cue tutorial gives at most 20 text packets. Keep the fixture private; commit synthetic boundary tests only. If the target fails, revise grouping within limits, not test thresholds or the eight-span cap.
- [ ] Run focused tests and existing caption/import regressions. Update the contract reference with a complete synthetic payload example, then review and commit task paths.

## Task 2: Independent acquisition stages and safe resume

**Create:** `stages.py`, `tests/test_stages.py`.
**Modify:** `workflow.py`, `tests/test_workflow.py`, contract reference.

**Interfaces:** `load_run(run: Path) -> dict`; `save_run(run: Path, manifest: dict) -> None`; `stage_reusable(record: dict, options_hash: str, root: Path) -> bool`; `invalidate(manifest: dict, stage: str) -> dict`. Writes use a sibling temporary file and atomic replace. A stage stores dependencies, status, attempts, producer/version, options hash, artifact list and gaps.

- [ ] Add failing tests: media 403 after successful captions, failure during import, interruption before manifest replacement, artifact tampering, extraction options changed, question changed, and v1 query/export compatibility.
- [ ] Implement the spec's stage graph. Metadata feeds video/transcript; video feeds visual-index; imported text/images feed inspection and report. Documents and supporting sources have separate records. Verify successful artifact hashes before reuse; retain earlier error attempts.
- [ ] Add `prepare --question TEXT --detail auto|text|deep`; question changes append analysis requests without redownloading. Add `retry RUN --stage NAME` and explicit `upgrade-run RUN` with retained `run.v1.json`. Refuse incompatible or partial upgrades cleanly.
- [ ] Assert a failed video stage produces `ready_partial` and an available transcript packet. On retry, replace metadata/transcript execution with mocks that raise if called; only the failed stage may run. Assert changes to frame options invalidate visual-index/report, not transcript.
- [ ] Update obsolete tests that require all-or-nothing failure only where the new partial behavior intentionally applies. Preserve failure for zero usable evidence. Run focused stage/workflow tests, review and commit.

## Task 3: One practical reading and recording flow

**Create:** `packets.py`, `tests/test_packets.py`.
**Modify:** `workflow.py`, `skills/sourcepack/SKILL.md`.

**Interfaces:** `present_packet(run: Path) -> dict`; `record_packet(run: Path, packet_id: str, annotations: dict) -> dict`. A packet carries its job/lease identity, exact evidence IDs and content digest. Annotations contain explicitly inspected IDs, observations/citations and gaps for uninspected IDs.

- [ ] Write failing tests for partial inspection, unknown IDs, stale lease, packet tampering, repeated submission and cross-job citations. A packet alone never changes inspection state.
- [ ] Implement `read RUN` as the convenient presentation command and `record RUN ANNOTATIONS.json`. Reuse existing lease/result validation internally. Keep `next` and `submit` unchanged. A record completes one bounded ticket, not arbitrary unseen evidence across jobs.
- [ ] Render transcript sections with source times, document sections with locator labels, and frame entries with native paths and source PTS. Preserve machine-readable JSON alongside Markdown presentation.
- [ ] Test that an uninspected image with a gap remains distinguishable from an inspected/cited image; an unseen evidence ID is rejected. Teach the skill the short prepare/read/open/record/answer flow with one concrete example.
- [ ] Run packet and existing ownership/lease regressions, review and commit.

## Task 4: Bounded visual coverage and navigation

**Create:** `visuals.py`, `tests/test_visuals.py`.
**Modify:** `media.py`, `workflow.py`, setup reference.

**Interfaces:** `select_frames(candidates: list[dict], duration_ms: int, requested_ms: list[int], remaining: int) -> list[dict]`. Candidates contain actual decoded PTS, source offset and selection reason. `write_contact_sheet(frames: list[dict], destination: Path) -> dict` returns sheet/tile metadata through an optional configured image worker.

- [ ] Add failing tests for final-scene coverage, requested-time priority, duplicate requested timestamps, budget overflow, static slide retention, variable frame rate and nonzero clip offset. Synthetic ffmpeg videos exercise decoded PTS; a brief changed setting fixture checks targeted retrieval.
- [ ] Implement overview plus bounded scene candidates, preserving requested moments even when images look similar. Fail explicitly if requests exceed remaining capacity. Limit candidate decoding and cache size as well as retained frames.
- [ ] Apply collection ceilings before creating jobs; preserve core clip/frame limits. Thread configured ffmpeg/ffprobe argv into core media paths so doctor and actual execution agree.
- [ ] Generate optional contact sheets with native-frame links and evidence IDs. Missing sheet support is a navigation gap, not a failed frame extraction. Do not infer small text from thumbnails.
- [ ] Run media/visual tests and exercise one targeted setting manually. Record viewed native image, actual PTS and retrieval result. Review and commit milestone A.

## Task 5: Basic document adapter with MarkItDown

**Create:** `documents.py`, `document_worker.py`, `tests/test_documents.py`, `tests/fixtures/documents/README.md`.
**Modify:** `workflow.py`, setup and contract references.

**Interfaces:** `document_preflight(path: Path) -> dict`; `convert_document(path: Path, output: Path, profile: str, options: dict) -> dict`. The parent calls the optional interpreter with a JSON request file; worker writes producer output and `sourcepack.normalized.v1`, returning output paths and capability gaps as JSON. Never interpolate source paths into shell strings.

- [ ] Add synthetic fixtures/tests for DOCX headings, PPTX slide markers, XLSX sheet identity, simple PDF content, non-ASCII paths and spaces. Add archive expansion, traversal, encrypted/malformed input and timeout cases. Fixtures must be authored for tests, not copied user files.
- [ ] Run failing adapter tests using a fake converter; verify limits apply before invocation. Conversions run in a dedicated output directory and cannot mutate originals.
- [ ] Implement MarkItDown worker with plugins disabled and no LLM client. Use only selected format extras. Preserve converter output verbatim; block locators explicitly say derived section, sheet or verified slide. Do not invent page numbers for text-PDF output.
- [ ] Reject macro-enabled formats initially and do not fetch external relationships. Inspect converter behavior on embedded/linked content with network blocked in qualification; document omissions. Apply input/time/block limits, noting unknown page counts rather than claiming page-limit enforcement where the backend cannot report pages.
- [ ] Qualify the pinned checkout in an isolated optional environment only when dependency setup is authorized and storage allows. Then select an exact tested distribution/commit with dependency lock and record it in `skills/sourcepack/references/runtime-locks/`. No `[all]` install. Keep optional live tests separately labelled from the default stdlib suite.
- [ ] Verify available live conversions, or mark the route implemented but unqualified. Update doctor with actual version/features, run focused tests, review and commit.

## Task 6: Optional Docling layout and OCR

**Modify:** `documents.py`, `document_worker.py`, setup reference.
**Create:** `tests/test_document_layout.py`.

**Interfaces:** `layout_readiness(config: dict) -> dict` returns `ready`, `version`, `artifacts_present`, `ocr_available`, `gaps`. Worker profile `documents-layout` returns native Docling JSON, derived Markdown, referenced page images and normalized blocks with native page/bbox/coordinate origin.

- [ ] Write failing tests for missing model directory, incomplete artifacts, absent OCR backend, preserved table cells/page provenance and unsupported coordinate origins. Fake worker tests establish contracts but do not prove extraction quality.
- [ ] Require explicitly configured existing model artifacts. Disable remote services/external plugins, default OCR off and configure offline behavior. Enforce readiness before constructing a converter, since construction may trigger model work.
- [ ] Qualify with egress blocked: missing weights must fail without download attempts; existing weights may run only when already provisioned/authorized. Keep original native JSON and table representation; associate each rendered page with original source hash and page number.
- [ ] On ready environments inspect two-column, table and scanned-page synthetic fixtures against rendered pages. Test citations recover the correct original item/page. On unavailable environments prove the explicit gap path and leave OCR/layout live acceptance unchecked.
- [ ] Record exact converter/dependency/model identifiers and separate licences. Do not advertise layout/OCR support based on mocks. Run focused tests, review and commit independently of basic documents.

## Task 7: Portable pack, supporting sources and honest answer links

**Create:** `pack.py`, `tests/test_pack.py`.
**Modify:** `export.py`, `workflow.py`, `skills/sourcepack/SKILL.md`, contract reference.

**Interfaces:** `build_pack(run: Path, destination: Path, include_originals: bool = True) -> dict`; `register_supporting_source(run: Path, child_run: Path, role: str) -> dict`. Source register records identity/hash/origin/role and acquired, presented, inspected, cited states independently.

- [ ] Add failing tests for moving an export to another directory, missing acquisition originals, cross-source ID collisions, uninspected companion pages, lightweight omissions and sensitive absolute path leakage.
- [ ] Produce the spec's index, answer, transcript/document, visual index, sources, observations, gaps and manifests. Copy originals within acquisition budgets by default; explicit lightweight mode lists every omission. No symlinks or machine-specific absolute references in exported navigation.
- [ ] Add host-selected companion registration, maximum three by default. Do not traverse outbound video links. Preserve individual job authorization: a root answer may cite observations from separate authorized jobs without issuing an unrestricted multi-job engine synthesis ticket.
- [ ] Validate answer citation references structurally and label semantic judgment as host responsibility. A saved draft answer is not proof of inspected evidence. Test each link resolves after relocation and every cited artifact matches its hash/source.
- [ ] Run pack/export regressions, update public limits to reflect verified routes only, review and commit.

## Task 8: Installed-skill acceptance and release decision

**Create:** `docs/acceptance/one-skill-protocol.md`, synthetic fixture recipes.
**Modify:** `docs/VERIFICATION.md`, `README.md`, setup reference only after results exist.

- [ ] Freeze questions and score rules before acquisition: transcript explanation, visual-only setting, required/optional tool, demonstrated/recommended distinction, document table fact and unseen follow-up. Define supported answer, correct citation, missed detail and manual intervention consistently.
- [ ] Run the full existing suite once after integration:

```sh
PYTHONPATH=skills/sourcepack/scripts python3 -m unittest discover -s tests -v
```

- [ ] Install to a fresh temporary skills directory using `scripts/install.py`; run outside the repository with no repository imports. Prove text works without optional profiles and doctor reports missing routes honestly.
- [ ] Use an unfamiliar 20–40-minute tutorial and the document fixtures. Preserve private evidence outside Git. Measure prepare/read/record actions, packet count, elapsed time, extraction failures, retries and observable host usage; unknown costs stay unknown.
- [ ] Interrupt after some observations, resume in a fresh host context, ask the frozen visual follow-up and recover the supporting native frame. Move the exported pack and verify citations remain usable.
- [ ] Compare equal evidence and questions against direct tools on the same host/model. Report acquisition versus analysis time separately. No accuracy claim from source inspection or a one-case win. Do not reuse answers across isolated runs.
- [ ] Release milestone A only if grouping, partial resume and follow-up gates pass. Release basic document routes only after real conversions pass. Layout remains optional/unqualified if existing models cannot support its live checks.
- [ ] Inspect final diff/status, preserve unrelated edits, update verification with passed/failed/not-attempted rows, and publish only reviewed code/docs when authorized. Keep user evidence, absolute machine paths and runtime secret configuration private.

## Completion checklist

- [ ] One entrypoint, two source workflows, existing host reasoning.
- [ ] Original evidence and versioned normalization remain distinguishable.
- [ ] Useful partial results, stage-specific recovery and readable packets proven.
- [ ] Native visual/document locations survive export and follow-up.
- [ ] Optional dependencies remain optional; no silent downloads or paid calls.
- [ ] Public claims match actual installed-skill evidence.

**Recommendation:** Build milestone A first. Its value addresses demonstrated friction in the existing skill. Then add MarkItDown; qualify Docling only where layout/OCR adds evidence the basic route cannot preserve. Import selected behaviors through adapters rather than installing seven overlapping orchestrators.

# Contracts and limits

- `run.json`: sourcepack.run.v2 for new runs; v1 remains readable. Identity includes original local path and content hash, or public source URL. A ready run returns its cached source snapshot. Use a new run directory to refresh a changing URL.
- Engine jobs/tickets and existing results retain v1 contracts; selected inspections emit host-result v2 as specified below. SQLite stays at user_version 2. SourcePack workflow version 0.4.0 wraps the core.
- YouTube: one finite watch URL, at most one hour; English captions only in the automatic path; video-only MP4 <=720p and <=256 MiB. No playlist expansion, authentication, cookies, ASR or paid extraction.
- Each imported clip stays <=300 seconds and <=64 MiB. Keyframe-aligned splitting can exceed the intended 240-second window; such clips fail explicitly rather than bypassing core limits.
- Jobs are independent within a collection. Query searches each job; cross-job synthesis is done in the host answer with explicit source citations, not represented as one engine-certified synthesis. The existing core supports bounded synthesis within a job.
- `next` supplies at most eight spans under the core's text budget. A successful submission validates ownership, lease, IDs and literal quotes. It does not prove semantic accuracy or actual image viewing.
- Collection export contains imported source bytes, observations and relative artifact links, plus a manifest. Retain the run directory for original metadata, raw captions, full downloaded rendition and acquisition logs.
- New runs and exports are private directories. URLs, local source paths, extractor logs and provider-returned metadata may contain sensitive data. Review before sharing. They are never intended as public repository contents.
- Source URL admission rejects credentials and currently resolved private IPs. This is not a subprocess network sandbox or a guarantee against DNS rebinding/redirects. Summarize handles its own network policy; only use public uncredentialed sources with this helper. HTML/script content is never executed by the evidence parser.
- Extraction is model-free in the configured route; the host's analysis may use cloud inference. Local evidence storage does not mean local inference. Monetary cost is unknown unless independently observed.
- Each successful acquisition stage is hashed before ingestion. Failed acquisition attempts keep logs; retry may repeat downloads. Ingestion resumes idempotently. Process locks release when a process exits. Do not run two writers against one run.

For advanced core commands, run `python3 SKILL_DIR/scripts/sourcelens_cli.py --help`. Select the collection's `RUN/state` and `RUN/acquired` explicitly. No task cancellation, migration rollback or file cleanup occurs automatically.

## Derived imports and stage-aware runs

New runs use `sourcepack.run.v2`; v1 remains readable, and `upgrade-run` preserves a copy before resuming acquisition. Independent stage receipts include options hashes, artifact hashes, attempts and explicit failures. `ready_partial` permits inspection of available evidence.

`sourcepack.normalized.v1` imports associate bounded blocks with an original file hash and optional hashed assets. Transcript blocks preserve child cue IDs, source times and text-offset maps. Originals are retained as source artifacts. This importer validates byte association, not semantic fidelity. Legacy adapters and evidence IDs remain unchanged.

Normalized source records use `source: {path, sha256, origin}`, `producer`, `blocks` and `assets`. Paths resolve relative to the payload directory within the authorized input root. Each block includes `id`, `kind`, bounded `text`, `method`, `source_sha256` and `locator`. Transcript `cue_map` items map original cue text offsets to block offsets without dropping repeated words. Hashed assets retain their own locator and source association. Images must be individually inspected; native page coordinates retain their producer coordinate basis.

`read` returns a `packet_id` bound to the full engine ticket, including lease identity. `record` accepts only `inspected_ids`, `observations` and `gaps`; it delegates to existing result validation. Each unread assigned item needs a gap. A source registered in the root collection is not authorization to cite its uninspected evidence.

## Compact review and selective findings

`inspect` emits `sourcepack.review.v1`: an opaque review ID and two generated reading/index files. The ID binds source identity, original spans/artifact hashes and the rendered reading content. It grants no inspection credit. The derived view collapses overlapping or rapid adjacent rolling caption updates; originals, span IDs and child cue maps are not edited. Cleaned text is not a verbatim quotation source.

`finish` accepts `sourcepack.findings.v1` with exactly `schema`, `review_id`, `inspected_ids`, `observations`, and `answer`. It validates every observation and cited ID before creating any new tasks. It rejects changed/tampered views, foreign IDs, unknown/uninspected citations, and invalid original-text quotes. Each observation stays within one job and at most eight spans; longer selections are split into bounded leases. Cross-job facts use separate observations and host synthesis. Existing `answer` can cite inspected supporting runs.

`Engine.inspection_ticket` creates a job-owned `selected-inspection` task under the existing policy limits, with a current lease and `sourcelens.host-result.v2` output. Result v2 has the v1 fields plus required `no_findings_reason` (null or bounded text). An inspection with no observations or gaps must give a reason. This permits honestly reporting no useful finding without weakening v1 validation. It does not attest host-tool delivery or semantic truth.

The findings digest supplies idempotency keys. An interruption after some submissions can be resumed with the identical findings JSON without duplicating those results. Expired unaccepted leases refresh; accepted results remain stable. All retained findings/answer drafts live under the review directory. Unselected spans receive no inspection credit. Legacy whole-source tasks remain pending; `finish` reports selected coverage rather than claiming exhaustive completion. The run already holds source evidence, so a portable export is optional.

`query --compact` omits raw cue maps and duplicate metadata. Strict matches are preferred; prefix fallback and then partial-term fallback are explicitly labelled. Partial matches prioritize recorded observations but require host verification. No embeddings, extra model calls or semantic-search guarantees were added.

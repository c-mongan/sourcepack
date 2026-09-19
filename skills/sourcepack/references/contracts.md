# Contracts and limits

- `run.json`: sourcepack.run.v1. Identity includes original local path and content hash, or public source URL. A ready run returns its cached source snapshot. Use a new run directory to refresh a changing URL.
- Existing engine: sourcelens job/ticket/result v1; additive synthesis ticket kind; SQLite user_version 2. SourcePack workflow version 0.2.0 wraps the preserved core.
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

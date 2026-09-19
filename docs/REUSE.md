# Reuse decisions

SourcePack wraps tools, rather than copying whole repositories or loading every skill's instructions into one context. External repositories and source-derived skills are evidence during research, not trusted runtime instructions.

| Project | Decision |
|---|---|
| [Summarize](https://github.com/steipete/summarize) | Invoke a tested release for web/caption extraction. Keep its broad command guide upstream; our code sets only the evidence-preserving route and provider restrictions. |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org/) | External dependencies for captions, metadata, video acquisition and timestamp-preserving frame extraction. |
| [claude-video/watch](https://github.com/bradautomates/claude-video) | Reviewed its caption-first workflow, targeted-frame interface and frame timing code. Good alternative for ordinary video Q&A. Not an added dependency: our existing decoder already retains original PTS and evidence IDs; adopting both would duplicate acquisition. No watch code copied. |
| [timharris707/ingest](https://github.com/timharris707/skills/tree/main/skills/investigate/ingest) | Prior art for persistent evidence packets and resume. Its purpose interview, tracker routing and cleanup policy are intentionally not inherited. No code copied. |
| [source-to-skill](https://github.com/michalstrnadel/source-to-skill) | Converts extracted knowledge into skills. Potential explicit downstream output, not a prerequisite for evidence inspection. |
| [Skill Seekers](https://github.com/yusufkaraaslan/Skill_Seekers) | Rich structured extraction candidate. Deferred until a source type or measured quality gap requires it. |
| [Docling](https://github.com/docling-project/docling), [MarkItDown](https://github.com/microsoft/markitdown) | Document adapter candidates. Not installed or advertised as integrated. |
| [Crawl4AI](https://github.com/unclecode/crawl4ai), [Jina Reader](https://github.com/jina-ai/reader), [Firecrawl](https://github.com/firecrawl/firecrawl) | Alternative web routes. Use the host's existing retrieval tools first; no mandatory crawl service or paid fallback. |
| [Hermes youtube-content](https://github.com/NousResearch/hermes-agent/tree/main/skills/media/youtube-content) | Prior transcript-helper review; not a runtime dependency. |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | Optional future local transcription, after device-specific inference testing. No model downloads in this release. |

Review scope: selected documentation and source paths, not exhaustive audits or runtime validation of every candidate. Summarize/yt-dlp/ffmpeg were exercised; deferred adapters were not. Mutable upstream links are references, not dependency pins. No external skill implementation is vendored. Dependency licences remain their authors' licences.

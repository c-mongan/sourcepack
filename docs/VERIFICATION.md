# Verification — 19 September 2026

This is a tested early release, not a general benchmark or a promise to understand every source.

## Local tests

`PYTHONPATH=skills/sourcepack/scripts python3 -m unittest discover -s tests -v`

47 tests passed on macOS with Python 3.14.6 and installed ffmpeg/ffprobe. This includes the 38 inherited core/regression tests and nine workflow tests. Coverage includes source identity, tampering rejection, resumed ingestion, provider-environment isolation, failed acquisition state, per-install tool paths, evidence/observation retrieval and original-time focus clips. Media tests used real local synthetic video. One inherited test fixture emits a non-failing SQLite ResourceWarning; it is not evidence of production acceptance.

The skill frontmatter validator passed. GitHub Actions runs the local suite on Python 3.11/3.13 with ffmpeg; consult the repository's Actions results for hosted status rather than inferring it from local tests.

## Independent copied-skill run

A separate host agent used a copied skill folder outside this repository and invoked helpers from an unrelated working directory. It processed a public roughly 19-second YouTube video:

- Read all six available English caption spans.
- Opened all 12 extracted native frames.
- Submitted five observations across three tickets.
- Started a fresh helper process, queried an animal-related visual term, retrieved its original frame at 3.2 seconds, and reopened it.
- Exported the private evidence collection.

The tested skill did not need the original checkout. No acquisition route failed for this short video. The tester used an explicit Summarize executable override and existing yt-dlp/ffmpeg. Two test-harness mistakes were corrected: a relative result filename from a different working directory, and a hash comparison against concurrently updated product files. These were not hidden as zero-intervention success.

During that run, a separate webpage test exposed a Summarize flag incompatibility. After the helper changed to non-LLM `readability` conversion, the tester refreshed the copied helper and repeated fresh video acquisition. Caption/video bytes matched the original run; semantic work was not redundantly repeated. The observed 228-second scope included the original analysis and requested acquisition rerun, excluded initial setup/final report writing, and is not a speed comparison. No continuous motion or independent audio analysis was performed.

## Live webpage run

The Python.org executive-summary page was acquired through Summarize 0.22.0. The original `--format md --markdown-mode off` combination failed for the website route despite working on the earlier YouTube case. Its failure log was retained privately. The corrected `readability` route acquired substantive prose, an interactive-script fallback notice and navigation. The host read all extracted text, attributed claims to the page, recorded the fallback limitation, and tested later observation retrieval and export.

This does not prove raw HTML preservation or embedded-image understanding. The helper saves extractor JSON; it reports that distinction.

## Prior longer case

The evidence core was previously exercised on a 35-minute tutorial with 132 sampled frames, full available captions, companion notes and current official documentation. Direct tools and tools plus SourcePack both scored 12/12 on a coarse selected-claim rubric. SourcePack demonstrated process resume and visual observation retrieval, not better answer accuracy, measured cost savings or faster analysis. That experiment motivated this smaller skill.

## Local installation smoke

The installer copied the skill into Codex discovery with private, per-install executable paths. Summarize 0.22.0 and yt-dlp 2026.08.19 were verified from isolated local tool directories, without changing global versions. The installed helper, invoked from an unrelated working directory with no task-specific environment override, acquired a fresh Example Domain page successfully. This proves the configured local installation route; a new host session must discover the skill.

## Not established

- General semantic accuracy, exhaustive visual recall or independently verified transcripts.
- Full end-to-end operation in hosts other than Codex, or on Windows.
- Automatic document/ASR adapters, paid/authenticated extraction or arbitrary source support.
- Recovery of unsaved host reasoning; only persisted acquisition and inspection work is resumable.
- Network sandboxing or prevention of every external-tool redirect/DNS behavior.
- Public rights to captured media. Tests and reports in this repo contain no captured user evidence.

All analysis evidence, local machine paths and raw receipts remain outside the published repository. No model downloads or paid extraction were used.

## 0.3 implementation and evaluation

See [2026-09-19 qualification results](acceptance/2026-09-19-results.md) for the current regression, real document-conversion, paired answer and fresh-context retrieval evidence. The paired pilot found equal selected-answer quality and higher SourcePack elapsed time; no general accuracy or speed advantage is claimed. Docling remains disabled pending offline model qualification.

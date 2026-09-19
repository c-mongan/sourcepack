# SourcePack

**Give your coding agent a source. Get an explanation you can check and return to.**

SourcePack is an installable skill for inspecting YouTube videos, public webpages and local text. It coordinates existing extraction tools, asks the host agent to read the text and inspect video frames, and saves observations against their original evidence.

```text
“Use SourcePack to explain this tutorial. Check the settings shown on screen,
compare the relevant official docs, and tell me what is demonstrated versus assumed.”
```

The host does the reasoning. Summarize, yt-dlp and ffmpeg handle extraction. A small local Python core preserves citations, pending work and searchable observations. No model service, daemon, vector database or hosted account is required by SourcePack itself.

## Install

Requires Python 3.11+ on macOS/Linux and a coding agent with file, shell and image-reading tools.

```sh
git clone https://github.com/c-mongan/sourcepack.git
cd sourcepack
python3 scripts/install.py --skills-dir ~/.codex/skills
```

For other skill-compatible agents, choose their skill directory, such as `~/.agents/skills`. The installer copies one self-contained folder and refuses to overwrite an existing installation. Reload skill discovery or start a new agent session, then ask it to use **SourcePack**. Cross-host behavior beyond Codex has not been validated.

Install extraction dependencies separately:

- **Web:** [Summarize](https://github.com/steipete/summarize), tested with `@steipete/summarize@0.22.0` and Node >=24.
- **YouTube:** [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg/ffprobe](https://ffmpeg.org/), plus Summarize as the first transcript candidate.
- **Local UTF-8 text:** no external Python packages or media tools.

The skill performs a readiness check and reports missing capabilities. It does not auto-install software, buy credits, download models or change provider settings. [Setup and executable overrides](skills/sourcepack/references/setup.md).

## What a run does

1. Preserve acquired originals and extractor diagnostics; normalize captions separately.
2. Read all available text in bounded batches.
3. Inspect sampled video frames; request closer windows where a setting or claim needs proof.
4. Inspect a small number of relevant companion pages or official docs using the host.
5. Explain findings with timestamps, source locations and explicit gaps.
6. Save observations so a later search can retrieve the supporting text or original frame.

If interrupted, repeat the preparation command and resume pending inspection tickets. A downloaded source is not automatically marked understood. The host records what it actually inspected; uninspected material remains a gap.

## Direct helper use

```sh
python3 skills/sourcepack/scripts/sourcepack.py doctor
python3 skills/sourcepack/scripts/sourcepack.py prepare ./notes.md --out /tmp/my-sourcepack-run
python3 skills/sourcepack/scripts/sourcepack.py next /tmp/my-sourcepack-run
# The host reads/opens the supplied evidence, fills the returned result_template,
# and saves result.json before submitting it.
python3 skills/sourcepack/scripts/sourcepack.py submit /tmp/my-sourcepack-run ./result.json
python3 skills/sourcepack/scripts/sourcepack.py query /tmp/my-sourcepack-run "retry limit"
python3 skills/sourcepack/scripts/sourcepack.py export /tmp/my-sourcepack-run /tmp/my-sourcepack-export
```

Choose a new output directory for each source or refreshed snapshot. Reusing the same source/run resumes the saved snapshot. The existing `sourcelens` CLI remains available through `skills/sourcepack/scripts/sourcelens_cli.py`; pip installation is optional.

## Scope and honest limits

This is an early, skill-first release. YouTube supports one finite watch URL up to one hour, English captions, and a video-only MP4 rendition up to 720p/256 MiB. Clips remain under the core's five-minute/64 MiB bounds. Keyframe alignment can cause a clip to exceed those bounds; that fails explicitly. Frame inspection is sparse and can miss brief events.

Public webpages use saved extractor output rather than original HTML snapshots. Local text supports `.txt`, `.md`, `.html`, `.htm`, `.vtt` and `.srt`. PDFs, office files, arbitrary media, playlists, authenticated pages and automatic ASR are not integrated. The host can use existing tools for those sources, but the helper does not claim support.

Search is lexical. Observations and image inspection are model self-reports. The core checks ownership and citation structure; it cannot certify semantic truth. SourcePack controls no host model billing. Local storage does not imply local inference. Source URL checks are not a network sandbox.

Runs contain private evidence and possibly sensitive URLs/paths. Keep them outside this repository. Exported source packs also remain private by default; retain the run for acquisition originals and logs.

## Why this exists

A first 35-minute tutorial case found equal selected-answer scores with and without the evidence layer. It did show process-resume and frame-backed retrieval working. That supports a small reusable skill, not a claim of superior reasoning. The next test is whether the complete skill reduces repeated orchestration work. [Verification and limitations](docs/VERIFICATION.md).

## Development

```sh
PYTHONPATH=skills/sourcepack/scripts python3 -m unittest discover -s tests -v
```

Media tests need ffmpeg/ffprobe; otherwise they skip explicitly. Tests use local synthetic fixtures and temporary files, not user evidence. No model/API calls occur in the default suite.

[Reuse decisions](docs/REUSE.md) · [Design](docs/DESIGN.md) · [Contracts](skills/sourcepack/references/contracts.md) · [MIT licence](LICENSE)

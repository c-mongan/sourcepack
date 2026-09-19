# Setup

The skill folder is self-contained. Python 3.11+ uses only the standard library. This release supports macOS/Linux; Windows locking is not implemented.

External tools are optional by route:

| Route | Dependencies |
|---|---|
| Local UTF-8 text/Markdown/HTML/VTT/SRT | Python |
| Public web extraction | Summarize |
| YouTube captions and video | yt-dlp, ffmpeg, ffprobe; Summarize is attempted first |

Tested extraction version: `@steipete/summarize@0.22.0`. It requires Node >=24. Check actual `node --version`, not the executable's directory name. Install separately when authorized, for example `npm install -g @steipete/summarize@0.22.0`. Tool installations are never run automatically by this skill. Follow official yt-dlp/ffmpeg installation instructions for your machine. YouTube extractor behavior changes; retain the failing version/route and retry a reviewed newer version when needed.

An existing executable on PATH is preferred. Optional environment overrides are JSON argv arrays (no shell evaluation):

```sh
export SOURCEPACK_SUMMARIZE='["/absolute/node", "/absolute/summarize/dist/cli.js"]'
export SOURCEPACK_YT_DLP='["/absolute/python", "/absolute/yt-dlp/__main__.py"]'
```

Other supported overrides: `SOURCEPACK_FFMPEG`, `SOURCEPACK_FFPROBE`. The core video decoder currently requires ffmpeg/ffprobe on PATH, even when the acquisition override is used.

The helper gives extractors only PATH, LANG, SYSTEMROOT, TMPDIR and NO_COLOR. It does not pass HOME, provider keys, cookies, shell configuration or ambient Summarize settings. yt-dlp uses `--ignore-config`. Summarize's web-caption route and disabled preprocessing/cloud fallbacks are explicit. For sources lacking captions, this release does not automatically invoke ASR.

The user still needs a host capable of opening images to inspect video. Doctor reports binary availability, not semantic readiness or provider success.

For a durable per-install override, create a local JSON file mapping `summarize`, `yt-dlp`, `ffmpeg` or `ffprobe` to argv arrays. Pass `--tool-config FILE` to the installer. It writes `scripts/tool-paths.json` in the installed skill only; keep machine paths out of the repo. Environment overrides take precedence. Treat this file as trusted executable configuration, never as source material.

## Optional documents

The core has no Python package dependencies. Configure a separate interpreter in the private `scripts/tool-paths.json`:

```json
{"documents-basic":{"argv":["/absolute/path/to/document-venv/bin/python"]}}
```

The qualification build used Microsoft MarkItDown commit `945314a45ddbe02935f2fd287b797dc0ba4a01e4` (0.1.8b3), with only `docx,pptx,xlsx,pdf` extras. To reproduce in a user-authorized isolated environment:

```sh
python3 -m venv /your/path/document-venv
/your/path/document-venv/bin/python -m pip install 'markitdown[docx,pptx,xlsx,pdf] @ git+https://github.com/microsoft/markitdown.git@945314a45ddbe02935f2fd287b797dc0ba4a01e4#subdirectory=packages/markitdown'
```

The [qualification dependency snapshot](runtime-locks/markitdown-macos-py312.txt) records the tested macOS arm64/Python 3.12 environment; it is not a universal cross-platform lock or a claim that an unreleased build is stable. The upstream Magika file-type classifier comes bundled with its dependency package. SourcePack performs no separate model download or LLM inference. Python network connections are denied in the conversion worker; this is defense in depth, not an operating-system sandbox.

`doctor` probes versions and configured profiles. `prepare FILE --out RUN` routes PDF/DOCX/PPTX/XLSX to the basic profile. Scans with no text produce a capability error. Unknown page coordinates are never invented. DOCX uses derived section locations, PPTX verified producer slide markers, XLSX sheet headings, and basic PDF derived sections. Images embedded in office files are not claimed visually inspected.

### Experimental layout adapter

`--document-profile documents-layout` is a separate optional route. It requires a Docling interpreter and explicitly pre-provisioned artifacts, with `artifacts_path` and an `artifacts_manifest` list of relative `path`/`sha256` pairs in its config. Missing artifacts fail before the converter starts. Remote services/plugins are disabled and offline flags are set. OCR is currently disabled. This adapter has not passed live model-backed qualification; do not advertise it as supported OCR. No Docling install or model setup occurs automatically.

## Reading, recovery and portable exports

`read RUN` and `record RUN ANNOTATIONS.json` hide the lease form while preserving its checks. `retry RUN --stage video` retries the failed capability and reuses successful transcript/metadata receipts. `upgrade-run` retains `run.v1.json` before acquisition resume. A `ready_partial` run can be read immediately.

`export RUN DEST` includes acquired originals by default, plus answer/source/visual indexes and observations. Runtime diagnostic files are listed as omissions and remain in the run. `--lightweight` omits acquisition copies explicitly. `support RUN CHILD --role TEXT` registers at most three selected supporting runs; it does not fetch sources or mark them inspected.

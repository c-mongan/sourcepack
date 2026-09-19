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

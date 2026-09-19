# Skill-first release
Approved scope: one source-inspection skill, tested acquisition helpers and existing evidence core. YouTube, public webpages, local UTF-8 text. The existing host reads and reasons; no nested inference runner.

Public interface: doctor; prepare SOURCE --out RUN; next RUN; submit RUN RESULT; query RUN TEXT; focus RUN START END; export RUN DESTINATION. Runs persist original extraction output, source metadata/captions, bounded clips, SQLite observations and gaps. Each clip uses the existing five-minute core limit and original decoded timestamps. The skill is self-contained and copied as one folder. External tools are dependencies, not vendored code. Public repo excludes all acquired media, local state, personal paths and private case reports.

Acceptance: legacy tests plus acquisition/resume/failure tests; copied-skill smoke test; fresh-source host analysis; frame-backed follow-up; public tracked-file review and GitHub readback. Exact semantic quality and costs remain unverified beyond observed cases.

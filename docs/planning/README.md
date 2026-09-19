# SourcePack reuse review and next build

Seven upstream repositories were cloned at fixed commits and selected source files reviewed. This is a design/implementation plan, not a claim that new adapters are already working.

- [Design and reuse decisions](ONE-SKILL-DESIGN.md)
- [Executable implementation plan](../superpowers/plans/2026-09-19-sourcepack-one-skill.md)
- [Repository pins and inspected source links](upstream-pins.json)

Build one skill with video and document workflows. First fix transcript packet size and partial recovery; then add MarkItDown for basic documents and optional Docling for richer PDF structure. Keep existing extractors and the host's reasoning. Avoid bringing in entire overlapping frameworks.

The inspected upstreams are Summarize, claude-video, timharris707/skills, Skill Seekers, source-to-skill, Microsoft MarkItDown and Docling. The source register records exact commits, inspected files and licence scope. No third-party implementation was copied in this planning pass, no converters installed and no models downloaded.

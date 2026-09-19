#!/usr/bin/env python3
"""Copy the self-contained skill into an explicit host skill directory."""
import argparse
from pathlib import Path
import shutil
import json
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--skills-dir',required=True,help='Host discovery directory, e.g. ~/.codex/skills')
p.add_argument('--tool-config',help='Optional local JSON object mapping tool names to argv arrays')
a=p.parse_args(); source=Path(__file__).resolve().parents[1]/'skills/sourcepack'
target=Path(a.skills_dir).expanduser()/'sourcepack'
if target.exists() or target.is_symlink():p.error(f'Refusing to overwrite existing skill: {target}')
config=None
if a.tool_config:
    config=json.loads(Path(a.tool_config).expanduser().read_text())
    if not isinstance(config,dict) or set(config)-{'summarize','yt-dlp','ffmpeg','ffprobe'}:
        p.error('Unsupported tool configuration')
    if any(not isinstance(v,list) or not v or any(not isinstance(x,str) or not x for x in v) for v in config.values()):
        p.error('Tool commands must be nonempty argv arrays')
shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc','tool-paths.json'))
if config is not None:
    path=target/'scripts/tool-paths.json';path.write_text(json.dumps(config,indent=2));path.chmod(0o600)
print(target)

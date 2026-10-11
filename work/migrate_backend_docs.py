"""Consolidate backend documents without selecting by modification date."""
import hashlib
import json
from pathlib import Path
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
writes, moves, comparisons = {}, {}, []
for source in sorted((ROOT/'backend/docs').rglob('*.md')):
    relative = source.relative_to(ROOT).as_posix()
    name = source.name
    if source.parent.name == 'message_interface_allocation':
        group = 'domains/communication/message_interface_allocation'
    elif any(word in name for word in ('AGENT', 'AI_', 'KNOWLEDGE', 'RAG', 'DATA_INGESTION')):
        group = 'domains/agent' if 'AGENT' in name or name.startswith('AI_') else 'domains/knowledge'
    elif any(word in name for word in ('SIMULATION_ENGINE', 'SIMULATION_INTERFACE', 'SIGNAL_EMULATION')):
        group = 'domains/simulation'
    elif name in {'CURRENT_STATUS.md', 'IMPLEMENTATION_STATUS.md'}:
        group = 'archive/backend-status'
    else:
        group = 'domains/engineering'
    target = ROOT/'docs'/group/name
    text = source.read_text(encoding='utf-8-sig')
    if target.exists():
        same = target.read_text(encoding='utf-8-sig') == text
        comparisons.append({'source': relative, 'existing': target.relative_to(ROOT).as_posix(), 'identical': same})
        if not same:
            target = target.with_name('backend-' + name)
            if target.exists():
                raise RuntimeError(f'Needs reconciliation: {target}')
    def relocate_link(match):
        path = match[1]
        if ':' in path or path.startswith(('#', '/')):
            return match[0]
        file, separator, anchor = path.partition('#')
        original = (source.parent/file).resolve()
        return '](' + os.path.relpath(original, target.parent).replace('\\', '/') + (separator+anchor if separator else '') + ')'
    relocated = re.sub(r'\]\(([^\s)]+)\)', relocate_link, text)
    target_rel = target.relative_to(ROOT).as_posix()
    writes[target_rel] = relocated
    link = os.path.relpath(target, source.parent).replace('\\', '/')
    writes[relative] = f'# Document moved\n\nCanonical document: [{name}]({link}).\n\nThis entry preserves old links during the structure migration.\n'
    moves[relative] = target_rel
out = ROOT/'docs/implementation-workloads/project-structure-migration-20261003/docs-migration-plan.json'
out.write_text(json.dumps({'writes':writes,'moves':moves,'content_comparisons':comparisons},indent=2),encoding='utf-8')
subprocess.run([sys.executable,str(ROOT/'work/structure_guard.py'),'--plan',str(out)],check=True)
for relative, content in writes.items():
    path=ROOT/relative
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(content,encoding='utf-8')
print(json.dumps({'documents_moved':len(moves),'comparisons':comparisons}))

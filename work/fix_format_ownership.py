"""Bind flat format imports to canonical owners and retain executable old CLIs."""
import ast
import json
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
aliases=json.loads((ROOT/'backend/nis/compatibility.json').read_text())
flat={old.rsplit('.',1)[1]:new for old,new in aliases.items() if old.startswith('backend.simulator.format_generators.')}
writes={}
for source in (ROOT/'backend/nis').rglob('*.py'):
    text=source.read_text(encoding='utf-8-sig')
    for name,target in flat.items():
        text=re.sub(r'(?m)^(\s*from\s+)'+re.escape(name)+r'(\s+import\s+)',lambda m:m[1]+target+m[2],text)
    if source.name == 'communication_generator.py':
        start=text.index('def add_format_generators_to_path()')
        end=text.index('\ndef package_output_path',start)
        text=text[:start]+'def add_format_generators_to_path() -> None:\n    """Retained API; canonical format modules need no sys.path modification."""\n    pass\n\n'+text[end:]
    if '__main__' in text and 'if __name__' in text:
        tree=ast.parse(text)
        insert=max([n.end_lineno for n in tree.body if isinstance(n,ast.ImportFrom) and n.module=='__future__'] or
                   ([tree.body[0].end_lineno] if isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant) else [0]))
        lines=text.splitlines(keepends=True)
        lines.insert(insert,'\n# Direct file entrypoints resolve the installed/source package independently of cwd.\n'
                     'import sys as _cli_sys\nfrom pathlib import Path as _CliPath\n'
                     '_cli_backend = next(p for p in _CliPath(__file__).resolve().parents if p.name == "backend")\n'
                     '_cli_sys.path.insert(0, str(_cli_backend.parent))\n')
        text=''.join(lines)
    if text!=source.read_text(encoding='utf-8-sig'):
        writes[source.relative_to(ROOT).as_posix()]=text
for old,target in aliases.items():
    actual=ROOT/(target.replace('.','/')+'.py')
    if not actual.is_file() or 'if __name__' not in actual.read_text(encoding='utf-8') or '__main__' not in actual.read_text(encoding='utf-8'):
        continue
    previous=ROOT/(old.replace('.','/')+'.py')
    if not previous.is_file():continue
    writes[previous.relative_to(ROOT).as_posix()]=(
        f'"""Compatibility entrypoint; owner {target}."""\n'
        'import importlib\nimport sys\nfrom pathlib import Path\n'
        'sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if p.name == "backend").parent))\n'
        'if __name__ == "__main__":\n    import runpy\n'
        f'    runpy.run_module({target!r}, run_name="__main__")\n'
        'else:\n'+f'    sys.modules[__name__] = importlib.import_module({target!r})\n')
out=ROOT/'docs/implementation-workloads/project-structure-migration-20261003/format-ownership-plan.json'
out.write_text(json.dumps({'writes':writes},indent=2),encoding='utf-8')
subprocess.run([sys.executable,str(ROOT/'work/structure_guard.py'),'--plan',str(out)],check=True)
for relative,text in writes.items():(ROOT/relative).write_text(text,encoding='utf-8')
print(json.dumps({'files_corrected':len(writes)}))

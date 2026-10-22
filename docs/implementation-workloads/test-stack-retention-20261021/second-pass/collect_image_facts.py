"""Read immutable image source inventories without launching the application."""
import importlib.util
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('previous_cleanup', OUT.parent / 'audit_cleanup.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
prior.OUT = OUT
CODE = r'''
import hashlib,json,pathlib
root=pathlib.Path('/app')
manifests={}
for name in ('backend/nis/app/build-info.json','backend/app/build-info.json','frontend/public/build-info.json'):
 p=root/name
 if p.is_file():
  try:manifests[name]=json.loads(p.read_text())
  except ValueError:pass
paths=set()
for folder in ('backend','frontend/src','frontend/scripts','config','scripts'):
 for p in (root/folder).rglob('*'):
  if not p.is_file() or {'.venv','node_modules','test-output','tests','__pycache__','runtime','generated','build'}.intersection(p.relative_to(root).parts):continue
  if p.suffix not in ('.py','.json','.tsx','.ts','.mjs','.js','.css','.toml','.yaml','.yml'):continue
  if '.test.' in p.name or p.name=='build-info.json':continue
  paths.add(p)
hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in sorted(paths)}
print(json.dumps({'manifests':manifests,'files':hashes}))
'''

data = json.loads((OUT / 'resolved-images.json').read_text())
(OUT / 'source-facts').mkdir(exist_ok=True)
for image in sorted(data['images'], key=lambda row: row['created'], reverse=True):
    target = OUT / 'source-facts' / (image['id'].split(':')[1] + '.json')
    if target.exists():
        continue
    result = subprocess.run([prior.DOCKER, 'run', '--rm', '--network', 'none', '--read-only',
                             '--entrypoint', 'python', image['id'], '-S', '-c', CODE],
                             text=True, encoding='utf-8', capture_output=True)
    if result.returncode:
        raise RuntimeError('Read-only image facts failed for ' + image['tags'][0] + ': ' + result.stderr[:500])
    facts = json.loads(result.stdout)
    target.write_text(json.dumps({'image': image['id'], 'tags': image['tags'], **facts}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'image': image['tags'][0], 'files': len(facts['files']),
                      'sources': sorted(set(r.get('source_sha256', '') for r in facts['manifests'].values()))}), flush=True)

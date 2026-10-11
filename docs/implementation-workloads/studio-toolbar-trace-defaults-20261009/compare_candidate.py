import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
code = '''import importlib.util,json,hashlib
from pathlib import Path
spec=importlib.util.spec_from_file_location('buildinfo','scripts/build/write-build-info.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
original=Path.read_bytes
hashes={}
def read(path):
 data=original(path)
 hashes[path.relative_to(module.ROOT).as_posix()]=hashlib.sha256(data.replace(b'\\r\\n',b'\\n')).hexdigest()
 return data
Path.read_bytes=read
manifest=module.build_manifest()
print(json.dumps({'manifest':manifest,'files':hashes}))
'''
host = json.loads(subprocess.check_output([sys.executable, '-c', code], cwd=root, text=True))
config = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))
candidate = json.loads(subprocess.check_output([config['paths']['docker_cli'], 'run', '--rm', '--entrypoint', 'python',
    'networkis:candidate-fc5d3079141e', '-c', code], text=True))
diff = {name:{'host':host['files'].get(name),'candidate':candidate['files'].get(name)}
        for name in host['files'].keys() | candidate['files'].keys()
        if host['files'].get(name) != candidate['files'].get(name)}
report = {'host_manifest':host['manifest'],'candidate_manifest':candidate['manifest'],'differences':diff}
(Path(__file__).parent / 'candidate-source-differences.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))

import hashlib, json, subprocess, tarfile
from pathlib import Path
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOCKER = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']
FILES = ['src/features/simulation/ui/model-simulation-runner.tsx', 'src/features/traces/ui/analysis-workspace-tools.tsx', 'src/features/traces/lib/analysis-workspace-browser.ts', 'src/app/globals.css']
def run(*args):
    return subprocess.check_output([DOCKER, *args], text=True)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
identity = json.loads(run('inspect', 'NetworkIS'))[0]
assert identity['State']['Running']
base_image = identity['Image']
before = json.loads(run('exec', 'NetworkIS', 'python', '-c',
    "from pathlib import Path; import hashlib,json; files=" + repr(FILES) + "; print(json.dumps({f:(hashlib.sha256((Path('/app/frontend')/f).read_bytes()).hexdigest() if (Path('/app/frontend')/f).exists() else None) for f in files}))"))
for name in FILES:
    assert before[name] == (sha(HERE / 'before/frontend' / name) if (HERE / 'before/frontend' / name).exists() else None), f'Production source drift: {name}'
hashes = {name: sha(ROOT / 'frontend' / name) for name in FILES}
patch_id = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:12]
stage = '/app/.frontend-ui-stage-' + patch_id
backup = '/app/.frontend-ui-rollback-' + patch_id
manifest = json.loads(run('exec', 'NetworkIS', 'cat', '/app/frontend/public/build-info.json'))
manifest.update(frontend_patch_id=patch_id, frontend_patch_mode='user-authorized-direct-frontend',
                frontend_patch_created_at=datetime.now(timezone.utc).isoformat(),
                frontend_patch_base_image=base_image, frontend_patch_source_hashes=hashes,
                frontend_patch_verification='small targeted checks, not full release gate')
(HERE / 'frontend-build-info.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
bundle = HERE / 'frontend-source-patch.tar'
with tarfile.open(bundle, 'w') as archive:
    for name in FILES:
        archive.add(ROOT / 'frontend' / name, arcname=name)
    archive.add(HERE / 'frontend-build-info.json', arcname='public/build-info.json')
run('cp', str(bundle), 'NetworkIS:/tmp/frontend-source-patch-' + patch_id + '.tar')
code = """
from pathlib import Path
import shutil, tarfile
stage = Path(STAGE)
assert stage.parent == Path('/app') and stage.name.startswith('.frontend-ui-stage-')
assert not stage.exists(), 'Stage already exists; do not overwrite it'
shutil.copytree('/app/frontend', stage, symlinks=True, ignore=shutil.ignore_patterns('.next*', 'test-results', 'playwright-report'))
with tarfile.open(ARCHIVE) as archive:
    archive.extractall(stage, filter='data')
print('Frontend staged; production unchanged')
""".replace('STAGE', repr(stage)).replace('ARCHIVE', repr('/tmp/frontend-source-patch-' + patch_id + '.tar'))
print(run('exec', 'NetworkIS', 'python', '-c', code))
record = {'patch_id': patch_id, 'base_image': base_image, 'stage': stage, 'backup': backup,
          'source_hashes': hashes, 'before_source_hashes': before, 'image_created': False,
          'base_build_id': manifest['build_id'], 'container_id': identity['Id']}
(HERE / 'stage.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record, indent=2))

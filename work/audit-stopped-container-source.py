"""Hash NIS source from a stopped container without starting its image or database."""
import hashlib
import json
import subprocess
import sys
import tarfile

docker, container = sys.argv[1:3]
roots = (
    'backend/agent_core', 'backend/app', 'backend/backend',
    'backend/communication', 'backend/engineering', 'backend/intelligence',
    'backend/knowledge', 'backend/nis', 'backend/simulator',
    'backend/simulator_engineering_mcp', 'backend/specializations',
    'backend/workflow', 'frontend/src', 'frontend/scripts',
    'config', 'scripts',
)
files = ('Dockerfile', '.dockerignore', 'generate_realistic_communication_tool.py')
excluded = {'__pycache__', 'tests', 'e2e', 'runtime', 'test-output'}
hashes = {}
for root in (*roots, *files):
    process = subprocess.Popen(
        [docker, 'cp', f'{container}:/app/{root}', '-'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|*') as archive:
            for entry in archive:
                if not entry.isfile():
                    continue
                tail = entry.name.split('/', 1)[-1]
                relative = f'{root}/{tail}' if root in roots else root
                if excluded.intersection(relative.split('/')) or relative.endswith(('.pyc', '.tsbuildinfo')):
                    continue
                stream = archive.extractfile(entry)
                if stream is None:
                    continue
                hashes[relative] = hashlib.sha256(stream.read().replace(b'\r\n', b'\n')).hexdigest()
    finally:
        process.stdout.close()
        stderr = process.stderr.read().decode(errors='replace')
        code = process.wait()
        if code and 'Could not find the file' not in stderr:
            raise RuntimeError(f'docker cp {root}: {stderr}')
print(json.dumps(hashes, sort_keys=True, separators=(',', ':')))

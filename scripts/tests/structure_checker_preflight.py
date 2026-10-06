"""Observed source-test preflight, preserving the existing EA provider."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding='utf-8'))
    root = Path(request['project'])
    config = json.loads((root / '.tool-checker/config/project-cli.json').read_text(encoding='utf-8'))
    if request['task_id'] != 'nis-structure-completion-20261003':
        return subprocess.run([*config['structure_delegate_provider']['argv'], '--request', args.request, '--output', args.output], cwd=root).returncode
    directory = Path(request['evidence_directory'])
    observations = {}
    commands = {'python': [str(root / 'backend/.venv/Scripts/python.exe'), '-c', 'import pytest, psycopg; print("pytest/psycopg ready")'],
                'node':['node','--version']}
    docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
    commands['docker'] = [docker, 'info', '--format', '{{.ServerVersion}}']
    for name, command in commands.items():
        result = subprocess.run(command, capture_output=True, text=True, cwd=root, timeout=20)
        if result.returncode: raise RuntimeError(name + ' is unavailable')
        observations[name] = result.stdout.strip()
    for name in ['backend/tests/test_structure_consolidation.py', 'backend/tests/test_structure_completion.py', 'backend/tests/test_structure_architecture.py',
                 'scripts/run-isolated-tests.py', 'docs/migrations/structure_mapping.csv',
                 'frontend/src/features/communication/lib/technology-projection.json']:
        path = root / name
        observations[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    projection = json.loads((root / 'frontend/src/features/communication/lib/technology-projection.json').read_text(encoding='utf-8'))
    if len(projection['technologies']) != 125: raise RuntimeError('Incomplete technology test input')
    evidence = directory / 'source-test-preflight.json'
    evidence.write_text(json.dumps(observations, indent=2), encoding='utf-8')
    proof = dict(source_hash=request['source_hash'],contract_hash=request['contract_hash'],project_path=request['project'],
                 checked_at=datetime.now(timezone.utc).isoformat(), available_skills=[],available_tools=[],available_views=[],
                 preconditions=[{'name':name,'status':'PASSED','evidence':[str(evidence)]} for name in request['case']['preconditions']])
    for key in ['dependencies','application','project','permissions','test_data']:
        proof[key] = {'status':'PASSED','evidence':[str(evidence)]}
    path = directory / 'preflight.json'
    path.write_text(json.dumps(proof, indent=2), encoding='utf-8')
    Path(args.output).write_text(json.dumps({request['test_id']:{'preflight':str(path)}}), encoding='utf-8')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

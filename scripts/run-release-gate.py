"""Build once, test that immutable image in a disposable stack, emit a receipt.

This command never restarts or modifies NetworkIS/NetworkIS-db. A failed gate
retains reports but cannot issue a PASS receipt for deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
POSTGRES = "postgres:16-alpine@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685"


def verification_manifest():
    paths = set((ROOT/'backend/tests').rglob('*')) | set((ROOT/'frontend/e2e').rglob('*')) | set((ROOT/'tests/fixtures').rglob('*'))
    paths.update(ROOT/name for name in ('frontend/playwright.config.ts',
        'scripts/run-release-gate.py', 'scripts/run-isolated-tests.py',
        'scripts/verify-live-wizard.py', 'scripts/deploy-verified-release.py',
        '.github/workflows/wizard-release-gate.yml'))
    hashes = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
              for path in sorted(paths) if path.is_file() and '__pycache__' not in path.parts}
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', help='Already built candidate image; must contain the current source manifest.')
    parser.add_argument('--output', type=Path, default=ROOT / 'backend/test-output/release-gates')
    parser.add_argument('--keep', action='store_true', help='Keep only this isolated stack on failure for diagnosis.')
    parser.add_argument('--prepare', action='store_true', help='Build/start an isolated development stack; never issues a release PASS.')
    parser.add_argument('--development-base', help='Only with --prepare: reuse installed runtime dependencies while iterating.')
    args = parser.parse_args()
    if args.development_base and not args.prepare:
        parser.error('--development-base cannot produce a release PASS; use a clean Dockerfile build for the gate.')
    module = importlib.util.spec_from_file_location('nis_isolation', ROOT / 'scripts/run-isolated-tests.py')
    isolation = importlib.util.module_from_spec(module); module.loader.exec_module(isolation)
    info_spec = importlib.util.spec_from_file_location('nis_build_info', ROOT/'scripts/write-build-info.py')
    info = importlib.util.module_from_spec(info_spec); info_spec.loader.exec_module(info)
    initial_manifest = info.build_manifest()
    initial_source_sha256 = initial_manifest['source_sha256']
    initial_commit_id = initial_manifest['commit_id']
    docker = isolation.docker_executable()
    token = secrets.token_hex(6)
    output = args.output.resolve() / token; output.mkdir(parents=True, exist_ok=True)
    names = {key: 'nis-e2e-' + key + '-' + token for key in ('db', 'app', 'network', 'runtime')}
    password = secrets.token_hex(24)
    env = {**os.environ, 'POSTGRES_PASSWORD': password}
    receipt = {'schema_version': 1, 'status': 'RUNNING', 'checks': [], 'containers': names,
               'initial_source_sha256': initial_source_sha256, 'initial_commit_id': initial_commit_id,
               'verification_sha256': verification_manifest()}
    created = []
    def save_receipt():
        (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    save_receipt()
    def run(command, *, environment=env, cwd=ROOT, name=None):
        with (output / ((name or 'command-' + str(len(receipt['checks']))) + '.log')).open('w', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=cwd, env=environment, stdout=log, stderr=subprocess.STDOUT)
        receipt['checks'].append({'name': name, 'exit_code': result.returncode})
        save_receipt()
        if result.returncode:
            raise RuntimeError(f'{name or "Command"} failed; see {output}')
    def control(*command):
        return subprocess.check_output([docker, *command], env=env, text=True).strip()
    try:
        node = shutil.which('node') or r'C:\Program Files\nodejs\node.exe'
        if not args.prepare:
            run([node, 'node_modules/typescript/bin/tsc', '--noEmit', '--incremental', 'false'], cwd=ROOT/'frontend', name='typecheck')
            run([node, '--experimental-strip-types', '--test', 'src/lib/*.test.mjs', 'src/lib/agent/*.test.mjs'], cwd=ROOT/'frontend', name='frontend-tests')
            run([sys.executable, str(ROOT/'scripts/run-isolated-tests.py'), '--', 'backend/tests', '-q'], name='backend-tests')
        if initial_source_sha256 != info.build_manifest()['source_sha256']:
            raise RuntimeError('Sources changed during unit verification. Repeat the gate from the initial source.')
        if receipt['verification_sha256'] != verification_manifest():
            raise RuntimeError('Tests changed during unit verification. Repeat the gate before building a candidate.')
        if not initial_commit_id:
            raise RuntimeError('Git revision is unavailable. A candidate needs a real base commit identity.')
        image = args.image or 'networkis:candidate-' + token
        if not args.image:
            command = [docker, 'build', '-t', image, '--build-arg', 'NIS_BUILD_COMMIT_ID=' + initial_commit_id]
            if args.development_base:
                base_id = control('image','inspect',args.development_base,'--format','{{.Id}}')
                development_file = output/'Dockerfile.development'
                development_file.write_text(f'FROM {args.development_base}\nLABEL networkis.development=true\nCOPY . /app\nARG NIS_BUILD_COMMIT_ID\nRUN NIS_BUILD_COMMIT_ID="$NIS_BUILD_COMMIT_ID" python /app/scripts/write-build-info.py\nRUN cd /app/frontend && node /usr/local/lib/node_modules/npm/bin/npm-cli.js run build\n',encoding='utf-8')
                receipt['development_base_id'] = base_id
                command += ['-f', str(development_file)]
                receipt['development_only'] = True
            run([*command, '.'], name='production-build')
        image_id = control('image', 'inspect', image, '--format', '{{.Id}}')
        receipt['image_id'] = image_id
        image_config = json.loads(control('image', 'inspect', image_id))[0]['Config']
        if image_config.get('Labels', {}).get('networkis.development') == 'true':
            receipt['development_only'] = True
            if not args.prepare:
                raise RuntimeError('Development images cannot be release candidates. Build using the production Dockerfile.')
        manifest = json.loads(control('run', '--rm', '--entrypoint', 'cat', image_id, '/app/backend/app/build-info.json'))
        if manifest['source_sha256'] != initial_source_sha256 or initial_source_sha256 != info.build_manifest()['source_sha256']:
            raise RuntimeError('Candidate source differs from the working tree. Build a new candidate.')
        if manifest.get('commit_id') != initial_commit_id or info.build_manifest()['commit_id'] != initial_commit_id:
            raise RuntimeError('Candidate Git revision differs from the verified base commit.')
        receipt['release'] = manifest
        control('volume', 'create', '--label', 'networkis.test=disposable', names['runtime']); created.append(('volume', names['runtime']))
        control('network', 'create', '--label', 'networkis.test=disposable', names['network']); created.append(('network', names['network']))
        control('run', '-d', '--name', names['db'], '--network', names['network'], '--network-alias', 'test-db',
                '--label', 'networkis.test=disposable', '-e', 'POSTGRES_USER=nis_test', '-e', 'POSTGRES_DB=nis_test_e2e',
                '-e', 'POSTGRES_PASSWORD', '--tmpfs', '/var/lib/postgresql/data', POSTGRES)
        created.append(('container', names['db']))
        for _ in range(120):
            if subprocess.run([docker,'exec',names['db'],'pg_isready','-U','nis_test','-d','nis_test_e2e'], capture_output=True).returncode == 0: break
            time.sleep(.5)
        else: raise RuntimeError('Test database failed readiness.')
        env['DATABASE_URL'] = f'postgresql://nis_test:{password}@test-db:5432/nis_test_e2e'
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            app_port = reservation.getsockname()[1]
        # Record an explicit host port. Docker's "::13500" dynamic publication
        # selects a different port after restart, invalidating browser recovery.
        local_ai_base_url = os.environ.get('NIS_E2E_LOCAL_AI_BASE_URL', 'http://127.0.0.1:1/v1').strip()
        control('run', '-d', '--name', names['app'], '--network', names['network'], '--label', 'networkis.test=disposable',
                '-e', 'DATABASE_URL', '-e', 'NETWORKIS_ALLOW_NON_CANONICAL_ROOT=1', '-e', 'NUMERIC_ACCELERATOR=cpu',
                '-e', 'SIMULATOR_RUNTIME_ROOT=/app/backend/runtime', '-e', 'SIMULATION_EXECUTOR=thread',
                '-e', 'AI_PROVIDER=hybrid-demand', '-e', 'CLOUD_ESCALATION=never', '-e', f'LOCAL_AI_BASE_URL={local_ai_base_url}',
                '-p', f'127.0.0.1:{app_port}:13500', '--mount', 'type=volume,source='+names['runtime']+',target=/app/backend/runtime', image_id)
        created.append(('container', names['app']))
        port = json.loads(control('inspect', names['app']))[0]['NetworkSettings']['Ports']['13500/tcp'][0]['HostPort']
        base = 'http://127.0.0.1:' + port
        receipt['base_url'] = base
        for _ in range(180):
            try:
                with urlopen(base + '/api/ready', timeout=2) as response:
                    if response.status == 200: break
            except Exception: pass
            time.sleep(1)
        else: raise RuntimeError('Test application failed readiness.')
        browser_temp = output / 'browser-temp'
        browser_temp.mkdir()
        test_env = {**os.environ, 'TEMP': str(browser_temp), 'TMP': str(browser_temp), 'TMPDIR': str(browser_temp),
                    'NIS_E2E_ISOLATED':'1', 'NIS_E2E_URL':base,
                    'NIS_E2E_APP_CONTAINER':names['app'], 'NIS_TEST_DOCKER':docker,
                    'NIS_E2E_OUTPUT':str(output/'browser'), 'NIS_E2E_REPORT':str(output/'browser.json')}
        # CI and local acceptance use the browser revision pinned by Playwright.
        # A system Chrome override is permitted only for manual diagnostic runs.
        test_env.pop('NIS_E2E_BROWSER_CHANNEL', None)
        if args.prepare:
            receipt['status'] = 'PREPARED'
            return 0
        run([node, 'node_modules/playwright/cli.js', 'test'], environment=test_env, cwd=ROOT/'frontend', name='browser-e2e')
        for name, options in [('small',['--complete-scope']), ('large',['--prompt-file',str(ROOT/'frontend/e2e/fixtures/wizard-large-50-250-250.txt')])]:
            run([sys.executable,str(ROOT/'scripts/verify-live-wizard.py'),'--base-url',base,'--report',str(output/(name+'-http.json')),*options],environment=test_env,name=name+'-http')
        if manifest['source_sha256'] != info.build_manifest()['source_sha256']:
            raise RuntimeError('Sources changed during verification. Candidate cannot be released.')
        if manifest['commit_id'] != info.build_manifest()['commit_id']:
            raise RuntimeError('Git revision changed during verification. Candidate cannot be released.')
        if receipt['verification_sha256'] != verification_manifest():
            raise RuntimeError('Tests changed during verification. Repeat the gate before release.')
        receipt['status'] = 'PASS'
    except (Exception, KeyboardInterrupt) as error:
        receipt.update(status='FAIL',error=str(error))
    finally:
        for kind, name in reversed(created):
            if kind == 'container':
                with (output/(name+'.log')).open('w',encoding='utf-8') as log:
                    subprocess.run([docker,'logs',name],stdout=log,stderr=subprocess.STDOUT)
            if not (receipt['status'] == 'PREPARED' or (args.keep and receipt['status'] != 'PASS')):
                cleanup = [docker, 'rm', '-f', name] if kind=='container' else [docker, kind, 'rm', name]
                subprocess.run(cleanup,capture_output=True)
        save_receipt()
        print(json.dumps({'status':receipt['status'],'receipt':str(output/'receipt.json')}),flush=True)
    return 0 if receipt['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())

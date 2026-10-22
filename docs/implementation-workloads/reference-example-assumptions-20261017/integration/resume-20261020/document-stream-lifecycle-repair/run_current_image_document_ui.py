"""Existing deterministic browser contracts against exact isolated normal image."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import subprocess
from urllib.request import urlopen

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
UI = OUT.parent / 'document-network-error-repair'
RECEIPT = ROOT / 'backend/test-output/release-gates/joint-waitress-lifecycle-originals-863f7aa13b0d/a65dd06ef20c/receipt.json'
r = json.loads(RECEIPT.read_text())
assert r['status'] == 'PREPARED' and r['base_url'] == 'http://127.0.0.1:52588'
assert r['image_id'] == 'sha256:8826cf8dcbb36a99a0c8a0204435ae5347dda72c79af48b6fb471b9dba625b36'
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']
assert subprocess.check_output([docker, 'inspect', r['containers']['app'], '--format', '{{.Image}}'], text=True).strip() == r['image_id']
with urlopen(r['base_url'] + '/api/build-info', timeout=10) as response:
    assert json.load(response)['source_sha256'] == r['initial_source_sha256']
output = UI / 'current-image-browser'
assert not output.exists()
output.mkdir()
env = {**os.environ, 'NIS_E2E_ISOLATED':'1', 'NIS_E2E_URL':r['base_url'], 'NIS_E2E_OUTPUT':str(output), 'NIS_E2E_REPORT':str(UI / 'current-image-browser.json')}
env.pop('NIS_E2E_BROWSER_CHANNEL', None)
command = ['C:/Program Files/nodejs/node.exe', 'node_modules/playwright/cli.js', 'test', 'e2e/document-intake.spec.ts']
with (UI / 'current-image-browser.log').open('w', encoding='utf8') as log:
    result = subprocess.run(command, cwd=ROOT / 'frontend', env=env, stdout=log, stderr=subprocess.STDOUT)
record = {'at_utc':datetime.now(timezone.utc).isoformat(), 'exit_code':result.returncode, 'image_id':r['image_id'], 'source_sha256':r['initial_source_sha256'], 'base_url':r['base_url'], 'command':command, 'scope':'Existing4 deterministic frontend document/transport contracts on exact normal image. Aborted/fixture responses; no additional native Qwen or original model/simulation/full gate PASS.'}
(UI / 'current-image-browser-result.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
print(json.dumps(record), flush=True)
raise SystemExit(result.returncode)

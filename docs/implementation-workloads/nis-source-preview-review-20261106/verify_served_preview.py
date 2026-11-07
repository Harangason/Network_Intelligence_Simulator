"""Bind the actually served compiled preview to the exact delivered image, read-only."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

directory = Path(__file__).resolve().parent
root = directory.parents[2]
receipt_path = root / 'backend/test-output/release-gates/delivery-6127991a9e47/4310b821dab9/receipt.json'
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS'
docker = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
container = json.loads(subprocess.check_output([docker, 'inspect', 'NetworkIS'], text=True, encoding='utf-8'))[0]
assert container['Image'] == receipt['image_id'] and container['State']['Running']
script = r'''
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const base = '/app/frontend/' + (process.env.NETWORKIS_NEXT_DIST_DIR || '.next') + '/static';
const result = [];
function visit(directory) {
  for (const item of fs.readdirSync(directory, {withFileTypes: true})) {
    const file = path.join(directory, item.name);
    if (item.isDirectory()) visit(file);
    else if (item.name.endsWith('.js')) {
      const raw = fs.readFileSync(file);
      if (raw.includes(Buffer.from('Beispieldokument zuerst'))) {
        result.push({relative: path.relative(base, file), bytes: raw.length,
                     sha256: crypto.createHash('sha256').update(raw).digest('hex')});
      }
    }
  }
}
visit(base);
process.stdout.write(JSON.stringify(result));
'''
result = subprocess.run([docker, 'exec', '-i', 'NetworkIS', 'node', '--input-type=module'],
                        input=script.encode(), capture_output=True)
(directory / 'served-preview-artifacts.stdout.json').write_bytes(result.stdout)
(directory / 'served-preview-artifacts.stderr.log').write_bytes(result.stderr)
assert result.returncode == 0
artifacts = json.loads(result.stdout)
assert artifacts, 'New preview label must be present in the actual compiled frontend'
report = {'at': datetime.now(timezone.utc).isoformat(), 'scope': 'Read-only compiled preview bundle identity and normal HTTP reads, no inference or project writes',
          'image_id': container['Image'], 'source_sha256': receipt['release']['source_sha256'],
          'receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
          'artifact_process_exit_code': result.returncode, 'artifacts': artifacts, 'http': []}
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for artifact in artifacts:
    for base in ['http://127.0.0.1:13500', 'http://192.168.178.10:13500']:
        url = base + '/_next/static/' + artifact['relative']
        with opener.open(url, timeout=15) as response:
            raw = response.read()
            assert response.status == 200
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == artifact['sha256'], url
        report['http'].append({'url': url, 'status': 200, 'sha256': digest, 'bytes': len(raw)})
report['status'] = 'PASSED'
(directory / 'live-frontend-bundle.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'PASSED', 'artifacts': len(artifacts), 'http_checks': len(report['http']), 'image_id': container['Image']}))

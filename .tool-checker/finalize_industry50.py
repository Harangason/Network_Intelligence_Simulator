import hashlib
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
evidence = root / '.tool-checker/evidence/industry50'
report = root / '.tool-checker/reports/industry50-report-20260916.md'
text = report.read_text(encoding='utf8')
text = text.replace("{'FAILED': 29, 'PARTIAL': 21}.", '**29 FAILED · 21 PARTIAL.**')
extra = '''\nZusätzlicher Browsernachweis S03-A: Auch der Klick auf „Modellvorschlag erstellen“ behebt die verlorenen Angaben nicht. Der Agent verlangt erneut Controller-Zuordnung, Typ/Aufgabe und physische Anschlüsse für Sensor1. Beleg: [Vorschlagsversuch](I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry50/S03-A/proposal-attempt.txt).\n\n'''
text = text.replace('## Nachgewiesene funktionierende Teile', extra + '## Nachgewiesene funktionierende Teile')
report.write_text(text, encoding='utf8')

docker = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
objects = [('container', 'nis-e2e-app-96f25e6a865f'), ('container', 'nis-e2e-db-96f25e6a865f'), ('network', 'nis-e2e-network-96f25e6a865f'), ('volume', 'nis-e2e-runtime-96f25e6a865f')]
checked = []
for kind, name in objects:
    result = subprocess.run([docker, kind, 'inspect', name], capture_output=True, check=True)
    obj = json.loads(result.stdout)[0]
    labels = obj.get('Config', {}).get('Labels', {}) if kind == 'container' else obj.get('Labels', {})
    assert labels.get('networkis.test') == 'disposable', (name, labels)
    checked.append({'kind': kind, 'name': name, 'labels': labels})
logs = subprocess.run([docker, 'logs', objects[0][1]], capture_output=True, check=True)
(evidence / 'runtime-app.log').write_bytes(logs.stdout + logs.stderr)
for kind, name in objects:
    args = [docker, 'rm', '-f', name] if kind == 'container' else [docker, kind, 'rm', name]
    subprocess.run(args, capture_output=True, check=True)
(evidence / 'cleanup.json').write_text(json.dumps({'removed_isolated_objects': checked, 'product_untouched': True}, indent=2), encoding='utf8')
manifest = []
for p in sorted(evidence.rglob('*')):
    if p.is_file() and p.name != 'sha256-manifest.json':
        data = p.read_bytes()
        manifest.append({'path': p.relative_to(evidence).as_posix(), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
(evidence / 'sha256-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
print(json.dumps({'evidence_files': len(manifest), 'isolated_objects_removed': len(checked)}))

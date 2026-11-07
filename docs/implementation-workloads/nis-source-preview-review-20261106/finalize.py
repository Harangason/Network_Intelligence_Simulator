"""Close this repair only against terminal delivery and live verification evidence."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

directory = Path(__file__).resolve().parent
root = directory.parents[2]
work_path = directory / 'workload.json'
work = json.loads(work_path.read_text(encoding='utf-8'))
receipt_path = Path(work['delivery']['receipt'])
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
spec = importlib.util.spec_from_file_location('final_preview_storage', root / 'scripts/release_storage.py')
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)
assert storage.complete_pass(receipt)
terminal = json.loads((directory / 'delivery-terminal.json').read_text(encoding='utf-8'))
assert terminal['exit_code'] == 0 and terminal['result']['status'] == 'DEPLOYED'
assert terminal['result']['image_id'] == receipt['image_id']
for phase in ['before', 'components', 'frontend-bundle', 'after']:
    live = json.loads((directory / ('live-' + phase + '.json')).read_text(encoding='utf-8'))
    assert live['status'] == 'PASSED' and live['image_id'] == receipt['image_id']
    assert live['source_sha256'] == receipt['release']['source_sha256']
for name, digest in work['frozen_files'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name


def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def passed(*paths):
    return {'status': 'PASSED', 'evidence': [ref(path) for path in paths]}


gate_dir = receipt_path.parent
browser = json.loads((gate_dir / 'browser.json').read_text(encoding='utf-8'))
stats = browser['stats']
assert stats['expected'] == 122 and stats['unexpected'] == stats['skipped'] == stats['flaky'] == 0
http = {}
for name in ['small', 'large']:
    report = json.loads((gate_dir / (name + '-http.json')).read_text(encoding='utf-8'))
    assessment = report['assessment']
    assert assessment['conformance'] == 'PASS' and assessment['failed_route_count'] == 0
    assert assessment['scope_coverage']['complete'] is True
    assert assessment['release']['source_sha256'] == receipt['release']['source_sha256']
    http[name] = {'project': report['project'], 'job_id': report['job_id'], 'statuses': report['statuses'],
                  'conformance': assessment['conformance'], 'failed_route_count': assessment['failed_route_count'],
                  'scope_complete': assessment['scope_coverage']['complete'], 'evidence': ref(gate_dir / (name + '-http.json'))}
summary = {'at': datetime.now(timezone.utc).isoformat(), 'scope': 'Canonical controlled release scenarios; no native historical Original acceptance',
           'status': 'PASSED', 'image_id': receipt['image_id'], 'source_sha256': receipt['release']['source_sha256'],
           'browser': stats, 'http': http, 'receipt': ref(receipt_path)}
(directory / 'release-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
release = passed(receipt_path, directory / 'release-summary.json')
deployment = passed(directory / 'delivery-terminal.json', directory / 'live-after.json')
health = passed(directory / 'live-before.json', directory / 'live-after.json')
functional = passed(directory / 'live-components.json', directory / 'production-preview.stdout.json',
                    directory / 'live-frontend-bundle.json', directory / 'browser-source-path-result.json')
work['outcomes']['complete_release_gate'] = release
work['outcomes']['verified_production_delivery'] = passed(receipt_path, directory / 'delivery-terminal.json',
                                                         directory / 'live-after.json', directory / 'live-components.json')
work['validations']['full_matching_release_gate'] = release
work['validations']['production_identity_health_and_preview'] = passed(directory / 'live-before.json',
                                                                      directory / 'live-components.json', directory / 'live-frontend-bundle.json', directory / 'live-after.json')
work['delivery'].update({'status': 'DEPLOYED_VERIFIED', 'tested_version': receipt['image_id'],
                         'running_version': live['image_id'], 'checks': {
                             'release': release, 'deployment': deployment, 'health': health, 'functional': functional},
                         'passed_checks': receipt['checks']})
work['tests'].append({'scope': 'Complete canonical release; overlapping local suites are not added',
                       'result': '725 frontend PASS; 22670 backend PASS, 2 SKIP, 56 subtests PASS, 1 warning; browser and HTTP checks Exit0',
                       'evidence': [ref(receipt_path), *[ref(gate_dir / name) for name in
                           ['frontend-tests.log', 'backend-tests.log', 'browser-e2e.log']]]})
work['remaining_findings'] = []
quota_path = directory / 'usage-before-delivery-verification.json'
quota = json.loads(quota_path.read_text(encoding='utf-8'))
assert quota['ordinaryUsageAllowed'] and quota['weeklyUsedPercent'] < quota['stopAtUsedPercent'] == 75
work['preflight']['weekly_last_observed_used_percent'] = quota['weeklyUsedPercent']
work['preflight']['weekly_limit_evidence'] = ref(quota_path)
user_status_path = max(directory.glob('user-project-status-*.json'), key=lambda path: path.stat().st_mtime_ns)
assert user_status_path.stat().st_mtime_ns >= (directory / 'delivery-terminal.json').stat().st_mtime_ns
work['user_project_status_after_delivery'] = ref(user_status_path)
work['status'] = work['completion_status'] = 'COMPLETED'
work['completed_at'] = datetime.now(timezone.utc).isoformat()
work['completion_scope'] = 'This source-preview repair only; no historical Original campaign or native model acceptance is asserted.'
work['browser_handoff'] = 'Original unsent browser draft was preserved without reload or input edits. Reload and reattach the actual source to load the delivered client.'
work_path.write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

guard = Path('F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py')
result = subprocess.run([sys.executable, str(guard), 'completion', '--workload', str(work_path)],
                        capture_output=True, text=True, encoding='utf-8')
guard_result = json.loads(result.stdout)
proof = {'at': datetime.now(timezone.utc).isoformat(), 'exit_code': result.returncode,
         'workload': ref(work_path), 'result': guard_result, 'stderr': result.stderr}
(directory / 'completion-guard.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert result.returncode == 0 and guard_result['status'] == 'COMPLETED' and not guard_result['issues']
report_path = directory / 'REPORT.md'
description = report_path.read_text(encoding='utf-8').split('Aktueller Releaseweg:')[0]
description = description.replace(
    'Status: Korrektur im normalen Kandidaten und im isolierten Browser geprüft; vollständiger Releaseweg läuft. Noch nicht produktiv.',
    'Status: vollständig geprüft, exakt getestetes Image produktiv übernommen und geprüft.')
report_path.write_text(description + f'''Abgeschlossener Releaseweg: Session 36741, normaler Exit 0 / DEPLOYED.
Receipt `{receipt_path.relative_to(root).as_posix()}` ist vollständig PASS.
Image `{receipt['image_id']}`.
Source `{receipt['release']['source_sha256']}`.
Verification `{work['delivery']['verification_sha256']}`.

Vollständige kanonische Prüfungen: Speicherprüfungen und TypeScript Exit 0;
725 Frontendfälle PASS; 22670 Backendfälle PASS, 2 SKIP, 56 Subtests PASS,
eine Feldnamenwarnung. Alle 122 Browserfälle PASS, keine Wiederholung und kein
übersprungener Browserfall. Beide kontrollierten HTTP-Vergleichsfälle haben
PASS-Konformität, vollständige Scopeabdeckung und null fehlgeschlagene Routen.
Vorhandene fachliche Warnungen bleiben in den Originalreports sichtbar.

Die produktive Containeridentität entspricht dem getesteten Image. Normale
Ready-/Build-GETs auf 13500, 15050 und LAN sowie dieselbe Projektseite auf Lokal
und LAN sind geprüft. Die reinen Komponenten aus dem tatsächlich laufenden
Produktimage bestehen die vollständige quellengebundene Vorschau-Gegenprobe;
es wurde dafür weder eine Inferenz noch ein Projektauftrag gestartet. Details:
`release-summary.json`, `delivery-terminal.json`, `live-before.json`,
`live-components.json`, `live-frontend-bundle.json`, `live-after.json` und `completion-guard.json`.
Das tatsächlich ausgelieferte JavaScript mit der neuen Vorschau stimmt lokal
und über LAN bytegenau mit dem kompilierten Artefakt im laufenden Image überein.
Alle sieben eingefrorenen Änderungsdateien sind unverändert. Abschlussguard:
COMPLETED, fünf Ziele und fünf Validierungen belegt, keine offenen Befunde.

Der ungesendete alte Browserentwurf wurde nicht neu geladen. Für den neuen
Client muss der Nutzer selbst neu laden und seine tatsächliche Datei erneut
anhängen. Der gespeicherte Nutzerprojektstatus wurde nach der Übernahme nur
gelesen; keine manuelle Änderung von Geräten, Anschlüssen oder Anforderungen.
Diese Abnahme umfasst die Vorschaukorrektur und das normale Releasegate;
sie ersetzt keine historischen nativen Fahrzeug-/Robotik-Originalprüfungen.
''', encoding='utf-8')
(directory / 'NEXT.md').write_text(f'''# Abgeschlossen: Vorschaukorrektur produktiv geprüft

Session36741 regulär Exit0/DEPLOYED. Vollständiges PASSreceipt:
{receipt_path.relative_to(root).as_posix()}

Exakt getestetes und produktiv geprüftes Image: {receipt['image_id']}
Quelle: {receipt['release']['source_sha256']}

Alle fünf Ziele/fünf Validierungen belegt; completion-guard.json COMPLETED,
keine Issues. Gesamtergebnis und Grenzen stehen in REPORT.md und workload.json.
Keine Folgearbeit für diesen Reparaturauftrag offen. Nicht als historische
Originalkampagnenabnahme darstellen. Keine neuen Modellrequests oder anderen
Aufträge daraus ableiten. Kein Shutdown/keine neue Automation.

Offenen alten Nutzerbrowser nicht eigenmächtig reloaden: ungesendete Anlage.
Nutzerhinweis: neu laden und tatsächliche Quelldatei erneut anhängen, um die
gelieferte Fassung zu verwenden. Projekt 20261106093746010-f2585546 beibehalten.
''', encoding='utf-8')
print(json.dumps({'status': 'COMPLETED', 'outcomes': len(work['required_outcomes']),
                  'validations': len(work['validation_requirements']), 'image_id': receipt['image_id']}))

"""Close the authorized work only with an exact PASS and live delivery evidence."""
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'docs/implementation-workloads/technology-full-parameter-audit-20261001'

def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    receipt_path = args.receipt.resolve()
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    live_path = ROOT / 'work/parameter-production-verification.json'
    live = json.loads(live_path.read_text(encoding='utf-8'))
    assert receipt['status'] == 'PASS'
    assert live['status'] == 'PASSED' and live['running_image'] == receipt['image_id']
    assert live['build']['source_sha256'] == receipt['release']['source_sha256']
    assert {row['name'] for row in receipt['checks'] if row['exit_code'] == 0} >= {
        'storage-tests', 'typecheck', 'frontend-tests', 'backend-tests', 'browser-e2e', 'small-http', 'large-http'}
    assert all(row['exit_code'] == 0 for row in receipt['checks'])
    backend_log = receipt_path.parent / 'backend-tests.log'
    frontend_log = receipt_path.parent / 'frontend-tests.log'
    browser_path = receipt_path.parent / 'browser.json'
    backend_text = backend_log.read_text(encoding='utf-8', errors='replace')
    passed = re.findall(r'(\d+) passed', backend_text)
    assert passed and not re.search(r'\d+ failed', backend_text)
    small_path, large_path = [receipt_path.parent / (name + '-http.json') for name in ('small', 'large')]
    small, large = [json.loads(path.read_text(encoding='utf-8')) for path in (small_path, large_path)]
    for case in (small, large):
        assert len(case['statuses']) == 9
        assert set(case['statuses'].values()) <= {'COMPLETE', 'APPROVED', 'WARNING'}
        assert case['assessment']['scope_coverage']['scope_mode'] == 'ALL'
        assert case['assessment']['scope_coverage']['complete']
        assert case['assessment']['conformance'] == 'PASS'
        assert case['assessment']['failed_route_count'] == 0
        assert not case['assessment']['missing_observed_signal_ids']
    individual_files = sorted((FOLDER / 'individual').glob('*.json'))
    assert len(individual_files) == 125
    records = [json.loads(path.read_text(encoding='utf-8')) for path in individual_files]
    assert all(row['status'] == 'SOURCE_AND_LOCAL_RULES_REVIEWED' for row in records)
    for path, record in zip(individual_files, records):
        # Keep the original local/source validation as history; append delivery
        # proof instead of implying those earlier checks exercised production.
        record['delivery'] = {'status': 'VERIFIED', 'tested_image': receipt['image_id'],
                              'running_image': live['running_image'],
                              'release': ref(receipt_path), 'live_verification': ref(live_path)}
        record['remaining_not_certified'] = [item for item in record.get('not_certified', [])
                                            if item != 'Production delivery']
        if 'consumer_followup' in record:
            record['consumer_followup'].update(production_delivered=True, release=ref(receipt_path))
        for field in record['parameter_reviews']:
            if 'consumer_followup' in field:
                field['consumer_followup'].update(production_delivered=True, release=ref(receipt_path))
        save(path, record)
    subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'work/verify-parameter-review-coverage.py')], check=True)
    coverage_path = ROOT / 'work/parameter-review-coverage.json'
    coverage = json.loads(coverage_path.read_text(encoding='utf-8'))
    assert coverage['status'] == 'PASSED' and coverage['profiles'] == 125
    inventory_path = FOLDER / 'consumer-schema-inventory.json'
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    assert len(inventory['profiles']) == 125
    inventory.update(production_delivered=True, release_gate='PASS', receipt=ref(receipt_path),
                     delivery=ref(live_path))
    save(inventory_path, inventory)
    progress_path = FOLDER / 'progress.json'
    progress = json.loads(progress_path.read_text(encoding='utf-8'))
    assert progress['source_and_local_reviews'] == progress['total_technologies'] == 125
    progress.update(overall_status='COMPLETED', complete_release_gate='PASS', production_delivered=True,
        completed_at=datetime.now(timezone.utc).isoformat(), release=ref(receipt_path), delivery=ref(live_path),
        tested_image=receipt['image_id'], running_image=live['running_image'],
        source_sha256=receipt['release']['source_sha256'], verification_sha256=receipt['verification_sha256'],
        verification_scope='125 individual source/parameter reviews; full backend and frontend regression; real isolated browser and HTTP acceptance for selected supported workflows. No claim of all 125 executable protocol models or real hardware certification.',
        backend_passed=int(passed[-1]))
    progress.setdefault('release_history', []).append({'status': 'PASS', 'evidence': ref(receipt_path),
        'scope': 'Full gate followed by exact tested image production delivery and read-only live verification.'})
    for technology in progress['technologies']:
        technology.update(production_delivered=True, release_gate='PASS',
                          status='SOURCE_PARAMETERS_VERIFIED_AND_DELIVERED')
    save(progress_path, progress)
    findings_path = FOLDER / 'consumer-findings.md'
    findings = findings_path.read_text(encoding='utf-8')
    pending = 'Die Einzelprüfungen und die Quellenkorrekturen sind dokumentiert. Die gemeinsame vollständige Abnahme und exakte produktive Übernahme sind bis zum vorhandenen PASS-/Deployment-Nachweis offen. Einzeltests und diese Inventarliste allein sind kein neunphasiger E2E-PASS.'
    assert pending in findings
    findings_path.write_text(findings.replace(pending,
        'Die 125 Einzelprüfungen und die gemeinsame vollständige Regression sind abgeschlossen. Der vollständige Release-Gate ist PASS; das exakt geprüfte Image ist produktiv übernommen und anhand von Image-/Quellidentität, API und Betriebsbereitschaft verifiziert. Die tatsächlichen neunphasigen ALL-Scope-Abnahmen der kleinen und großen isolierten Referenzfälle stehen im PASS-Nachweis. Die übrigen Profilprüfungen bestätigen Parametersemantik und Datenisolation, keine ausführbare Simulation aller 125 Technologien und keine reale Gerätequalifikation.'), encoding='utf-8')
    report_path = FOLDER / 'abschluss.md'
    report_path.write_text(f'''# Abschluss der Technologieparameter-Prüfung

- **Status:** vollständig geprüft und produktiv übernommen.
- **Profile:** 125/125 einzeln geprüft; {inventory['total_fields']:,} Editorfelder und {inventory['total_constraints']:,} Regeln.
- **Backend:** {int(passed[-1]):,} Tests bestanden; verbleibende Skips und Warnungen stehen im vollständigen Testlog.
- **Frontend:** vollständiger TypeScript- und Frontend-Testlauf bestanden.
- **Release:** alle Pflichtprüfungen PASS, einschließlich echter Browser-/HTTP-Workflows, persistierter Simulation, Neustart-/Wiederaufnahme und großer Referenzanforderung.
- **Produktives Image:** `{receipt['image_id']}`.
- **Quellidentität:** `{receipt['release']['source_sha256']}`; getestete Quellfassung entspricht der laufenden Fassung.
- **Erhalt:** historische Images und die erfassten Parameter des vorhandenen Projekts erhalten; keine Tests auf der produktiven Datenbank.
- **Dokumentation:** README mit Fähigkeiten, allen Verbindungstypen, Vorschlägen, Bestätigungsnachweisen und Modellgrenzen aktualisiert.

## Geprüfte Korrekturen

Eigenständige, branchenneutrale Profile und Standards je Technologie; keine CAN-/Ethernet-Ratenübernahme zwischen fremden Bussen. Verlustfreie große Ganzzahlen, native bedingte Werte und Nachweise, vollständiger profilgebundener Export, erhaltener Bestätigungsstatus bei Teilgruppen, konsistente Ratenaliase und strenge Konfliktprüfung. Der genaue ursprüngliche Ventilaktor-Satz wird konkret erkannt. Registry-Vorschläge bestätigen keine Adressen, Gerätefähigkeiten, Clock Stretching oder Transaktionszeiten.

## Tatsächlicher Umfang

Alle 125 Profile sind konfigurierbar und haben einzeln geprüfte Parametersemantik. Sechs Profile haben registrierte Kapazitätsmodelle, 115 bleiben ausdrücklich `MODEL_MISSING`, vier direkte I/O-Profile `NOT_APPLICABLE`. Die kleine und große isolierte Referenzanforderung sind neunphasige ALL-Scope-Abnahmen. Die qualifizierten virtuellen LIN-/Ethernet-Eingaben dieser Fälle ersetzen keine reale Hardware-, PHY-, Security- oder LDF-Qualifikation.

Die bestehende unabhängige ToolChecker-Masterkampagne wurde nicht zurückgesetzt oder als bestanden markiert. Dieser Abschluss bezieht sich auf den freigegebenen Technologieparameter-Auftrag und seinen vollständigen Projekt-Release-Gate.

Im großen Referenzfall bleiben 1.404 Signalverträge erhalten. Die HTTP-Abnahme beobachtet {large['assessment']['observed_signal_count']:,} transportierte Signale; {len(large['assessment']['scope_coverage']['excluded_signal_ids']):,} Signale sind mit ausdrücklichem Ausschluss außerhalb des Transports dokumentiert. Dies ist keine physikalische Simulation sämtlicher 1.404 Signale.

## Nachweise

- [PASS-Nachweis]({receipt_path.as_posix()})
- [Backend-Log]({backend_log.as_posix()})
- [Frontend-Log]({frontend_log.as_posix()})
- [Browser-Bericht]({browser_path.as_posix()})
- [Kleine neunphasige HTTP-Abnahme]({small_path.as_posix()})
- [Große neunphasige HTTP-Abnahme]({large_path.as_posix()})
- [Produktive Prüfung]({live_path.as_posix()})
- [Feldabdeckung aller 125 Profile]({coverage_path.as_posix()})
- [README]({(ROOT / 'README.md').as_posix()})
''', encoding='utf-8')
    work_path = FOLDER / 'workload.json'
    work = json.loads(work_path.read_text(encoding='utf-8'))
    before, after, diffs, changed = [], [], [], []
    for relative in work['revision_before']:
        source, original = ROOT / relative, FOLDER / 'before' / relative
        if not source.exists() or not original.exists() or source.read_bytes() == original.read_bytes():
            continue
        target, delta = FOLDER / 'after' / relative, FOLDER / 'diff' / (relative + '.diff')
        target.parent.mkdir(parents=True, exist_ok=True)
        delta.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        delta.write_text(''.join(difflib.unified_diff(original.read_text(encoding='utf-8').splitlines(keepends=True),
            source.read_text(encoding='utf-8').splitlines(keepends=True), fromfile='before/' + relative,
            tofile='after/' + relative)), encoding='utf-8')
        changed.append(relative)
        before.append(ref(original)); after.append(ref(target)); diffs.append(ref(delta))
    sources = [ref(path) for path in individual_files]
    gate_refs = [ref(receipt_path), ref(backend_log), ref(frontend_log), ref(browser_path), ref(small_path), ref(large_path), ref(coverage_path)]
    work.update(completion_status='COMPLETED', files_changed=changed, before=before, after=after, diff=diffs,
                remaining_findings=[], unresolved_decisions=[], completion_report=ref(report_path))
    work['validations'] = {name: {'status': 'PASSED', 'evidence': gate_refs + [ref(live_path), ref(progress_path)]}
                           for name in work['validation_requirements']}
    work['validation'] = work['validations']
    work['outcomes'] = {name: {'status': 'PASSED', 'evidence': [ref(progress_path), ref(report_path),
                       *sources, *gate_refs, ref(live_path)]} for name in work['required_outcomes']}
    work['tests'] = [{**row, 'production_delivered': True, 'release_gate': 'PASS',
                     'evidence': [ref(FOLDER / 'individual' / (row['technology'] + '.json'))]}
                    for row in work['tests']]
    work['delivery'] = {'decision': 'YES', 'authorization': 'AGENTS.md standing production authorization and user Freigabe / vollständig fertig stellen',
        'target': 'Canonical NetworkIS production stack on port 13500',
        'tested_version': receipt['image_id'], 'running_version': live['running_image'],
        'checks': {name: {'status': 'PASSED', 'evidence': [ref(receipt_path), ref(live_path)]}
                   for name in ('release', 'deployment', 'health', 'functional')}}
    work['documentation_followup']['status'] = 'COMPLETED_VERIFIED_DELIVERY'
    save(work_path, work)
    print(json.dumps({'status': 'COMPLETED', 'profiles': 125, 'backend_passed': int(passed[-1]),
                      'image_id': receipt['image_id'], 'report': str(report_path)}))

if __name__ == '__main__':
    main()

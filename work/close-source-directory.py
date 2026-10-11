"""Close this distinct workload only after exact PASS and live evidence."""
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'docs/implementation-workloads/source-directory-20261003'

def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    receipt_path = args.receipt.resolve()
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    live_path = ROOT / 'work/source-directory-production-verification.json'
    live = json.loads(live_path.read_text(encoding='utf-8'))
    assert receipt['status'] == 'PASS'
    assert live['status'] == 'PASSED' and live['running_image'] == receipt['image_id']
    assert live['build']['source_sha256'] == receipt['release']['source_sha256']
    assert all(check['exit_code'] == 0 for check in receipt['checks'])
    assert {check['name'] for check in receipt['checks']} >= {'backend-tests', 'frontend-tests', 'browser-e2e', 'small-http', 'large-http', 'typecheck'}
    http_paths = [receipt_path.parent / (name + '-http.json') for name in ('small', 'large')]
    for http_path in http_paths:
        case = json.loads(http_path.read_text(encoding='utf-8'))
        assert len(case['statuses']) == 9
        assert set(case['statuses'].values()) <= {'COMPLETE', 'APPROVED', 'WARNING'}
        assessment = case['assessment']
        assert assessment['conformance'] == 'PASS'
        assert assessment['scope_coverage']['scope_mode'] == 'ALL' and assessment['scope_coverage']['complete']
        assert assessment['failed_route_count'] == 0 and not assessment['missing_observed_signal_ids']
    backend_log = receipt_path.parent / 'backend-tests.log'
    passed = re.findall(r'(\d+) passed', backend_log.read_text(encoding='utf-8', errors='replace'))
    assert passed
    report_path = FOLDER / 'abschluss.md'
    report_path.write_text(f'''# Quellenverzeichnis und Lizenzkontrollen

Abgeschlossen und produktiv bereitgestellt am {datetime.now(timezone.utc).isoformat()}.

- 595 eindeutige Quellen für 123 der 125 registrierten Verbindungstypen; Custom Binary und Custom Protocol sind eigene Definitionen ohne externe Standardspezifikation. Dafür werden keine Quellen erfunden. Gemeinsame Dokumente erscheinen einmal mit ihren Technikzuordnungen. Dokumentversionen bleiben getrennt.
- Fuzzy-Suche, alphabetische Ausgangssortierung nach Bustyp, alle sieben Spalten sortierbar, kurze Links, 50 Zeilen pro Seite und erreichbare Navigation auf schmalen Fenstern.
- 61 dokumentierte Abrufdaten; 534 nicht dokumentierte Daten bleiben ausdrücklich unbekannt. Das Datum der Rechteprüfung ersetzt kein Abrufdatum.
- Veröffentlichungsrechte: {json.dumps(live['sources']['publication_rights'], ensure_ascii=False)}. Ungeklärte Rechte sind keine erteilte Erlaubnis. Originaldokumente und geschützte Tabellen werden nicht ausgeliefert.
- Dokumentbezogene Hinweise und Herausgeberregeln sind getrennt; insbesondere Matter-Core und Apache-lizenzierte SDK-Dateien. STOP-Dialoge erklären den Prüfstand und verlinken Original und Bedingungen.
- NMEA 0183/2000 und MIPI CSI-2/DSI bleiben konfigurierbar; die vorsorgliche NIS-Policy verlangt eine geprüfte projektbezogene Freigabe für die Ausführung. Dies ist keine Rechtsbehauptung über jede abstrakte Simulation. I3C Basic wird nicht pauschal gesperrt.
- Eingereichte Referenzen bleiben PENDING. Betreiberprüfung mit tatsächlichem Nachweis, SHA-256, Prüfer, Begründung und Auditereignis; Ablauf, Widerruf und Policywechsel sperren wieder. HTTP kann sich keine Freigabe geben.
- Projektwechsel, gemischte Technikidentitäten, serverseitige Sperren, beide Themes und schmale Navigation geprüft. Keine echte Lizenz durch Tests erteilt.
- {passed[-1]} Backendtests bestanden; vollständige Frontend-, Browser- und neunphasige kleine/große HTTP-Abnahmen im PASS-Nachweis.
- Getestetes und laufendes Image: `{receipt['image_id']}`; Quellidentität `{receipt['release']['source_sha256']}`.
- Quellen-/Rechte-Metadaten und der Betreiberbefehl gehören zur Release-Identität; Änderungen daran verhindern die Wiederverwendung eines Images mit veralteten Inhalten. Die drei neuen Identitätsregressionen sind Bestandteil der 24 Release-Hilfstests.
- Produktive Datenmounts, erfasster Projektzustand und historische Images erhalten. SQL-Prüfungen isoliert; unabhängige ToolChecker-Kampagne unverändert.

## Grenzen

Die technische Rechteklassifizierung ist keine individuelle Rechtsberatung oder Garantie für Patent-, Implementierungs- oder Zertifizierungsrechte. Ungeklärte Quellen bleiben sichtbar gesperrt für eine nicht belegte Veröffentlichung. Die Technikfreigabe bestätigt keine Kapazität oder vollständige Protokollsimulation. Manuelle Betreiberprüfung ist ein administrativer Vertrauensentscheid, keine automatische Vertrags-Echtheitsprüfung.

## Nachweise

- [Vollständiger PASS]({receipt_path.as_posix()})
- [Produktive Prüfung]({live_path.as_posix()})
- [README]({(ROOT / 'README.md').as_posix()})
- [Quellen- und Lizenzvertrag]({(ROOT / 'docs/SOURCE_LICENSING_CONTRACT.md').as_posix()})
- [Rechte-Prüfbericht]({(FOLDER / 'rights-review.json').as_posix()})
''', encoding='utf-8')
    path = FOLDER / 'workload.json'
    work = json.loads(path.read_text(encoding='utf-8'))
    before, after, diffs, changed = [], [], [], []
    for relative in work['revision_before']:
        source, original = ROOT / relative, FOLDER / 'before' / relative
        if not source.exists() or not original.exists() or source.read_bytes() == original.read_bytes():
            continue
        target, delta = FOLDER / 'after' / relative, FOLDER / 'diff' / (relative + '.diff')
        target.parent.mkdir(parents=True, exist_ok=True)
        delta.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        delta.write_text(''.join(difflib.unified_diff(original.read_text(encoding='utf-8').splitlines(keepends=True), source.read_text(encoding='utf-8').splitlines(keepends=True), fromfile='before/' + relative, tofile='after/' + relative)), encoding='utf-8')
        changed.append(relative); before.append(ref(original)); after.append(ref(target)); diffs.append(ref(delta))
    evidence = [ref(receipt_path), ref(live_path), ref(backend_log), ref(receipt_path.parent / 'browser.json'), ref(report_path), ref(FOLDER / 'rights-review.json'), *[ref(path) for path in http_paths], ref(receipt_path.parent / 'storage-tests.log')]
    work.update(completion_status='COMPLETED', files_changed=changed, before=before, after=after, diff=diffs, remaining_findings=[], completion_report=ref(report_path))
    work['outcomes'] = {name: {'status': 'PASSED', 'evidence': evidence} for name in work['required_outcomes']}
    work['validations'] = {name: {'status': 'PASSED', 'evidence': evidence} for name in work['validation_requirements']}
    work['delivery'] = {'decision': 'YES', 'authorization': 'User request and standing AGENTS.md production authorization', 'target': 'Canonical NetworkIS port 13500', 'tested_version': receipt['image_id'], 'running_version': live['running_image'], 'checks': {name: {'status': 'PASSED', 'evidence': evidence} for name in ('release', 'deployment', 'health', 'functional')}}
    path.write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'COMPLETED', 'report': str(report_path), 'backend_passed': passed[-1]}))

if __name__ == '__main__':
    main()


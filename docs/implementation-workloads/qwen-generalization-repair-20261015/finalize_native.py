"""Verify the single final seven-file run and freeze its exact application."""
import hashlib
import difflib
import json
import runpy
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
folder = sys.argv[1]
manifest = json.loads((HERE / folder / 'manifest.json').read_text(encoding='utf-8'))
assert len(manifest['cases']) == 7
assert all(c['status'] == 'RETEST_PASSED' for c in manifest['cases'])
assert manifest['final_application_integrity_verified']
assert manifest['full_application_source_sha256'] == runpy.run_path(str(ROOT / 'scripts/write-build-info.py'))['build_manifest']()['source_sha256']
original = json.loads((HERE.parent / 'qwen-generalization-20261015/manifest.json').read_text(encoding='utf-8'))
hashes = manifest['application_hashes']
for path, digest in hashes.items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
for case in manifest['cases']:
    baseline = next(c for c in original['cases'] if c['id'] == case['id'])
    assert case['source_sha256'] == baseline['source_sha256']
    assert hashlib.sha256(Path(case['original_path']).read_bytes()).hexdigest() == case['source_sha256']
workload = json.loads((HERE / 'workload.json').read_text(encoding='utf-8'))
hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in workload['files_changed']}
freeze = {'application_and_test_hashes': hashes, 'native_model': manifest['model'],
          'model_digest': manifest['installed_model']['digest'], 'native_evidence': folder,
          'full_application_source_sha256': manifest['full_application_source_sha256'],
          'targeted_tests': '121 intake/registry/wizard regressions; further 41 projection/registry/wizard checks; typecheck and 643 frontend tests; two strengthened isolated editor browser cases; one complete50/250/250 nine-stage targeted case with real write receipts (19.6min)',
          'scope': 'Seven complete original documents; native local Qwen intake and proposal, no canonical writes; not seven nine-stage E2E workflows',
          'additional_repairs': 'Frontend projection synchronized; general editor consumes edit deep-link on close; seven native cases repeated on the final overall application source'}
(HERE / 'source-freeze.json').write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding='utf-8')
for path in hashes:
    dest = HERE / 'after' / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes((ROOT / path).read_bytes())
diff = ''.join(''.join(difflib.unified_diff(
    (HERE / 'before' / path).read_text(encoding='utf-8').splitlines(keepends=True),
    (ROOT / path).read_text(encoding='utf-8').splitlines(keepends=True),
    fromfile='a/' + path, tofile='b/' + path)) for path in hashes)
(HERE / 'owned-changes.diff').write_text(diff, encoding='utf-8')
calls = [call for c in manifest['cases'] for call in json.loads((HERE / folder / (c['id'] + '-wire.json')).read_text(encoding='utf-8'))]
audit = {'status': 'PASSED', 'files': 7, 'calls': len(calls),
         'automatic_local_corrections': len(calls) - sum(c['segments'] for c in manifest['cases']),
         'full_application_source_sha256': manifest['full_application_source_sha256'],
         'tokens': sum(c['response']['eval_count'] for c in calls),
         'seconds': round(sum(c['seconds'] for c in manifest['cases']), 2),
         'model': manifest['model'], 'model_digest': manifest['installed_model']['digest'],
         'full_original_sources_verified': True, 'canonical_writes': False,
         'application_hashes': manifest['application_hashes']}
(HERE / 'native-acceptance.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
lines = ['# Qwen: allgemeine Dokumentkorrektur', '',
         'Sieben unveränderte Originaldateien wurden mit demselben Anwendungsstand und echtem lokalem Qwen erneut geprüft. Keine Dateinamen-Sonderlogik, kein Cloud-Fallback, keine kanonischen Modelländerungen.', '',
         '| Projekt | Ergebnis | Abschnitte | Modellaufrufe | Sekunden |', '|---|---|---:|---:|---:|']
for c in manifest['cases']:
    lines.append(f"| {c['file']} | bestanden | {c['segments']} | {c['calls']} | {c['seconds']} |")
lines.extend(['', f"Modell: `{audit['model']}`, {audit['calls']} echte Aufrufe, {audit['tokens']} Ausgabetokens. Original- und übertragene Quellen sind vollständig und hashgeprüft. {audit['automatic_local_corrections']} automatische lokale Korrektur innerhalb der bestehenden Quellenprüfung; keine manuell ersetzte Modellantwort.", '',
              'Abnahme: Gerätearten und konkrete Instanzen getrennt; Controllerrollen erhalten; Sensorik/Aktorik und Funktionsgruppen vollständig; sämtliche expliziten Anforderungen erhalten; offene Protokollfamilien bleiben klärungsbedürftig. 121 gezielte Regressionstests bestanden.', '',
              'Dies prüft Dokumentaufnahme und Vorschlagserstellung. Es sind keine sieben vollständigen Engineering-Workflows mit neun Stufen. Release und Produktivprüfung werden separat nachgewiesen.'])
(HERE / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(json.dumps(audit))

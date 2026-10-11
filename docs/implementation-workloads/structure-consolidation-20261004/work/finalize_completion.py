"""Complete the audit only from the successful delivered release evidence."""
import hashlib
import json
from pathlib import Path

from edit_utils import OUT, ROOT

receipt_path = ROOT / 'backend/test-output/release-gates/delivery-ffc6f9dda8d7/bdc9bef1951e/receipt.json'
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
production = json.loads((OUT/'production-verification.json').read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS'
assert len(receipt['checks']) == 8 and all(item['exit_code'] == 0 for item in receipt['checks'])
assert production['status'] == 'PASS' and production['tested_image_matches_running']
assert production['image_id'] == receipt['image_id']
assert production['source_sha256'] == receipt['release']['source_sha256']
assert '"status": "DEPLOYED"' in (OUT/'delivery-release.log').read_text(encoding='utf-8-sig')
owners = json.loads((OUT/'ownership-after.json').read_text(encoding='utf-8'))
assert not owners['physically_empty'] and not owners['docstring_only_leaf_packages']
small = json.loads((receipt_path.parent/'small-http.json').read_text(encoding='utf-8'))
large = json.loads((receipt_path.parent/'large-http.json').read_text(encoding='utf-8'))
for result in (small, large):
    assessment = result['assessment']
    assert assessment['conformance'] == 'PASS' and assessment['failed_route_count'] == 0
    assert assessment['evaluated_route_count'] == assessment['expected_route_count']
    assert len(result['statuses']) == 9

report_path = OUT/'completion-report.md'
report = report_path.read_text(encoding='utf-8')
report = report.replace('**VOLLSTÄNDIGER RELEASE- UND DEPLOYMENTLAUF LÄUFT**',
                        '**ABGESCHLOSSEN, AUSGELIEFERT UND IN PRODUKTION VERIFIZIERT**')
report = report.replace('`installed-package-final.json`', '`installed-package-release.json`')
report = report.replace('`checker-delivery-result.json`', '`checker-release-result.json`')
report = report.replace('- `final-targeted-complete.xml`: 290 gezielte Tests und 56 Subtests bestanden; eine vorhandene Modellfeldwarnung.',
    '- `final-targeted-complete.xml`: 290 gezielte Tests und 56 Subtests bestanden; eine vorhandene Modellfeldwarnung. `wildcard-imports.xml`: elf Fälle nach der abschließenden Exportkorrektur bestanden. Diese überlappenden Läufe werden nicht als 301 unabhängige Tests addiert.')
report = report.replace('- `before-index.json`, `after-index.json`, `changes.patch`: ursprüngliche Snapshots, neue Dateien und Entfernungseinträge; nur Änderungen dieses Auftrags. Bestehende Änderungen und historische Nachweise bleiben erhalten.',
    '- `before-index.json`, `after-index.json`, `changes.patch`: ursprüngliche Snapshots, neue Dateien und Entfernungseinträge; nur Änderungen dieses Auftrags. 197 geänderte Dateien: 123 entfernt, 36 erstellt und 38 geändert. Bestehende Änderungen und historische Nachweise bleiben erhalten.')
report = report.split('## Release und Produktion')[0] + f'''## Release und Produktion

`backend/.venv/Scripts/python.exe scripts/release-and-deploy.py` ist mit Exitcode 0
abgeschlossen. Der vollständige Receipt steht auf **PASS**, alle acht Checks auf
Exitcode 0. Derselbe Befehl hat das exakte getestete Image auf die kanonische
Produktionsinstanz `NetworkIS` ausgeliefert und die laufende Identität geprüft.

- Receipt: `{receipt_path.relative_to(ROOT).as_posix()}`.
- Getestetes und laufendes Image: `{receipt['image_id']}`.
- Geprüfter und laufender Quellhash: `{receipt['release']['source_sha256']}`.
- Backend: **21.564 Tests und 56 Subtests bestanden**, zwei übersprungen, eine Warnung.
- Frontend: **564 Tests bestanden**, TypeScript-Prüfung bestanden.
- Browser: **86 Fälle bestanden**, einschließlich neun Stufen, Wiederherstellung,
  echter Modellübernahme und des bestätigten großen 50/250/250-Auftrags.
- HTTP, klein: neun Stufen, **6/6 Routen**, 18 erforderliche und beobachtete Signale,
  Konformität PASS und keine fehlgeschlagene Route.
- HTTP, groß: neun Stufen, **766/766 Routen**, 594 transportpflichtige Nachrichten
  und 1.169 erforderliche Signale vollständig abgedeckt, Konformität PASS und keine
  fehlgeschlagene Route. 59 Nachrichten mit 235 internen, nicht gerouteten Signalen
  bleiben ausdrücklich vom Transportscope ausgeschlossen; für sie wird keine
  funktionale Beobachtung oder Timing-Freigabe behauptet. Fachliche Warnungen im
  großen Szenario wurden über den echten Preflight-Freigabeschritt behandelt und
  bleiben sichtbar. Transportkonformität ersetzt keine funktionale Timing-Abnahme.
- Produktion: `healthy`, Readiness für Datenbank und Speicher vorhanden. Native
  CAN-/Ethernet-Erzeugung, Paketbytes, LIN-Ausrichtung, Zeitstempelpräzision,
  212 alte Importidentitäten und fünf Generator-Wildcard-Exporte bestanden.
  Beide früheren physischen Technologiequellbäume sind auch im Image abwesend.
- Der gesamte Technologiekatalog stimmt vor und nach der Auslieferung überein
  (125 Profile). `/api/ready`, `/api/build-info` und `/api/technologies` sind sowohl
  lokal als auch über LAN geprüft. Nachweise: `production-running-image.json`,
  `production-native-smoke.json`, `production-verification.json`,
  `delivery-release.log` und die Browser-/HTTP-Berichte neben dem Receipt.

Zwei frühere eigene Gate-Läufe wurden **vor dem Imagebau** als ABORTED beendet:
zunächst zur Entfernung der letzten zwei Technologie-Paketwurzeln, danach zur
Erhaltung der historischen Generator-Wildcard-Exporte. Diese Läufe sind keine
PASS-Nachweise. Der oben bezeichnete finale Lauf prüft und liefert den endgültigen
Quellstand aus. Historische Images wurden nicht bereinigt.

Zugriff: [Lokal](http://localhost:13500) · [VPN/LAN](http://192.168.178.10:13500).

## Abschluss und Grenzen

Die sechs erforderlichen Ergebnisse und fünf Validierungen dieses Auftrags sind
mit Datei-Hashes im `workload.json` belegt. Es bleiben keine offenen Befunde dieses
Auftrags. Der Completion-Guard bestätigt den Abschluss separat in
`completion-guard.json`; die historische EA-Kampagne wird dadurch nicht als PASS
erklärt. Die bestehenden vollständigen Release-Tests sowie die neuen Eigentümer-
und Importregressionen schützen den konsolidierten Bestand.

Der Nachweis umfasst den lokalen kanonischen Quellbestand, seine beobachtbaren
Verbraucher, das separat installierte Paket und die ausgelieferte Anwendung.
Nicht beobachtbare externe oder persistierte Verbraucher bleiben als Grenze der
Abhängigkeitsinventur ausgewiesen. Reale Workflow-/Automationsmetadaten und
veröffentlichte ausführbare Kompatibilitätseinstiege bleiben begründet erhalten.
'''
report_path.write_text(report, encoding='utf-8')

def evidence(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def passed(*paths):
    return {'status': 'PASSED', 'evidence': [evidence(path) for path in paths]}

workload_path = OUT/'workload.json'
work = json.loads(workload_path.read_text(encoding='utf-8'))
equivalence = OUT/'behavior-equivalence.json'
inventory = OUT/'ownership-after.json'
checker = OUT/'checker-release-result.json'
work['outcomes'] = {
    'native_format_ownership': passed(equivalence, inventory, OUT/'installed-package-release.json'),
    'simulation_technology_ownership': passed(equivalence, inventory, OUT/'production-native-smoke.json'),
    'assessment_technology_ownership': passed(equivalence, inventory, receipt_path),
    'empty_scaffolding_removed': passed(inventory, OUT/'removed-directories.json', OUT/'remove-last-technology-roots-files.json'),
    'complete_dependency_evidence': passed(ROOT/'docs/migrations/structure_mapping.csv', OUT/'alias-inventory-verification.json', inventory),
    'production_delivery': passed(receipt_path, OUT/'delivery-release.log', OUT/'production-verification.json'),
}
work['validations'] = {
    'behavior_equivalence': passed(equivalence),
    'targeted_regressions': passed(OUT/'final-targeted-complete.xml', OUT/'wildcard-imports.xml', OUT/'installed-package-release.json'),
    'architecture': passed(checker, inventory),
    'full_release_gate': passed(receipt_path, receipt_path.parent/'browser.json', receipt_path.parent/'small-http.json', receipt_path.parent/'large-http.json'),
    'production_verification': passed(OUT/'production-verification.json', OUT/'production-native-smoke.json'),
}
for name, path in [('before', 'before-index.json'), ('after', 'after-index.json'), ('diff', 'changes.patch')]:
    work[name] = [evidence(OUT/path)]
work['remaining_findings'] = []
work['completion_status'] = 'COMPLETED'
work['delivery'].update(status='DEPLOYED', receipt=str(receipt_path),
    tested_version=receipt['image_id'], running_version=production['image_id'],
    source_sha256=production['source_sha256'], checks={
        'release': passed(receipt_path),
        'deployment': passed(OUT/'delivery-release.log', OUT/'production-running-image.json'),
        'health': passed(OUT/'production-running-image.json', OUT/'production-verification.json'),
        'functional': passed(OUT/'production-verification.json', OUT/'production-native-smoke.json'),
    })
work['completion_report'] = evidence(report_path)
workload_path.write_text(json.dumps(work, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'status': 'EVIDENCE_COMPLETED', 'image_id': receipt['image_id'], 'outcomes':len(work['outcomes']), 'validations':len(work['validations'])}))

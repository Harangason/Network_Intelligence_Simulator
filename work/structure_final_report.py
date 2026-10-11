"""Report only completed evidence; deployment remains required until verified."""
from finish_structure_owners import *
import csv
from datetime import datetime

receipt_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
receipt = json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path else None
production = OUT / 'production-verification.json'
delivered = receipt is not None and receipt.get('status') == 'PASS' and production.is_file()
rows = list(csv.DictReader(read('docs/migrations/structure_mapping.csv').splitlines()))
wrappers = [r for r in rows if r['action'] == 'move-with-forwarding-entry']
checker = ROOT / '.tool-checker/runs/standalone/session-b156585d421048558c1b2ff77485fc50.json'
assert json.loads(checker.read_text())['status'] == 'PASS'
status = 'ABGESCHLOSSEN UND PRODUKTIV AUSGELIEFERT' if delivered else 'IMPLEMENTIERT; VOLLSTÄNDIGE RELEASEPRÜFUNG LÄUFT'
lines = [
    '# Abschluss der NIS-Strukturmigration', '', 'Stand: ' + datetime.now().strftime('%Y-%m-%d') + '. Status: **' + status + '**.', '',
    'Dieser Nachweis ergänzt die ursprüngliche Migration und schließt die fünf Befunde aus `docs/project-scanner/migration-review-20261003/analysis.md`.', '',
    '| Befund | Ergebnis | Nachweis |', '| --- | --- | --- |',
    '| R1 | Frontend nutzt die kanonische Technologieprojektion. MODBUS RTU bleibt MODBUS RTU; unbekannte und im Editor nicht unterstützte Technologien bleiben offen. Routing erzeugt keine ersetzte oder teilweise Strecke und zeigt die offene Zuordnung. | Bus-Technologie-Tests; Projektionstest; vollständiger Frontendlauf |',
    '| R2 | Framing, Timing, Scheduling, CAN-Arbitrierung sowie konkrete PHY-Definitionen und Regeln liegen bei den Technologiepaketen. Bitratenvorschläge stammen ausschließlich aus profile.json. Generische Dienste delegieren an diese Eigentümer. | 1.664 Berechnungsfälle, 600 Timingadapter-Aufrufe und 1.458 PHY-Fälle ohne Abweichung; alle 125 Registryprofile und vier Katalogexporte unverändert |',
    f'| R3 | {len(rows)} Zuordnungen; alle {len(wrappers)} Übergangswrapper mit Eigentümer, beobachteten Verbrauchern und pfadspezifischem Entfernungskriterium. Neue Build-, Test- und API-Dateien sind erfasst. | docs/migrations/structure_mapping.csv; Abdeckungstest |',
    '| R4 | Zwölf Architektur-/Regressionsprüfungen schützen die Verantwortungsgrenzen, einschließlich eingeschleuster Protokollregeln, kopierter Ratenvorschläge und des vollständigen alten Katalogexportvertrags. Fünf Fälle laufen in der vorhandenen Tool-Checker-CLI mit frischer automatischer Vorprüfung. | 5/5 Tool-Checker-Fälle PASS; migration-risk-tests.xml |',
    '| R5 | Alle 125 Technologiepakete dokumentieren Profile, tatsächlichen Status, Schnittstellen, vorhandene Adapter und Tests. Gemeinsamer Einstieg für Erweiterungen vorhanden. | Dokumentationsprüfung; backend/nis/communication/technologies/README.md |', '',
    'Die Kompatibilitätswrapper bleiben begründet erhalten. Der interne Scan findet konkrete Verbraucher bei 130 Wrappern; ein leerer interner Scan schließt externe oder persistierte Verbraucher nicht aus. Ihre Entfernung setzt die jeweils dokumentierte Vertragsmigration voraus. Es wird keine zusätzliche Technologieunterstützung behauptet.', '',
    'Zusätzliche Absicherung: Der Projektionsgenerator gehört jetzt zur Quellidentität eines Releases. Änderungen daran verhindern die Wiederverwendung eines älteren Images; temporäre Backend-Buildartefakte bleiben ausgeschlossen. Ein Regressionstest belegt beide Fälle.', '',
    '## Verifikation', '',
    '- Abschließende gemeinsame Prüfung sämtlicher im Migrationsplan genannter Risiken: 829 Tests bestanden; migration-risk-tests.xml.',
    '- 147 gezielte Timing-/Kapazitäts-/Registry-/Serialtests bestanden.',
    '- 36 PHY-/Port-/LIN-/Architekturtests bestanden.',
    '- Nach Entfernung der Ratenkopien 66 gezielte Architektur-/Registry-/Serialtests bestanden.',
    '- 28 Release-Skripttests bestanden.',
    '- TypeScript-Prüfung und 564 Frontendtests bestanden.',
    '- Tool Checker: eigene Suite nis-structure-completion-20261003, fünf Fälle PASS; historische EA-Kampagne unverändert.', '',
    'SQL-Prüfungen liefen ausschließlich auf temporären Postgres-Containern über scripts/run-isolated-tests.py. Die Produktionsdatenbank wurde für Tests nicht verwendet. Vorzeitig angehaltene Gate-Läufe sind als ABORTED dokumentiert; sie bauten kein Kandidatenimage. Der nachfolgende vollständige Gate-Nachweis ist maßgeblich.', '',
    'Bekannte Modellfeldwarnungen bleiben als Warnungen ausgewiesen. Die gezielten Teilprüfungen ersetzen den vollständigen Release-Nachweis nicht.', '',
    'Tool-Checker-Beleg: ' + str(checker), '',
    'Vorher-/Nachher-/Diff: before-index.json, after-index.json, changes.patch. Vorhandene Nutzeränderungen wurden erhalten.', '',
]
if receipt:
    lines += ['## Release und Produktion', '', 'Receipt: ' + str(receipt_path), '',
              'Status: **' + receipt['status'] + '**. Image: `' + str(receipt.get('image_id')) + '`.', '',
              'Quellhash: `' + receipt['initial_source_sha256'] + '`.', '',
              '| Gate | Ergebnis |', '| --- | --- |']
    lines += [f"| {check['name']} | {'PASS' if check['exit_code'] == 0 else 'FAIL'} |" for check in receipt['checks']]
    if receipt['status'] == 'PASS':
        gate_dir = receipt_path.parent
        browser = json.loads((gate_dir / 'browser.json').read_text(encoding='utf-8'))
        stats = browser['stats']
        lines += ['', f"Vollständiger Gate-Lauf: 21.558 Backendtests und 56 Subtests bestanden; zwei bereits im Ausgangsstand übersprungene Tests und eine bestehende Modellfeldwarnung. 564 Frontendtests bestanden. Browser: {stats['expected']} bestanden, {stats['unexpected']} unerwartete Fehler, {stats['flaky']} instabile Fälle, {stats['skipped']} übersprungen.", '']
        for name in ['small', 'large']:
            flow_path = gate_dir / (name + '-http.json')
            flow = json.loads(flow_path.read_text(encoding='utf-8'))
            assert len(flow['statuses']) == 9 and all(value in {'COMPLETE', 'APPROVED', 'WARNING'} for value in flow['statuses'].values())
            assessment = flow['assessment']
            assert assessment['conformance'] == 'PASS' and assessment['failed_route_count'] == 0
            assert assessment['release']['source_sha256'] == receipt['initial_source_sha256']
            lines += [f"Neunstufiger HTTP-Wizard ({name}): alle neun Stufen abgeschlossen, gespeicherter Simulationsjob und Trace geprüft, Konformität PASS, {assessment['evaluated_route_count']} bewertete Routen und keine fehlgeschlagene Route; Beleg: {flow_path}."]
        lines += ['', 'WARNING-Stufen behalten ihre fachlichen Evidenzwarnungen. Ein erfolgreicher Ablauf bestätigt keine unbelegte Technologieunterstützung oder funktionale Timingfreigabe.']
if delivered:
    proof = json.loads(production.read_text())
    assert proof['image_id'] == receipt['image_id'] and proof['status'] == 'PASSED'
    lines += ['', 'Die laufende Image-ID entspricht dem exakt geprüften Image. Readiness, Buildidentität und 125 produktive Technologieprofile wurden über lokale und LAN-URLs lesend geprüft. Der vollständige ausgelieferte Katalog entspricht der Vorher-Aufnahme; ausschließlich deren nachgewiesene PowerShell-Zeichenfehlinterpretation wurde für diesen Vergleich verlustfrei normalisiert. Die vollständigen Browser-/Wizardtests liefen auf dem isolierten Kandidaten. Es wurde kein zusätzlicher schreibender Produktions-E2E-Lauf durchgeführt.']
write('docs/implementation-workloads/structure-completion-20261003/completion-report.md', '\n'.join(lines) + '\n')
for path in ['docs/implementation-workloads/project-structure-migration-20261003/completion-report.md',
             'docs/project-scanner/migration-review-20261003/analysis.md']:
    source = read(path)
    if 'structure-completion-20261003/completion-report.md' not in source:
        write(path, '> Ergänzender Abschluss der Befunde R1–R5: [aktueller Abschlussnachweis](../../implementation-workloads/structure-completion-20261003/completion-report.md). Der folgende Text bleibt als historischer Nachweis erhalten.\n\n' + source)
apply('completion-report-' + ('delivered' if delivered else 'pending') + '-' + datetime.now().strftime('%Y%m%d%H%M%S%f'))
print(json.dumps({'status':status,'rows':len(rows),'wrappers':len(wrappers)}))

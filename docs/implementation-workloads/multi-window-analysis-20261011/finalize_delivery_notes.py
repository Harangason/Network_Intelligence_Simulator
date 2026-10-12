"""Record the actual completed delivery without changing application sources."""
import json
from pathlib import Path

here = Path(__file__).parent
def read(name):
    return json.loads((here / name).read_text(encoding='utf-8-sig'))
production = read('production-verification.json')
functional = read('production-functional.json')
workload = read('workload.json')
receipt = json.loads(Path(production['receipt']).read_text(encoding='utf-8-sig'))
assert production['status'] == functional['status'] == 'PASSED'
assert workload['completion_status'] == 'COMPLETED'
assert receipt['status'] == 'PASS' and all(check['exit_code'] == 0 for check in receipt['checks'])
assert production['running_image'] == production['expected_image'] == receipt['image_id']
state = read('delivery-state.json')
state.update(status='COMPLETED_VERIFIED_PRODUCTION_DELIVERY',
    production_has_multi_window_change=True, gate_pid=None,
    running_image=production['running_image'], image_tag=receipt['image_tag'],
    next_step='Completed: full PASS, exact tested production image, local and LAN/VPN readiness, actual browser functionality and completion guard verified.',
    verification_evidence=['production-verification.json', 'production-functional.json', 'completion-guard.json'])
state['next'] = state['next_step']
(here / 'delivery-state.json').write_text(json.dumps(state, indent=2)+'\n', encoding='utf-8')
(here / 'completion-guard.json').write_text(json.dumps({
    'status':'COMPLETED', 'issues':[], 'campaign_passed':False,
    'scope':'This implementation workload only; existing repair campaign remains separate'
}, indent=2)+'\n', encoding='utf-8')
notes = here / 'implementation-notes.md'
backup = here / 'implementation-notes-before-delivery.md'
if not backup.exists():
    backup.write_bytes(notes.read_bytes())
notes.write_text('''# NIS Mehrfenster-Analyse – produktiv übernommen

Die browserbasierten Phasen 0–6 der Anweisung sind umgesetzt. Simulation, Sequenz, Signale, Trace, Buslast, Ereignisse, Befunde, Ursachen, Diagramme und Analyse-Assistent lassen sich über die Fensterleiste öffnen. Gesperrte Popups erhalten Ersatzlinks. Fenster werden manuell auf die gewünschten Monitore verschoben. Ein nativer Desktop-Host für automatische Monitorpositionierung steht nicht zur Verfügung; diese Erweiterung wird nicht als geliefert ausgewiesen.

Ein projektgebundener Primärkontext ordnet Metadatenänderungen. Gekoppelte Fenster übernehmen Quelle, Originalreferenzen, Auswahl, Zeitbasis, Cursor und Filter; unabhängige Fenster behalten ihren Kontext. Vergleiche besitzen zwei ausdrücklich getrennte Quellen, Objektfilter und Zeitfenster. Kontextmeldungen übertragen keine Trace-Daten und berechnen keine technischen Ergebnisse. Projektwechsel und das Beenden der Analysesitzung invalidieren den gemeinsamen Darstellungskontext, ohne eine laufende Backend-Simulation zu beenden.

Originaldaten kommen aus vorhandenen projektgebundenen Serverendpunkten. Ein SharedWorker teilt kurzlebige, begrenzte Leseergebnisse; jeder Cachezugriff prüft weiterhin den Serverzugriff. Browser ohne SharedWorker verwenden denselben begrenzten Leseendpunkt. Modellkonfiguration und gespeicherte Buslastwerte werden selektiv aus dem eingefrorenen Snapshot gelesen. Es gibt kein neues technisches Schattenmodell und keine automatische Zeitbasisangleichung.

Fensterprofile liegen lokal und projektgebunden im Browser. Wiederherstellung öffnet Ansichten, Kopplungen und Fenstergrößen nach einer Benutzeraktion. Deep Links erhalten Projekt, Quelle, Originalauswahl, Zeitfenster und getrennte Vergleichsseiten. Der bestehende Engineering-Assistent erhält Originalreferenzen und Analysemetadaten über seinen bestehenden Kontextvertrag; vorhandene Projekt- und Sitzungsgrenzen gelten weiter.

Gezielte Prüfungen verwendeten temporäre Postgres-Datenbanken über scripts/run-isolated-tests.py, echte Trace-Imports, echte Golden-/Fault-Simulationen und echte Browserfenster. Nach der Zeitfenster-Reparatur bestanden 7 Unit-Prüfungen, Typprüfung, 2 isolierte Backend-Fälle und 9 echte Browserfälle. Diese gezielten Ergebnisse ersetzen keinen vollständigen Release-PASS.

Der vorherige vollständige Docker-Release b9804dd2b416 bestand 618 Frontend- und 21796 Backend-Prüfungen sowie 115 Browserfälle. Nur E2E-02 scheiterte an einer Zeitfenster-Eingabe während empfangener Kontextanzeige. Die Veröffentlichung wurde auf explizite Eingaben umgestellt; der gezielte Browser-PASS prüfte auch schnelle Eingaben in Gegenrichtung und den gemeinsamen Textfilter. Kleine/große HTTP-Prüfungen und Deployment erfolgten beim fehlgeschlagenen Lauf nicht.

Die Nutzerergänzung vom 12.10.2026 erklärt den Fehlereditor anhand der tatsächlichen, unveränderten Engine: absolute Beginn-/Endzeiten, typabhängiger Zusatzwert (bei STUCK ungenutzt), deutsche Auswahltexte und 29 technische Begriffe. Typprüfung bestanden; keine zusätzliche Design-Testreihe. Enger Diff und Quellenprüfung stehen in fault-explanations.diff und fault-explanations-source-review.md.

Der Nutzer hat am 12.10.2026 ausdrücklich genau das vollständig archivierte, ungenutzte Image networkis:candidate-b9804dd2b416 zur Löschung freigegeben. Nach frischen Archiv-, Image- und Containerprüfungen wurde nur dieses Image mit --no-prune entfernt. Archiv, FAIL-Beleg, Produktion und Rückfallimages blieben erhalten. Belege: retention-authorization-b9804dd2b416.json und failed-candidate-b9804dd2b416-storage-review.json.

Der neue vollständige Lauf ist PASS: Aufbewahrungsprüfung, Typprüfung, 618 Frontend-Tests, 21796 Backend-Tests (2 Skips, 1 Warnung, 56 bestandene Subtests), Produktionsbuild, alle 116 Browserfälle sowie kleine und große HTTP-Prüfung. Die Browserfälle enthalten alle sechs vorgeschriebenen Mehrfenster-E2Es einschließlich des reparierten Zeitfensters und die vollständigen großen Wizard- und Rücksprungabläufe. Beleg: backend/test-output/release-gates/delivery-b8b05bd2b669/4bfc55bac818/receipt.json.

scripts/release-and-deploy.py hat genau dieses geprüfte Image produktiv übernommen: networkis:candidate-4bfc55bac818, Image-ID sha256:3c3562900fc255344f65bdcf5c4cb2791685bd2532e220ff647c9ad48af48854, Quellhash a01c723d03fe364ac646c05f764be785e85cab76ab7a1ca6271a3e5220df8a64. production-verification.json bestätigt identische laufende Image-ID, Quellhash und Bereitschaft lokal sowie über LAN/VPN.

production-functional.json bestätigt am vorhandenen Projekt und Originaljob 33f124d0ad234c989dcbbd773e6393f9 echte getrennte Fenster: gekoppelter Cursor 0,02 s, unabhängiger Cursor unverändert 0,02 s, erneutes Ankoppeln auf 0,04 s, 96 gespeicherte Buslastnetze, unveränderte Jobliste sowie 29 Fehlerbegriffe und die erklärte Zusatzwertbehandlung. Es wurde keine neue Simulation gestartet oder das Engineering-Modell geändert. Die erste Zusatzkontrolle verglich irrtümlich die kompakte Projekt-ID mit der kanonischen Präfix-ID. production-verifier-correction.json dokumentiert die durch Workflow, Originaljob und bestehenden Normalisierungscode belegte Korrektur ausschließlich des Nachweishelfers; das geprüfte Anwendungsimage blieb unverändert.

finish_evidence.py hat unveränderte Quelldatei-Hashes, vollständigen PASS und Produktivbelege geprüft und den Workload abgeschlossen. Der Implementation Guard meldet COMPLETED ohne offene Punkte. Die übergeordnete Reparaturkampagne wird dadurch nicht für bestanden erklärt. Die native Desktop-Erweiterung zur automatischen Monitorpositionierung bleibt außerhalb der gelieferten browserbasierten Phasen 0–6.
''', encoding='utf-8')
print(json.dumps({'status':'COMPLETED', 'image':production['running_image']}))

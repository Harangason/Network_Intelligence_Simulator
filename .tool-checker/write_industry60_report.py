import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'.tool-checker/evidence/industry60'
R=ROOT/'.tool-checker/reports'
report=json.loads((R/'industry60-report-20260916.json').read_text(encoding='utf8'))
intake=json.loads((E/'intake-summary.json').read_text())
def link(path,label=None):
 p=Path(path);return f'[{label or p.name}](<{p.as_posix()}>)'
text=[f'''# Prüfbericht: 60 industrieneutrale Agenten-, MCP- und Trace-Szenarien

Stand: {datetime.now(timezone.utc).isoformat()}

## Ergebnis und Reichweite

**Keine Freigabe des vollständigen 60-Fälle-Vertrags.** {report['counts'].get('FAILED',0)} Fälle enthalten nachgewiesene Abweichungen; {report['counts'].get('PARTIAL',0)} bleiben teilweise geprüft. Kein Fall wird hier allein aufgrund eines HTTP-200, eines grünen Status oder eines erfolgreichen Komponenten-Tests als vollständiger E2E-PASS gewertet. Mehrere Fälle teilen dieselbe Fehlerursache.

Die 40 A/B-Originaleingaben wurden frisch an den echten Agenten des veröffentlichten Images gesendet. Alle 40 lieferten HTTP 200 und persistierte Entwürfe; Originalanforderungen blieben unverändert erhalten. Das beweist Intake und Persistenz, nicht erzeugte Ports, Routing, Simulation oder eine neunstufige Freigabe. Weitere Architekturentscheidungen wurden entsprechend der Nutzeranweisung offengelassen. Die im S24-Quelltest ausdrücklich vorgegebene direkte CAN-FD-Auswahl wurde als SCRIPTED_TEST ausgeführt.

Die zusätzlichen Agenten-/MCP-Fälle wurden mit realen HTTP-, Browser- und isolierten SQL/MCP-Proben untersucht. Für S31–S40 kamen echte Golden-/Fehlersimulationen, Browseransichten, HTTP-Reasoning, Decoder-/Fensterregressionen und eine Datei mit 100.501 Ereignissen hinzu. Die gesamte CameraBurst-Kausalkette von S38 und die vollständige kanonische Snapshot-Kette von S40 wurden nicht erfolgreich aufgebaut. Diese fehlenden Nachweise sind ausdrücklich offen.

**Keine Produktkorrekturen und kein Deployment in dieser Prüfung. Produktdatenbank und Nutzerprojekte wurden nicht als Testdaten verwendet.**

## Quelle und Prüfumgebung

- Quelldokument: {link('H:/OneDrive/Download/NETWORK_SIMULATOR_60_INDUSTRY_NEUTRAL_AGENT_MCP_TRACE_TEST_SCENARIOS.md')}
- SHA-256 unverändert am Ende: `{report['source_hash']}`.
- Erste 50 Fallblöcke gegenüber der vorherigen Quelle unverändert; S31–S40 neu. Alte Überschriften nennen noch 50, die finale Liste umfasst 60; geprüft wurde diese 60er-Liste.
- Veröffentlichtes Image: `{report['image']}`; Frontend-/Backend-Build `{report['build']}`.
- Isolierte App auf Port 51576, separate Postgres-Instanz und Runtime-Volume, Kennzeichnung `networkis.test=disposable`.
- Vorbereitungsbeleg: {link(ROOT/'backend/test-output/industry60-stack/f4a32bef96e8/receipt.json')}. Status PREPARED ist **kein** Release-PASS.
- Lokale Modelle qwen3.8:27b / llama3.1:8b; Cloud-Fallback deaktiviert. Browser: Codex-In-App-Browser über cua_repl. Benutzer-Tab unverändert.
- 3 isolierte MCP-/SQL-Prüfungen und 66 Trace-/Reasoning-Regressionsprüfungen bestanden. Darunter sind Beobachtungsproben und Komponenten mit gestubbten Modell-/Transportzugriffen; **keine 69 vollständigen E2E-Fälle**. SQL-Ausführung ausschließlich über `scripts/run-isolated-tests.py`.
- {link(ROOT/'.tool-checker/industry60-trace-tests.log','Testprotokoll')} · {link(E/'trace-regressions.xml','JUnit')} · {link(E/'mcp/protocol.json','MCP-Protokoll')}.

## Priorisierte Befunde
''']
for f in sorted(report['findings'],key=lambda x:x['id']):
 text.append(f"### {f['id']} · {f['priority']} · {f['title']}\n\nBetroffen: {', '.join(f['cases'])}.\n\n{f['detail']}\n\nNachweise: "+' · '.join(link(E/p) for p in f['evidence'])+'\n')
text.append('''## Positive Gegenproben

- S23: ParkAssist und DriverAssistance werden aus dem bestehenden Modell korrekt mit ihren Controllern, CAN-/Ethernet-Ports und Netzen beantwortet. Modellrevision bleibt unverändert.
- S27: MotorRPM mit 0–5000 rpm und Auflösung 50 benötigt mindestens 7 Bit. Die vorhandene 4-Bit-Bindung wird als ERROR erkannt, ohne einen neuen Generator zu starten.
- MCP-Registry: 181 registrierte Tools; Input-/Outputschemas, Version und Permission-Metadaten vorhanden. Unbekannte Tools, nicht unterstützte Technologie und Timeout werden als unterschiedliche Statuswerte behandelt.
- S24: Nach der vorgegebenen Auswahl wurden Port/Anbindung und Route tatsächlich persistiert; Capacity, Timing und Preflight wurden erneuert. Der Fehler liegt hier zusätzlich in der Ergebnisdarstellung, nicht in einer nur vorgetäuschten Mutation.
- S07-A erkennt beide Controller/Compute-Knoten, S11-A drei und S20-A alle 56. S01-A bewahrt SPI, I2C, GPIO, PWM und CAN-FD statt pauschal Automotive-Ethernet zuzuordnen.
- Trace-Fenster: Auswahl bleibt beim Wechsel zwischen Botschaften, Sequenz, Signalen, Trace und Findings erhalten. Werte, Einheiten und kanonische Objektlinks sind vorhanden.
- Golden-/Fehlervergleich findet eine 100-ms-Abweichung beim Gateway-Delay. Ohne unveränderlichen Snapshot wird die Ursache korrekt nicht endgültig freigegeben.
- Dateibasiertes Core-Paging liefert aus 100.501 Datensätzen begrenzte 500er-Fenster einschließlich des späten Fensters ab Sekunde 99. Das ist eine andere Strecke als der begrenzte Import-Endpunkt.

## Abdeckung je Fall

PARTIAL bedeutet fehlende Teile des vollständigen Quellvertrags, nicht automatisch einen Produktfehler. FAILED bedeutet mindestens eine konkret belegte Abweichung. Die Hintergrundjob-Anzeige bezeichnet PARTIAL intern als BLOCKED; die folgende Tabelle verwendet die eigentlichen, fachlich nachbewerteten Laufresultate.

| Fall | Ergebnis | Geprüfter Bereich / Grenze |
|---|---|---|
''')
for r in report['cases']:
 text.append(f"| {r['id']} | {r['status']} | {r['detail']} {link(Path(r['evidence'])/'review/finish.json','Laufbeleg')} |\n")
text.append('''
## A/B-Intake im Detail

Zahlenfolge: Controller / Gateway / Sensor / Aktor. „Offen“ zählt gespeicherte Issues, keine einmaligen Rückfragen. Ein unbekannter Typ oder eine offene Technik wird bei unvollständiger Eingabe nicht pauschal als Fehler bewertet. Die technische Architekturqualität nach den unbeantworteten Entscheidungen ist damit nicht bewiesen.

| Fall | C/G/S/A | Typisiert | Technik konkret | Offene Issues | Originaltext erhalten |
|---|---|---|---|---|---|
''')
for r in intake:
 cnt=r['counts'];text.append(f"| {r['id']} | {' / '.join(str(cnt[k]) for k in ['CONTROLLER','GATEWAY','SENSOR','ACTUATOR'])} | {r['known']} | {r['explicit_technology']} | {r['open']} | {'Ja' if r['source_retained'] else 'Nein'} |\n")
text.append(f'''
## Testaufbaufehler und verbleibende Grenzen

1. Ein erster Fehlersimulationsversuch nutzte eine nichtkanonische Gateway-ID und konnte nicht starten. Das wurde als **TEST_DATA_ERROR** behandelt. Nach Erzeugung echter kanonischer IDs liefen Golden und Fault durch. Der anfängliche Fehler ist kein Produktbefund. Die Logs enthalten außerdem den ursprünglichen ungültigen Routing-Verweis `canonical-route`; korrigierte Jobs verwenden die gespeicherte UUID.
2. Golden und Fault wurden über die reale Simulations-HTTP-Strecke aus überprüfter expliziter Konfiguration gestartet. Die kanonischen Hardware-/Signal-/Route-IDs existieren, aber Routingfreigabe, Topologie und unveränderlicher Workflow-Snapshot wurden für diese Fixture nicht vollständig hergestellt. Daraus darf weder S40-PASS noch ein Fehler allein wegen MISSING_SIMULATION_SNAPSHOT abgeleitet werden.
3. Der Fault erzeugt Verzögerung/Deadline-Verletzung; einen anwachsenden Queue-Rückstau belegt die Fixture nicht. Die in S28/S36/S38 verlangte gesamte Kausalkette ist deshalb offen. Insbesondere wurde CameraBurst nicht durch eine andere Ursache ersetzt und als bestanden ausgegeben.
4. Browser-Dateiauswahl wurde zweimal versucht. Der Provider lieferte jeweils keinen Filechooser. Der große Import wurde deshalb zusätzlich direkt über den echten HTTP-Endpunkt geprüft. Browsergeschwindigkeit, Scroll-/Speicherverhalten dieser großen Importdatei sind **nicht gemessen**.
5. S29: Der echte isolierte SQL/MCP-Test belegt gespeichertes Finding, Risikobewertung und erneute Prüfung nach Modelländerung. Die zusätzliche HTTP-Probe hatte keinen gespeicherten Articulation-Point-Befund und antwortete korrekt INCOMPLETE. Sie ersetzt keinen positiven Browser-E2E-Test dieses Falls.
6. A/B-Fälle enthalten viele offene Entscheidungen. Es wurden keine Defaults, Zuordnungen oder Genehmigungen erfunden, um durch die Gates zu gelangen. Nicht jede A/B-Variante wurde zusätzlich einzeln im Browser geöffnet.
7. Die Tool-Checker-Nachbewertung registriert die vorhandenen Originalbelege und einen frischen Modellstand. Sie ist ausdrücklich **kein erneuter Agentenlauf**. Nicht nachgewiesene Vertragschecks bleiben offen; ursprüngliche Resultate werden nicht rückwirkend zu PASS geändert.

## Empfohlene Korrekturreihenfolge

1. **Antwort- und Laufvertrag stabilisieren:** Schemaerhalt bei Cache-Begrenzung, persistierter terminaler Status auch bei SSE-Abbruch, begrenzte Fortsetzung ohne Cursor, Wiederaufnahme desselben Laufs statt wiederholter Fehler.
2. **Intent vor Wizard-Modus:** Ein konkreter Verbindungs-/Analyseauftrag für bestehende Funktionen muss den passenden Ausführungspfad wählen. CREATE_ARCHITECTURE darf diesen Auftrag nicht in einen leeren Neuentwurf umleiten.
3. **Trace-Identität korrigieren:** Routenwechsel pro End-to-End-Transport und Segment vergleichen; normales Gateway-Forwarding darf kein ROUTE_CHANGE sein. Gegenprobe mit tatsächlichem Pfadwechsel beibehalten.
4. **Persistente Importsessions und Zeitvertrag:** Große Imports vollständig serverseitig speichern, fensterweise lesen; fehlende Zeit als Datenlücke erhalten; Auswahl/Event-ID/Filter im Deeplink und beim Reload wiederherstellen.
5. **MCP-Fehlerstruktur ergänzen:** Feld, Grund und erwartete Form separat liefern. Anschließend dieselben Negativtests über MCP und Browser ausführen.
6. **Fehlende Abnahme gezielt schließen:** Vollständige kanonische Snapshot-Fixture, echte Queue-/CameraBurst-Kette, fünf Signalarten/fehlerhafte Encodings und die weiteren Technologieansichten ergänzen. Offene Engineering-Entscheidungen bleiben offen, bis sie ausdrücklich getroffen sind.

Eine spätere Wizard-Korrektur muss gemäß Projektvertrag das Release-Gate bestehen und exakt das getestete Image per PASS-Receipt ausrollen. Dieser Bericht erteilt keine solche Freigabe.

## Artefakte

- {link(R/'industry60-report-20260916.json','Maschinenlesbarer Bericht mit allen 60 Fällen')}
- {link(ROOT/'.tool-checker/industry60.normalized.json','Normalisierter vollständiger Testvertrag')}
- {link(E/'intake-summary.json','40 Intake-Ergebnisse')}
- {link(E/'trace/canonical-jobs.json','Frische Simulationsjobs')}
- {link(E/'backend-final.log','Isoliertes Backend-Log')}
- {link(E/'integrity.json','SHA-256-Verzeichnis der Prüfnachweise')}
''')
(R/'industry60-report-20260916.md').write_text('\n'.join(text),encoding='utf8')
manifest=[]
for p in sorted(E.rglob('*')):
 if p.is_file() and p.name!='integrity.json':manifest.append({'path':str(p.relative_to(E)),'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(E/'integrity.json').write_text(json.dumps({'created_at':datetime.now(timezone.utc).isoformat(),'files':manifest},indent=2),encoding='utf8')
print(report['counts'],len(manifest))

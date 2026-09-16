import json,hashlib,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1];E=R/'.tool-checker/evidence/industry50';O=R/'.tool-checker/reports';O.mkdir(exist_ok=True)
m=json.loads((R/'.tool-checker/industry50.normalized.json').read_text(encoding='utf8'));intake=json.loads((E/'intake-analysis.json').read_text(encoding='utf8'));by={x['id']:x for x in intake};rows=[]
for c in m['test_cases']:
 p=E/c['test_id'];f=p/'review/finish.json' if (p/'review/finish.json').exists() else p/'finish.json'
 status=json.loads(f.read_text(encoding='utf8'))['status'] if f.exists() else 'PENDING'
 if c['test_id'] in by:
  x=by[c['test_id']];detail=f"{x['devices']} Geräte im Entwurf; {x['unknown_kind']} ohne erkannten Gerätetyp, {x['without_technology']} ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf."
 else:
  obs=p/'observations.json';d=json.loads(obs.read_text(encoding='utf8')) if obs.exists() else {};detail=next((v.get('detail','') for v in d.get('outputs',[]) if v.get('detail')),'Noch in Prüfung.')
 rows.append({'id':c['test_id'],'title':c['title'],'status':status,'scope':detail,'evidence':str(p),'full_e2e_pass':False})
counts=dict(collections.Counter(x['status'] for x in rows));source=Path('H:/OneDrive/Download/NETWORK_SIMULATOR_50_INDUSTRY_NEUTRAL_AGENT_MCP_TEST_SCENARIOS.md');source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
result={'source':str(source),'source_sha256':source_hash,'tested_image':'sha256:8c249e600edeca8dc3f924afbb2d6c10eb4f6776f3d54f85ff7aa2ec7394f3cf','build':'b1297e9bad56','counts':counts,'full_50_e2e_pass':False,'cases':rows,'decisions':'S24 source-scripted direct CAN-FD only. Other open architecture decisions not auto-answered. S07-B prior CAN-FD+Ethernet authorization remains valid but not applied through all missing detailed inventory decisions in this intake rerun.'}
(O/'industry50-report-20260916.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
def link(label,path):return f'[{label}]({str(path).replace(chr(92),"/")})'
s=f'''# Erneute Agentenprüfung: 50 industrieneutrale Szenarien

Stand: 16.09.2026. **Keine Freigabe für den vollständigen 50-Fälle-Agentenworkflow.**

## Ergebnis und tatsächlicher Umfang

{counts}. **0 vollständig bestandene Szenarien nach dem gesamten Quellvertrag.** Das bedeutet nicht, dass jede Teilfunktion defekt ist: PARTIAL bezeichnet ausdrücklich fehlende Folgeprüfungen bzw. offene Entscheidungen, nicht automatisch einen Produktfehler.

- Alle 40 ursprünglichen A/B-Aufträge erneut unverändert über den echten HTTP-Agenten ausgeführt, mit lokaler Inferenz, gespeicherten Entwürfen, Antwortverlauf, Modellzustand und Browserbelegen.
- Die zehn neuen Fälle mit realen Browseraktionen, MCP-Aufrufen, kanonischen Testmodellen und ergänzenden isolierten SQL-/Core-Proben geprüft. Grenzen je Fall stehen unten. Kein Mock-Erfolg wird als E2E-Nachweis gewertet.
- Getestet wurde das veröffentlichte Image `{result['tested_image']}`, Build `b1297e9bad56`, in einem separaten Stack auf Port 60023. Die PREPARED-Receipt dieses Stacks ist **keine neue Release-PASS-Receipt**.
- Es wurden keine Produktkorrekturen implementiert und keine Produktprojekte verändert. Die bereits vorhandene Release-Gate-Freigabe deckt diesen erweiterten Szenariensatz nicht vollständig ab.
- Vier ergänzende pytest-Beobachtungsproben liefen erfolgreich. Das bestätigt ihre Ausführung, **nicht** vier bestandene Szenarien. Die Proben verwenden denselben Quellstand, aber den lokalen Python-Prozess; Browser/HTTP verwenden das veröffentlichte Image.
- Keine weiteren Architekturentscheidungen automatisch beantwortet. Nur S24 enthält eine ausdrücklich im Testskript vorgegebene Wahl. Fehlende Messgrößen, Bindungen und Kodierungen wurden nicht erfunden.

Quelle: `{source}`  
SHA-256: `{source_hash}`

## Wesentliche Fehler

| Priorität | Befund | Reproduzierbarer Nachweis |
|---|---|---|
| P1 | Konkrete Anforderungen werden nicht ausreichend in den Entwurf übernommen. | S03-A nennt Positionssensoren, Servoantriebe und CANopen; gespeichert werden generische Geräte, `known_kind=false` und `technology=null`. Das Original bleibt erhalten, aber die strukturierte Ausarbeitung fehlt. |
| P1 | Zusätzliche Compute-Knoten verschwinden. | S07-A/B: nur ein Controller statt Controller plus zusätzlichem Rechner. S11-B: zwei statt drei einschließlich Auswerte-PC. S20-A: sechs zusätzlich genannte Edge/HPC-Knoten fehlen neben den 50 Controllern. |
| P1 | Die bisherige Test-Erwartung war zu schwach. | `tests/fixtures/industry40.json` zählt diese zusätzlichen Knoten teilweise ebenfalls nicht. Die bisherigen Anzahlentests konnten deshalb grün bleiben. Das ist eine Testlücke, keine neu nachgewiesene Regression des aktuellen Images. |
| P1 | Zusammengesetzter Gesamtauftrag wird falsch zerlegt. | S30 verwendet den Originalprompt. Der Parser sucht das Objekt „DriverAssistance, prüfe die Kommunikation in einer kurzen Simulation“ und meldet 0 Treffer. Die komplette Folgeausführung wird nicht erreicht. |
| P1 | Signalprüfung wird in den falschen Ablauf geleitet. | S27: vorhandenes MotorRPM, 0–5000 rpm, 50 rpm Auflösung, 10 ms, CAN-FD. Der Browser meldet „Eine positive Gesamtzielmenge konnte nicht ermittelt werden.“ Der MCP-Bitbreitenkern berechnet separat korrekt 7 Bit. |
| P1 | Reiner Leseauftrag läuft in den Antwort-Timeout und liefert auch später nicht die gewünschte Anbindungsbeschreibung. | S23: nach rund 290 Sekunden Verbindungsabbruch. Später wird ein INCOMPLETE-Ergebnis zu nicht belegten Rechenwerten gespeichert, obwohl nach vorhandenen Anbindungen gefragt wurde. Modellrevision blieb unverändert. |
| P2 | Architektur-Einstieg transportiert keinen klaren CREATE_ARCHITECTURE-Modus. | S21: Knopf füllt Text vor, Envelope bleibt ENGINEERING_REQUEST; gespeicherter Entwurf vorhanden. Ein durchgängiger Goal-/Execution-Plan ist nicht belegt. Generische Aktoren erhalten außerdem eine unpassende „Ventilbefehl“-Auswahl. |
| P2 | Fehlerhafte Antwortkarte trotz technisch erfolgreicher Verbindung. | S24 legt nach einer Wahl Port und Route an, der kanonische Goal ist COMPLETE; davor zeigt die Oberfläche „Die Antwort konnte nicht als Engineering-Karte dargestellt werden“. |
| P2 | MCP-Fehlervertrag nicht vollständig eingehalten. | Nicht existentes Tool → INVALID_INPUT; unbekannte Technologie → SUCCESS mit gekennzeichnetem GENERIC_ESTIMATE statt NOT_SUPPORTED; injizierter Transporttimeout → ungefangener TimeoutError statt TOOL_TIMEOUT. |
| P2 | Tool-Metadaten erreichen den Agenten nur teilweise. | 178 reale Tools, Wire-Input-/Output-Schemas vorhanden. Die Agenten-Registry reduziert das Output-Schema; eine explizite Tool-Version fehlt auf Wire-Ebene. Permission-Verträge existieren im Core. |

## Nachgewiesene funktionierende Teile

- Originaltexte der 40 Branchenfälle bleiben im Entwurf erhalten. Kein erneuter automatischer Sprung nach Automotive wurde beobachtet: 36 Entwürfe ohne festgelegte Industrie, vier `embedded_systems`. Eine offene Industrie ist noch keine fachlich vollständige Ausarbeitung.
- S24: kanonischer Port, Netzmitgliedschaft und eine Route entstehen nach der vorgegebenen einzelnen Entscheidung im selben Workload. Kapazität, funktionales Timing und Preflight sind im gespeicherten COMPLETE-Goal belegt; 50 Journal-Einträge. Das ist ein echter technischer Erfolg, aber wegen der fehlerhaften UI-Karte kein fehlerfreier Gesamttest.
- S26: persistierte MULTI-Frage mit zwei Datenoptionen; Bestätigung ohne Auswahl deaktiviert. Kein unautorisiertes Weiterlaufen.
- S25: negative Payloadgröße wird abgewiesen; volle Controllerkanäle werden mit NO_FREE_CHANNEL/HARDWARE_INTERFACE_CAPACITY_EXCEEDED erkannt.
- S27: Bitbreitenberechnung 7 Bit und Ablehnung einer bewusst zu kleinen 4-Bit-Kodierung funktionieren im MCP-Kern.
- S28: echter 15-s-Job mit Gateway-Verzögerung ab 12 s, 150 Latenzverletzungen, ein Timeout. Der Agent behauptet keinen unbewiesenen Root Cause.
- S29-Core: leere Risikobegründung abgewiesen; begründete Risikoakzeptanz gespeichert; spätere Modelländerung setzt die Entscheidung auf NEEDS_REVIEW. Der technische Finding-Datensatz bleibt erhalten.

## Grenzen der Integrationstests

S22/S25 enthalten direkte MCP-/Core-Proben; nicht jeder geforderte Agenten- oder Retry-Pfad ist damit geprüft. Die vier pytest-Proben sind keine Browser-E2E-Suite.

S28: Der erste Job scheiterte wegen eines fehlenden kanonischen Gateway-Ziels im Testfixture. Das war ein Aufbaufehler des Tests und wird nicht als Produktbug gezählt. Nach Anlage echter Hardware entstand ein vollständiger Simulationsjob. Eine dauerhaft wachsende Queue wurde dabei nicht nachgewiesen (Queue-Tiefe im betrachteten Fenster 0); eine vollständige kanonische Route und ein Workflow-Snapshot fehlen in diesem Fixture. Deshalb ist ROOT_CAUSE_UNCONFIRMED fachlich angemessen und der Gesamtfall PARTIAL. Die ursprüngliche geforderte Queue-Growth-Kausalkette gilt nicht als bestanden.

S29: Der exakte Ausgangsbefund wurde im isolierten Core als explizites Testfixture eingespielt. Das beweist den Lifecycle, nicht die vorgelagerte automatische Erkennung des Artikulationspunkts. Der Browser-Zusatztest erhält den vorgegebenen Befund als Kontext; er ersetzt keinen vollständig verknüpften Finding-UI-E2E-Lauf.

S07-B: Die frühere CAN-FD/Ethernet-Freigabe bleibt gültig; im erneuten Intake wurden fehlende Geräteaufgaben/Kodierungen nicht durch weitere Annahmen ergänzt. Für die übrigen offenen Architekturentscheidungen gilt weiterhin die ausdrückliche Vorgabe, sie offen zu lassen.

## Fallmatrix

| Fall | Status | Tatsächlich geprüfter Stand |
|---|---|---|
'''
for x in rows:s+=f"| {x['id']} | **{x['status']}** | {x['scope'].replace('|','/')} |\n"
s+='''
## Empfohlene nächste Korrekturschritte

1. Anforderungen und Gerätelisten verlustfrei in ein gemeinsames typisiertes Modell überführen. Zusätzliche Rechner, Gruppen und eindeutige Technologien müssen erhalten bleiben. Fehlende Daten gezielt abfragen.
2. Wizard-Auswahl als expliziten Intent mit ausgewählten kanonischen Objekten übertragen. Signalprüfung, Modelllesen und Erstellung dürfen nicht über dieselbe unscharfe Schlüsselwortlogik laufen.
3. Mehrteilige Aufträge in getrennte Ziele zerlegen; Funktionsnamen vor den Folgeaufträgen begrenzen. S30 als verbindlichen Regressionstest übernehmen.
4. Reine Modellabfragen deterministisch über den Modellgraphen beantworten; Inferenz-/Antwortbudgets und dauerhafte Wiederaufnahme abstimmen. Timeout darf keinen inhaltsfremden Ersatztext erzeugen.
5. Antwortkarten vor dem Senden schema-validieren. Ein erfolgreicher Core-Lauf darf keine zusätzliche defekte Karte erzeugen.
6. MCP-Fehler normalisieren, Toolversion und Output-Schema erhalten, unbekannte Technologien nur nach expliziter Wahl als generische Schätzung behandeln.
7. Testorakel unabhängig aus der Spezifikation ableiten. Vollständige Hardwareinventare, Fachtypen und Bindungen prüfen; nicht nur Gesamtzahlen oder grüne Fortschrittskarten.
8. S28/S29 mit vollständig kanonischen Fixtures bis Trace, Finding, Entscheidung, Reload und Revisionswechsel absichern. Danach dieselbe 50er-Suite erneut ausführen; erst dann die Release-Freigabe erweitern.

Dies sind Vorschläge aus der Prüfung; sie wurden in diesem Auftrag nicht implementiert.

## Nachweise

'''
s+=link('Maschinenlesbare Fallmatrix',O/'industry50-report-20260916.json')+'\n\n'
s+=link('Originalnachweise und Screenshots',E)+'\n\n'
s+=link('Normalisierter vollständiger Prüfvertrag',R/'.tool-checker/industry50.normalized.json')+'\n\n'
s+=link('Isolierter Teststack / PREPARED-Receipt',R/'backend/test-output/industry50-stack/96f25e6a865f/receipt.json')+'\n'
(O/'industry50-report-20260916.md').write_text(s,encoding='utf8')
print(json.dumps(counts))

import json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'.tool-checker/evidence/industry60-recheck'
R=ROOT/'.tool-checker/reports/industry60-recheck-20260916.json'
report=json.loads(R.read_text(encoding='utf8'))
details={
 'S21':'CREATE_ARCHITECTURE mit Originaltext: persistierter Entwurf; offene Anschlüsse und Geräteaufgaben. Kein vollständiger Wizard-Abschluss.',
 'S22':'Kommunikationsprüfung beendet sich mit ANSWERED und konkreter Wegentscheidung; kein beobachteter Langlauf. Auswahl bleibt offen.',
 'S23':'Bestehende CAN-FD-/Ethernet-Anbindung richtig gelesen. Vollständiger geforderter Visualisierungs-/Toolpfad nicht abgenommen.',
 'S24':'Konkrete Anschlussentscheidung wird gestellt. Keine neue Architekturentscheidung beantwortet; Mutation und große Antwortdarstellung daher nicht vollständig erneut geprüft.',
 'S25':'INVALID_INPUT enthält field/reason/expected_schema; NOT_SUPPORTED und injizierter TOOL_TIMEOUT korrekt. Kanalgrenze ergänzend auf Core-Planung geprüft, kein vollständiger MCP-create_port-Negativpfad.',
 'S26':'Abstrakter Originaltext benennt Quelle/Ziel nicht. Agent meldet 0 Treffer für „eine bestehende Funktion“. Testdaten müssen die vorgesehenen Kontextreferenzen explizit binden; kein Mehrfachentscheidungs-/Resume-PASS.',
 'S27':'MotorRPM wird aus persistiertem Signal geprüft: 4 Bit reichen nicht, 7 erforderlich. Kein automatisches Umkodieren; komplette Binding-Reparatur nicht durchgeführt.',
 'S28':'ANALYZE_TRACE mit echtem SimulationRun endet INCOMPLETE mit Datenlücken, ohne leere Fortsetzungsschleife. Snapshot und vollständige Ursachenkette fehlen im Testaufbau.',
 'S29':'Kein gespeicherter Finding-Datensatz im Fixture: Agent verlangt korrekt Finding-ID/Modellanalyse. Bewertung/Persistenz mangels vollständiger Fixture nicht abgenommen.',
 'S30':'CREATE_ARCHITECTURE überschreibt den Anschlussauftrag nicht mehr. Wegentscheidung für bestehende Funktionen, Simulation und Trace-Folgeauftrag bleiben erhalten; Entscheidung bleibt offen.',
 'S31':'Echte Simulations- und Importsession geladen; Importsession bleibt erhalten und ist projektisoliert. MCP lehnt fehlende Zeit ab. Vollständige Source-/Timebase-/Sync-Metadatenmatrix nicht belegt.',
 'S32':'CAN-FD/Ethernet im echten Browser, Rohdaten, Source/Destination und IDs geprüft. DDS/Modbus/PROFINET/ARINC429-Labels nicht vollständig abgenommen.',
 'S33':'Reale Zwei-Segment-Simulation: Source→Gateway→Destination und Adressen sichtbar; 0 falsche ROUTE_CHANGE im neuen Fault-Fenster. Negativer Route-Mismatch nicht vollständig abgenommen.',
 'S34':'Temperature mit 34,2 degC/VALID sichtbar; MotorRPM-Bitbreite separat geprüft. Fünfkanal- und sämtliche negativen Decode-Fälle nicht vollständig abgenommen.',
 'S35':'Event route-RT-1-target:625:segment:0 bei 12.5001575 s bleibt über Botschaften, Sequenz, Signale, Trace und Reload ausgewählt; Zeitfenster 12,4–12,6 s bleibt. Vollständige Playhead-Abnahme fehlt.',
 'S36':'Neue Golden-/Fault-HTTP-Jobs, Gateway-Delay 12–15 s, 100 ms zusätzliche Latenz, Deadline-Miss und Marker belegt. Queue-Ursachenkette/Snapshot fehlen; keine kausale Freigabe.',
 'S37':'Neuer Golden-Vergleich zeigt erste Abweichung bei 12.00217094 s und 100 ms Zeitdifferenz. Nicht alle zusätzlichen/fehlenden Ereignis-, Zustands- und Routenvarianten getestet.',
 'S38':'Hypothesen/Evidence und explizit unbelegte Ursache geprüft. Die geforderte CameraBurst→Queue→CAN-FD→MotorStatus-Fixture wurde nicht vollständig aufgebaut; keine Ursachenfreigabe.',
 'S39':'100501 Ereignisse vollständig über HTTP importiert; Browser hält 2000 und lädt Seite 2 ab 2 s. Reload/Projektisolation über API geprüft. Nicht alle Filter und Downsampling vollständig abgenommen.',
 'S40':'Frischer integrierter Teilpfad aus Modell-IDs, Simulation, Views, Golden-Vergleich, Reasoning und Reload. Kein freigegebener vollständiger Snapshot-/Finding-/Completion-Pfad.',
}
for row in report['cases']:
 row['scope']=details.get(row['id'],row['scope'])
report['confirmed_failed_case_percent']=100*report['counts'].get('FAILED',0)/60
report['interpretation']='Untergrenze bestätigter fehlerhafter Fälle; PARTIAL ist kein PASS. Keine Schätzung einer produktiven Ausfallwahrscheinlichkeit.'
R.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
lines=['# Industry60 – erneute Prüfung vom 16.09.2026','',
'**Ziel unter 1 % nicht erreicht und nicht freigegeben.**', '',
f"60 Fälle bewertet: {report['counts']}. Bestätigte fehlerhafte Fälle: mindestens {report['confirmed_failed_case_percent']:.2f} %. Teilprüfungen zählen nicht als bestanden.", '',
'Dies ist keine vollständig abgeschlossene Wiederholung aller Pflichtpfade: 40 Original-Architekturaufträge wurden frisch über den Agenten angesprochen und im Browser nachgeladen; offene Entscheidungen wurden nicht erfunden. Integrations- und Trace-Fälle wurden mit den unten genannten Grenzen erneut untersucht. Insbesondere S26/S29 benötigen bessere Ausgangsfixtures, S38 die vollständige Camera-Burst-Kette. Eine Fehlerquote unter 1 % lässt sich daraus nicht behaupten.', '',
'## Build und Isolation','',
'Kandidat `f32703613317`, Image `'+report['image']+'`. Frische SQL-Datenbank und Runtime im Stack `919f1a3730d4`; keine Produktprojekte verändert. Lokale Modelle qwen3.8:27b und llama3.1:8b erreichbar. Ollama war ausgeschaltet und wurde für den Test gestartet. Source-SHA256: `'+report['source_hash']+'`.', '',
'Der Release-Lauf `65739aa984db` enthält 1796 bestandene Backendtests (2 übersprungen), 390 Frontendtests, Typprüfung, Produktionsbuild, 68 Browser-E2E und den kleinen HTTP-Test. Sein großer HTTP-Test hat keinen Abschlussnachweis; der Prozess war beendet. **Kein PASS-Receipt, keine Auslieferung.** Diese Zahlen sind keine 60 bestandenen Szenarien.', '',
'Vier frische isolierte MCP-/Trace-Probes wurden erfolgreich ausgeführt; ihre Assertions sind begrenzte Teilnachweise. HTTP 200 oder Tool SUCCESS allein wurde nicht als fachlicher Szenario-PASS gezählt.', '',
'## Bestätigte Befunde','']
for f in report['findings']:lines += [f"### {f['id']} · {f['priority']} · {f['title']}",'',f['detail'],'','Nachweise: '+', '.join('../evidence/industry60-recheck/'+p for p in f['evidence']), '']
lines += ['## Nachgewiesene Verbesserungen','',
'- Fehlende Inline-Zeitstempel werden als INVALID_INPUT abgewiesen.',
'- MCP-Schemafehler enthalten Feld, Grund und erwartetes Schema.',
'- Normale Gateway-Segmente erzeugen im neuen Lauf keine falschen Routenwechsel.',
'- Bestehender Anschlussauftrag bleibt auch im CREATE_ARCHITECTURE-Modus erhalten.',
'- Trace-Auswahl und Zeitfenster bleiben nach Reload erhalten.',
'- Import: 100501 Ereignisse gespeichert, weitere Seiten abrufbar, anderer Projektkontext erhält 404.',
'- Kommunikationsprüfung und Trace-Agent liefern einen Abschluss beziehungsweise ausdrücklich INCOMPLETE statt der zuvor beobachteten Schleifen.', '',
'## Fallmatrix','', '| Fall | Ergebnis | Tatsächlicher Umfang / Grenze |','|---|---|---|']
for r in report['cases']:lines.append(f"| {r['id']} | {r['status']} | {r['scope'].replace('|','/')} |")
lines += ['','## Nächste Schritte','',
'1. Explizite Technologiebindungen wie „EtherCAT für Drives“ in den Entwurf übernehmen; Regression für S12-A und weitere rollenbezogene Netzangaben.',
'2. Antwortzusammenfassung ausschließlich aus der tatsächlichen Geräte-/Funktionsliste erzeugen; keine feste Temperatur-/Ventil-Schablone.',
'3. S26/S29/S38 mit vollständigen, dokumentierten Fixtures versehen und fehlende Trace-Varianten testen. Fehlende Testdaten sind von Produktfehlern zu trennen.',
'4. Offene Architekturentscheidungen weiterhin offen lassen, bis ausdrücklich beantwortet. Danach vollständige neun Stufen und Trace-Kette wiederholen.',
'5. Unter 1 % bei 60 Fällen bedeutet 0 fehlgeschlagene Fälle; für eine Vollabnahme dürfen zusätzlich keine Pflichtprüfungen offen bleiben. Danach kompletter Release-Gate-Lauf und ausschließlich dessen PASS-Image ausliefern.','']
(R.with_suffix('.md')).write_text('\n'.join(lines),encoding='utf8')
files={str(p.relative_to(E)):hashlib.sha256(p.read_bytes()).hexdigest() for p in E.rglob('*') if p.is_file() and p.name!='integrity.json'}
(E/'integrity.json').write_text(json.dumps({'files':files,'count':len(files)},indent=2),encoding='utf8')
print(json.dumps({'counts':report['counts'],'evidence_files':len(files),'report':str(R.with_suffix('.md'))}))

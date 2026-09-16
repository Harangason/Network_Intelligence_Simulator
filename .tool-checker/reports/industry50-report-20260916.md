# Erneute Agentenprüfung: 50 industrieneutrale Szenarien

Stand: 16.09.2026. **Keine Freigabe für den vollständigen 50-Fälle-Agentenworkflow.**

## Ergebnis und tatsächlicher Umfang

**29 FAILED · 21 PARTIAL.** **0 vollständig bestandene Szenarien nach dem gesamten Quellvertrag.** Das bedeutet nicht, dass jede Teilfunktion defekt ist: PARTIAL bezeichnet ausdrücklich fehlende Folgeprüfungen bzw. offene Entscheidungen, nicht automatisch einen Produktfehler.

- Alle 40 ursprünglichen A/B-Aufträge erneut unverändert über den echten HTTP-Agenten ausgeführt, mit lokaler Inferenz, gespeicherten Entwürfen, Antwortverlauf, Modellzustand und Browserbelegen.
- Die zehn neuen Fälle mit realen Browseraktionen, MCP-Aufrufen, kanonischen Testmodellen und ergänzenden isolierten SQL-/Core-Proben geprüft. Grenzen je Fall stehen unten. Kein Mock-Erfolg wird als E2E-Nachweis gewertet.
- Getestet wurde das veröffentlichte Image `sha256:8c249e600edeca8dc3f924afbb2d6c10eb4f6776f3d54f85ff7aa2ec7394f3cf`, Build `b1297e9bad56`, in einem separaten Stack auf Port 60023. Die PREPARED-Receipt dieses Stacks ist **keine neue Release-PASS-Receipt**.
- Es wurden keine Produktkorrekturen implementiert und keine Produktprojekte verändert. Die bereits vorhandene Release-Gate-Freigabe deckt diesen erweiterten Szenariensatz nicht vollständig ab.
- Vier ergänzende pytest-Beobachtungsproben liefen erfolgreich. Das bestätigt ihre Ausführung, **nicht** vier bestandene Szenarien. Die Proben verwenden denselben Quellstand, aber den lokalen Python-Prozess; Browser/HTTP verwenden das veröffentlichte Image.
- Keine weiteren Architekturentscheidungen automatisch beantwortet. Nur S24 enthält eine ausdrücklich im Testskript vorgegebene Wahl. Fehlende Messgrößen, Bindungen und Kodierungen wurden nicht erfunden.

Quelle: `H:\OneDrive\Download\NETWORK_SIMULATOR_50_INDUSTRY_NEUTRAL_AGENT_MCP_TEST_SCENARIOS.md`  
SHA-256: `25dfcb42be151010693db6a44f9e4f545a3c339627558608c2e659c07ba73a09`

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


Zusätzlicher Browsernachweis S03-A: Auch der Klick auf „Modellvorschlag erstellen“ behebt die verlorenen Angaben nicht. Der Agent verlangt erneut Controller-Zuordnung, Typ/Aufgabe und physische Anschlüsse für Sensor1. Beleg: [Vorschlagsversuch](I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry50/S03-A/proposal-attempt.txt).

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
| S01-A | **FAILED** | 8 Geräte im Entwurf; 7 ohne erkannten Gerätetyp, 8 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S01-B | **PARTIAL** | 8 Geräte im Entwurf; 8 ohne erkannten Gerätetyp, 8 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S02-A | **FAILED** | 5 Geräte im Entwurf; 5 ohne erkannten Gerätetyp, 5 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S02-B | **PARTIAL** | 5 Geräte im Entwurf; 4 ohne erkannten Gerätetyp, 5 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S03-A | **FAILED** | 6 Geräte im Entwurf; 6 ohne erkannten Gerätetyp, 6 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S03-B | **PARTIAL** | 5 Geräte im Entwurf; 5 ohne erkannten Gerätetyp, 5 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S04-A | **FAILED** | 9 Geräte im Entwurf; 5 ohne erkannten Gerätetyp, 9 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S04-B | **PARTIAL** | 8 Geräte im Entwurf; 4 ohne erkannten Gerätetyp, 8 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S05-A | **FAILED** | 7 Geräte im Entwurf; 7 ohne erkannten Gerätetyp, 7 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S05-B | **PARTIAL** | 6 Geräte im Entwurf; 6 ohne erkannten Gerätetyp, 6 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S06-A | **FAILED** | 24 Geräte im Entwurf; 20 ohne erkannten Gerätetyp, 24 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S06-B | **PARTIAL** | 23 Geräte im Entwurf; 23 ohne erkannten Gerätetyp, 23 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S07-A | **FAILED** | 15 Geräte im Entwurf; 15 ohne erkannten Gerätetyp, 15 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S07-B | **FAILED** | 15 Geräte im Entwurf; 15 ohne erkannten Gerätetyp, 15 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S08-A | **FAILED** | 29 Geräte im Entwurf; 29 ohne erkannten Gerätetyp, 29 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S08-B | **PARTIAL** | 28 Geräte im Entwurf; 28 ohne erkannten Gerätetyp, 28 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S09-A | **FAILED** | 37 Geräte im Entwurf; 37 ohne erkannten Gerätetyp, 37 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S09-B | **PARTIAL** | 37 Geräte im Entwurf; 37 ohne erkannten Gerätetyp, 37 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S10-A | **FAILED** | 31 Geräte im Entwurf; 31 ohne erkannten Gerätetyp, 31 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S10-B | **PARTIAL** | 31 Geräte im Entwurf; 31 ohne erkannten Gerätetyp, 31 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S11-A | **FAILED** | 36 Geräte im Entwurf; 36 ohne erkannten Gerätetyp, 36 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S11-B | **FAILED** | 34 Geräte im Entwurf; 34 ohne erkannten Gerätetyp, 34 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S12-A | **FAILED** | 31 Geräte im Entwurf; 31 ohne erkannten Gerätetyp, 31 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S12-B | **PARTIAL** | 30 Geräte im Entwurf; 30 ohne erkannten Gerätetyp, 30 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S13-A | **FAILED** | 27 Geräte im Entwurf; 27 ohne erkannten Gerätetyp, 27 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S13-B | **PARTIAL** | 26 Geräte im Entwurf; 26 ohne erkannten Gerätetyp, 26 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S14-A | **FAILED** | 39 Geräte im Entwurf; 39 ohne erkannten Gerätetyp, 39 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S14-B | **PARTIAL** | 38 Geräte im Entwurf; 38 ohne erkannten Gerätetyp, 38 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S15-A | **FAILED** | 34 Geräte im Entwurf; 34 ohne erkannten Gerätetyp, 34 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S15-B | **PARTIAL** | 33 Geräte im Entwurf; 33 ohne erkannten Gerätetyp, 33 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S16-A | **FAILED** | 49 Geräte im Entwurf; 49 ohne erkannten Gerätetyp, 49 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S16-B | **PARTIAL** | 48 Geräte im Entwurf; 48 ohne erkannten Gerätetyp, 48 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S17-A | **FAILED** | 13 Geräte im Entwurf; 13 ohne erkannten Gerätetyp, 13 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S17-B | **PARTIAL** | 12 Geräte im Entwurf; 12 ohne erkannten Gerätetyp, 12 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S18-A | **FAILED** | 31 Geräte im Entwurf; 31 ohne erkannten Gerätetyp, 31 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S18-B | **PARTIAL** | 30 Geräte im Entwurf; 30 ohne erkannten Gerätetyp, 30 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S19-A | **FAILED** | 251 Geräte im Entwurf; 226 ohne erkannten Gerätetyp, 251 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S19-B | **PARTIAL** | 250 Geräte im Entwurf; 250 ohne erkannten Gerätetyp, 250 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S20-A | **FAILED** | 251 Geräte im Entwurf; 251 ohne erkannten Gerätetyp, 251 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S20-B | **PARTIAL** | 250 Geräte im Entwurf; 250 ohne erkannten Gerätetyp, 250 ohne strukturierte Anschlussangabe. Original erhalten; kein vollständiger Modell-/Routing-/Simulationslauf. |
| S21 | **FAILED** | Einstieg und gespeicherter Entwurf funktionieren im selben Chat. Acht Geräte, aber kein CREATE_ARCHITECTURE-Goal/Execution Plan nachgewiesen; generische Aktoren erhalten unpassend Ventilbefehl-Auswahl. Offene Fachentscheidungen bleiben unbeantwortet. |
| S22 | **FAILED** | 178 echte MCP-Tools entdeckt; Registry und Schemas erreichbar. Nicht existentes Tool liefert INVALID_INPUT statt NOT_SUPPORTED/TOOL_NOT_FOUND. Agentenseitige Registry reduziert Output-Schema; kein explizites Tool-Version-Feld. Vollständiger ParkAssist-Agentenpfad hier nicht behauptet. |
| S23 | **FAILED** | Read-Auftrag läuft über fünf Arbeitsschritte und endet im Browser nach ca. 290 Sekunden mit unterbrochener Antwortverbindung statt fachlichem Ergebnis. Kein Retry ohne Prüfung des laufenden Backend-Auftrags. |
| S24 | **FAILED** | Ein SCRIPTED_TEST-Ja führte im gleichen Workload zur kanonischen Port-/Routingmutation und COMPLETE mit Kapazität, funktionalem Timing und Preflight. Browser zeigt davor eine ungültige Antwortkarte. Daher technischer Teil erfolgreich, Gesamttest mit Darstellungsfehler. |
| S25 | **FAILED** | Negativer Payload liefert INVALID_INPUT; volle Kanäle werden abgewiesen. Unbekannte Technologie liefert SUCCESS mit explizit markiertem GENERIC_ESTIMATE statt NOT_SUPPORTED. Injizierter MCP-Transporttimeout entweicht als TimeoutError statt strukturiertem TOOL_TIMEOUT. Kein automatischer fachlicher Retry geprüft. |
| S26 | **PARTIAL** | Echte persistierte MULTI-Auswahl für zwei Funktionsnachrichten sichtbar, Bestätigen ohne Auswahl deaktiviert. Keine Nutzerentscheidung erfunden; vollständiger Resume bleibt entsprechend Nutzeranweisung offen. Single-Choice-Resume separat in S24 nachgewiesen. |
| S27 | **FAILED** | Signal-Wizard antwortet auf Prüfung des vorhandenen MotorRPM mit Eine positive Gesamtzielmenge konnte nicht ermittelt werden. Fachprüfung wird nicht erreicht. Separater echter MCP-Kern berechnet korrekt 7 Bit und erkennt 4-Bit-Unterdimensionierung. |
| S28 | **PARTIAL** | Realer 15-s-Simulationsjob mit Gateway Delay ab 12s erzeugt 150 Latenzverletzungen und wird im Trace-Wizard analysiert. Kein erfundener Root Cause: ROOT_CAUSE_UNCONFIRMED. Geforderte vollständige Queue-Growth-Kausalkette nicht im Testlauf nachgewiesen; kanonische Route/Snapshot fehlen im aufgebauten Testfixture. Deshalb Teilprüfung, kein E2E-PASS. |
| S29 | **PARTIAL** | Exakter Finding-Lifecycle im isolierten Core geprüft: leere Begründung abgewiesen, ACCEPTED_RISK gespeichert, nach Modelländerung NEEDS_REVIEW; Finding bleibt. Browser-Zusatztest mit textuell vorgegebenem Ausgangsbefund liefert unpassenden Ersatztext über Kapazitäts-/Timingwerte statt Entscheidungskarte. Kein vollständiger Finding-ID/UI-E2E-Nachweis. |
| S30 | **FAILED** | Originalprompt scheitert vor jeder Entscheidung: Parser behandelt DriverAssistance, prüfe die Kommunikation in einer kurzen Simulation als Objektnamen und findet 0 Treffer. Simulation, Trace und Completion werden nicht erreicht. |

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

[Maschinenlesbare Fallmatrix](I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/reports/industry50-report-20260916.json)

[Originalnachweise und Screenshots](I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry50)

[Normalisierter vollständiger Prüfvertrag](I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/industry50.normalized.json)

[Isolierter Teststack / PREPARED-Receipt](I:/PycharmProjects/My_first_Network_Simulator/backend/test-output/industry50-stack/96f25e6a865f/receipt.json)

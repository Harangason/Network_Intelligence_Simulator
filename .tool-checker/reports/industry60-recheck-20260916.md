# Industry60 – erneute Prüfung vom 16.09.2026

**Ziel unter 1 % nicht erreicht und nicht freigegeben.**

60 Fälle bewertet: {'FAILED': 2, 'PARTIAL': 58}. Bestätigte fehlerhafte Fälle: mindestens 3.33 %. Teilprüfungen zählen nicht als bestanden.

Dies ist keine vollständig abgeschlossene Wiederholung aller Pflichtpfade: 40 Original-Architekturaufträge wurden frisch über den Agenten angesprochen und im Browser nachgeladen; offene Entscheidungen wurden nicht erfunden. Integrations- und Trace-Fälle wurden mit den unten genannten Grenzen erneut untersucht. Insbesondere S26/S29 benötigen bessere Ausgangsfixtures, S38 die vollständige Camera-Burst-Kette. Eine Fehlerquote unter 1 % lässt sich daraus nicht behaupten.

## Build und Isolation

Kandidat `f32703613317`, Image `sha256:b8aa1ca221c77c0410a71d8d4b0c0511626709648e4329e0fe34f52555f134e6`. Frische SQL-Datenbank und Runtime im Stack `919f1a3730d4`; keine Produktprojekte verändert. Lokale Modelle qwen3.8:27b und llama3.1:8b erreichbar. Ollama war ausgeschaltet und wurde für den Test gestartet. Source-SHA256: `e0f28f004b5b75a07157c73c3a2a0d7f086956907a6e16e486d6e2a0f2a0b327`.

Der Release-Lauf `65739aa984db` enthält 1796 bestandene Backendtests (2 übersprungen), 390 Frontendtests, Typprüfung, Produktionsbuild, 68 Browser-E2E und den kleinen HTTP-Test. Sein großer HTTP-Test hat keinen Abschlussnachweis; der Prozess war beendet. **Kein PASS-Receipt, keine Auslieferung.** Diese Zahlen sind keine 60 bestandenen Szenarien.

Vier frische isolierte MCP-/Trace-Probes wurden erfolgreich ausgeführt; ihre Assertions sind begrenzte Teilnachweise. HTTP 200 oder Tool SUCCESS allein wurde nicht als fachlicher Szenario-PASS gezählt.

## Bestätigte Befunde

### R01 · P2 · Gemischter Auftrag wird im Erklärungstext auf Temperatur und Ventile reduziert

Originalauftrag umfasst Druck, Drehzahl, Motorcontroller und Relais. Der Antwortentwurf beschreibt nur Temperatursensoren und Ventile und erklärt einen nicht eingegebenen Schreibfehler. Geräteliste enthält dagegen alle acht Geräte; Fehler betrifft die fachliche Zusammenfassung.

Nachweise: ../evidence/industry60-recheck/S01-A/events.json, ../evidence/industry60-recheck/S01-A/browser.txt

### R02 · P1 · Explizite Antriebstechnologie geht im Entwurf verloren

Originalauftrag: EtherCAT für Drives. Alle zehn MotorDrives stehen im persistierten Entwurf mit technology=null und offenen Anschlussangaben. Die bekannte Technologie wird nicht übernommen.

Nachweise: ../evidence/industry60-recheck/S12-A/request.json, ../evidence/industry60-recheck/S12-A/draft.json, ../evidence/industry60-recheck/S12-A/browser.txt

## Nachgewiesene Verbesserungen

- Fehlende Inline-Zeitstempel werden als INVALID_INPUT abgewiesen.
- MCP-Schemafehler enthalten Feld, Grund und erwartetes Schema.
- Normale Gateway-Segmente erzeugen im neuen Lauf keine falschen Routenwechsel.
- Bestehender Anschlussauftrag bleibt auch im CREATE_ARCHITECTURE-Modus erhalten.
- Trace-Auswahl und Zeitfenster bleiben nach Reload erhalten.
- Import: 100501 Ereignisse gespeichert, weitere Seiten abrufbar, anderer Projektkontext erhält 404.
- Kommunikationsprüfung und Trace-Agent liefern einen Abschluss beziehungsweise ausdrücklich INCOMPLETE statt der zuvor beobachteten Schleifen.

## Fallmatrix

| Fall | Ergebnis | Tatsächlicher Umfang / Grenze |
|---|---|---|
| S01-A | FAILED | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S01-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S02-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S02-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S03-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S03-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S04-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S04-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S05-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S05-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S06-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S06-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S07-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S07-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S08-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S08-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S09-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S09-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S10-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S10-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S11-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S11-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S12-A | FAILED | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S12-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S13-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S13-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S14-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S14-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S15-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S15-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S16-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S16-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S17-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S17-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S18-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S18-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S19-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S19-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S20-A | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S20-B | PARTIAL | Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme. |
| S21 | PARTIAL | CREATE_ARCHITECTURE mit Originaltext: persistierter Entwurf; offene Anschlüsse und Geräteaufgaben. Kein vollständiger Wizard-Abschluss. |
| S22 | PARTIAL | Kommunikationsprüfung beendet sich mit ANSWERED und konkreter Wegentscheidung; kein beobachteter Langlauf. Auswahl bleibt offen. |
| S23 | PARTIAL | Bestehende CAN-FD-/Ethernet-Anbindung richtig gelesen. Vollständiger geforderter Visualisierungs-/Toolpfad nicht abgenommen. |
| S24 | PARTIAL | Konkrete Anschlussentscheidung wird gestellt. Keine neue Architekturentscheidung beantwortet; Mutation und große Antwortdarstellung daher nicht vollständig erneut geprüft. |
| S25 | PARTIAL | INVALID_INPUT enthält field/reason/expected_schema; NOT_SUPPORTED und injizierter TOOL_TIMEOUT korrekt. Kanalgrenze ergänzend auf Core-Planung geprüft, kein vollständiger MCP-create_port-Negativpfad. |
| S26 | PARTIAL | Abstrakter Originaltext benennt Quelle/Ziel nicht. Agent meldet 0 Treffer für „eine bestehende Funktion“. Testdaten müssen die vorgesehenen Kontextreferenzen explizit binden; kein Mehrfachentscheidungs-/Resume-PASS. |
| S27 | PARTIAL | MotorRPM wird aus persistiertem Signal geprüft: 4 Bit reichen nicht, 7 erforderlich. Kein automatisches Umkodieren; komplette Binding-Reparatur nicht durchgeführt. |
| S28 | PARTIAL | ANALYZE_TRACE mit echtem SimulationRun endet INCOMPLETE mit Datenlücken, ohne leere Fortsetzungsschleife. Snapshot und vollständige Ursachenkette fehlen im Testaufbau. |
| S29 | PARTIAL | Kein gespeicherter Finding-Datensatz im Fixture: Agent verlangt korrekt Finding-ID/Modellanalyse. Bewertung/Persistenz mangels vollständiger Fixture nicht abgenommen. |
| S30 | PARTIAL | CREATE_ARCHITECTURE überschreibt den Anschlussauftrag nicht mehr. Wegentscheidung für bestehende Funktionen, Simulation und Trace-Folgeauftrag bleiben erhalten; Entscheidung bleibt offen. |
| S31 | PARTIAL | Echte Simulations- und Importsession geladen; Importsession bleibt erhalten und ist projektisoliert. MCP lehnt fehlende Zeit ab. Vollständige Source-/Timebase-/Sync-Metadatenmatrix nicht belegt. |
| S32 | PARTIAL | CAN-FD/Ethernet im echten Browser, Rohdaten, Source/Destination und IDs geprüft. DDS/Modbus/PROFINET/ARINC429-Labels nicht vollständig abgenommen. |
| S33 | PARTIAL | Reale Zwei-Segment-Simulation: Source→Gateway→Destination und Adressen sichtbar; 0 falsche ROUTE_CHANGE im neuen Fault-Fenster. Negativer Route-Mismatch nicht vollständig abgenommen. |
| S34 | PARTIAL | Temperature mit 34,2 degC/VALID sichtbar; MotorRPM-Bitbreite separat geprüft. Fünfkanal- und sämtliche negativen Decode-Fälle nicht vollständig abgenommen. |
| S35 | PARTIAL | Event route-RT-1-target:625:segment:0 bei 12.5001575 s bleibt über Botschaften, Sequenz, Signale, Trace und Reload ausgewählt; Zeitfenster 12,4–12,6 s bleibt. Vollständige Playhead-Abnahme fehlt. |
| S36 | PARTIAL | Neue Golden-/Fault-HTTP-Jobs, Gateway-Delay 12–15 s, 100 ms zusätzliche Latenz, Deadline-Miss und Marker belegt. Queue-Ursachenkette/Snapshot fehlen; keine kausale Freigabe. |
| S37 | PARTIAL | Neuer Golden-Vergleich zeigt erste Abweichung bei 12.00217094 s und 100 ms Zeitdifferenz. Nicht alle zusätzlichen/fehlenden Ereignis-, Zustands- und Routenvarianten getestet. |
| S38 | PARTIAL | Hypothesen/Evidence und explizit unbelegte Ursache geprüft. Die geforderte CameraBurst→Queue→CAN-FD→MotorStatus-Fixture wurde nicht vollständig aufgebaut; keine Ursachenfreigabe. |
| S39 | PARTIAL | 100501 Ereignisse vollständig über HTTP importiert; Browser hält 2000 und lädt Seite 2 ab 2 s. Reload/Projektisolation über API geprüft. Nicht alle Filter und Downsampling vollständig abgenommen. |
| S40 | PARTIAL | Frischer integrierter Teilpfad aus Modell-IDs, Simulation, Views, Golden-Vergleich, Reasoning und Reload. Kein freigegebener vollständiger Snapshot-/Finding-/Completion-Pfad. |

## Nächste Schritte

1. Explizite Technologiebindungen wie „EtherCAT für Drives“ in den Entwurf übernehmen; Regression für S12-A und weitere rollenbezogene Netzangaben.
2. Antwortzusammenfassung ausschließlich aus der tatsächlichen Geräte-/Funktionsliste erzeugen; keine feste Temperatur-/Ventil-Schablone.
3. S26/S29/S38 mit vollständigen, dokumentierten Fixtures versehen und fehlende Trace-Varianten testen. Fehlende Testdaten sind von Produktfehlern zu trennen.
4. Offene Architekturentscheidungen weiterhin offen lassen, bis ausdrücklich beantwortet. Danach vollständige neun Stufen und Trace-Kette wiederholen.
5. Unter 1 % bei 60 Fällen bedeutet 0 fehlgeschlagene Fälle; für eine Vollabnahme dürfen zusätzlich keine Pflichtprüfungen offen bleiben. Danach kompletter Release-Gate-Lauf und ausschließlich dessen PASS-Image ausliefern.

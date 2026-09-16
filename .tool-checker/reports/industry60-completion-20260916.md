# Industry60 – laufende Korrektur und Vervollständigung

Dieser Nachtrag ersetzt keine offenen Pflichtprüfungen durch PASS. Die ursprüngliche 60-Fälle-Matrix bleibt historische Evidence. Build d424cc3e1b44 ist nach vollständigem Release-Gate PASS ausgeliefert. Eine Fehlerquote unter 1 % über alle 60 Szenarien ist weiterhin nicht nachgewiesen.

## Aktueller Stand

Kandidat **d424cc3e1b44** enthält die unten dokumentierten Geräte-, Routing-, Signal-, Trace- und Golden-Korrekturen. Auf diesem Kandidaten wurde S01-A mit den ausdrücklich genehmigten Testannahmen erneut durch alle neun HTTP-Stufen geführt, simuliert und im Browser nachgeladen. Neue Gateway-/Golden-Nachweise stammen aus echten kanonischen Modellobjekten, freigegebenen Snapshots und abgeschlossenen Simulationsjobs. Die Reparatur von Abschnittsidentität und Fensterrand-Zuordnung beseitigt den zuvor reproduzierten Abbruch sowie falsche zusätzliche/fehlende Ereignisse. Der Browser weist den Gültigkeitszeitraum gespeicherter Analysen aus.

Die beiden ursprünglichen Fehler R01/R02 sind erneut direkt per HTTP und persistiertem Entwurf nachgeprüft. Alle 40 A/B-Aufträge wurden frisch eingegeben; das ersetzt keine noch offenen Architekturentscheidungen. **Offen bleiben insbesondere die vollständige CameraBurst-Kette (S38), weitere Trace-MCP-/Decoder-/Filter-Pflichtpfade sowie die inhaltliche Zuordnung offener Architekturvarianten.** Keine pauschale 60/60-Freigabe. Der vollständige Release-Lauf d5ea3ac961a0 ist PASS; der geprüfte Build ist ausgeliefert. Dies schließt die genannten offenen Szenario-Kriterien nicht automatisch ab.

## Bestätigte Korrekturen

- S01-A: Explizite Mehrfachanschlüsse des Controllers bleiben im Entwurf erhalten. Individuelle Messbereiche, Auflösungen und Abtastzeiten werden bis zum Generator weitergereicht. GPIO und PWM sind im kanonischen Interface-Vokabular zugelassen.
- S01-A: SPI/GPIO/PWM werden im Routing nicht mehr zu CUSTOM umgeschrieben. Der reale isolierte HTTP-Ablauf auf Build `f2d330d1ac1a` erreichte alle neun Stufen, erstellte einen Simulations-Snapshot und beobachtete elf vorgesehene Routen/Signale. Assessment PASS; Capacity, Validation und Intelligence melden weiterhin WARNING. Das ist keine Hardwarefreigabe.
- S01-A: Die anschließende Inhaltsprüfung fand die fehlenden ausdrücklich benannten Funktionen. Der Generator erhält diese nun mit Zuordnung zum einzigen Funktionscontroller. Bei mehreren möglichen Controllern wird keine Zuordnung erfunden. Die SQL-Regression enthält die vier Funktionsnamen. Auf Build `ae24b52bb3ec` wurde der vollständige HTTP-Ablauf erneut erfolgreich ausgeführt und alle vier Funktionen anschließend aus dem kanonischen Modell gelesen.
- S25: Der tatsächliche MCP-Aufruf `create_physical_port` wird bei ausgeschöpfter Controllerkapazität abgewiesen. Der Vorher-/Nachher-Vergleich bestätigt unveränderte Interfaces.
- S31: Import-Sessions speichern Metadaten über den gesamten Stream. MCP stellt Source-Typ, Zeitbasis, Synchronisationsstatus und Laufreferenz bereit. Reale HTTP-Quellen wurden durch den tatsächlichen MCP-Server gelesen; fremder Projektkontext ist abgewiesen. Unbekanntes Format und ungültige Metadaten liefern HTTP 422. Fehlende Zeitbasis bleibt unbekannt.
- S32: Neutrale Spalten für gemischte Sessions; eigene DDS-, Modbus-, PROFINET- und ARINC429-Profile. Browsernachweise zeigen Topic/Sequenz, Register, Frame/Cycle Counter und Label/SDI/SSM. CAN-Identifier und Zustands-/Richtungslabels wurden anschließend weiter präzisiert.
- S34: Als Dictionary gelieferte Signale behalten Namen, physikalische Werte, Einheiten, Qualität und diskrete Zustände. Fünfkanal-Import im Browser geprüft. Zusätzlicher Fehler in der gemeinsamen Kontextanzeige (Textzustand wurde als „—“ dargestellt) korrigiert und auf Build `ae24b52bb3ec` im Browser mit „HealthState: WARNING“ bestätigt.
- S35: Auswahl bei genau 12,500 Sekunden bleibt beim Wechsel Botschaften → Signale → Sequenz → Trace erhalten. Vollständige MCP-/Zeitbasis-Negativprüfung noch nicht abgeschlossen.
- S37: Golden-Vergleich zählt reine Signal-, Status- und Pfadabweichungen, zusätzliche/fehlende Ereignisse und Zeitabweichungen. Erste Abweichung wird zeitlich sortiert. Fehlende Zeit, doppelte Identitäten sowie explizit inkompatible/unbekannte Zeitbasen werden abgewiesen.

## Nachweise

- `../evidence/industry60-completion/S01-A/nis-e2e-completion-s01-8fbae1d7/nine-stage-http.json`
- `../evidence/industry60-completion/S01-A/nis-e2e-completion-s01-9b2e2e74/nine-stage-http.json` und `functions.json`
- `../evidence/industry60-completion/S25/full-channel-mcp.json`
- `../evidence/industry60-completion/S31/live-mcp-sessions.json`
- `../evidence/industry60-completion/S32/` (Vorher-/Nachher-Browserzustände, Quelle und Import)
- `../evidence/industry60-completion/trace/` (Negativimporte und Fünfkanal-/Zeitauswahl)
- `../evidence/industry60-completion/S37/mcp-matrix.json` (zehn tatsächliche MCP-Aufrufe, einschließlich Negativfälle)
- `backend/tests/test_shared_draft_workflow.py`
- `backend/tests/test_golden_trace_deviations.py`
- `backend/tests/test_trace_session_metadata.py`
- `backend/tests/test_trace_session_tools.py`

Die importierten UI-Prüfdaten sind ausdrücklich synthetische Testdaten, keine Simulationsergebnisse. S01-A verwendet die vom Nutzer bestätigten Testannahmen; keine Übertragung auf produktive Hardware.

## Weiter offen

Die vollständigen Pflichtpfade der übrigen Architekturvarianten und S21–S40 werden durch diese Teilnachweise nicht als abgeschlossen gewertet. Insbesondere funktionale Ein-/Ausgangszuordnungen, vollständige Signaldecoder-Negativmatrix, Trace-MCP-Fähigkeiten, CameraBurst-Ursachenkette und abschließende persistierte Findings benötigen weitere Arbeit. Weitere Architekturentscheidungen bleiben gemäß Nutzeranweisung offen, bis sie ausdrücklich beantwortet werden.

Release-Lauf `1a0460c09620`: 1830 Backendtests bestanden, zwei übersprungen; wegen Änderungen während der Prüfung bewusst kein PASS-Receipt. Eine Freigabe muss auf dem unveränderten finalen Quellstand erneut vollständig laufen.


## Fortsetzung: reale Browserbefunde und zusätzliche Regressionen

- S27: Im realen Browser die Aktion „Signal prüfen“ ausgeführt, das gespeicherte Signal MotorRPM ausgewählt und den Befund „4 Bit reichen nicht; mindestens 7 Bit“ erhalten. Der Befund bleibt nach Reload erhalten. Kanonisches Signal, Nachricht, Gespräch und Browserzustände liegen unter `../evidence/industry60-completion/S27/`. Dies belegt die fachliche Bitprüfung; die vollständige ausdrücklich verlangte MCP-Werkzeugsequenz ist damit noch nicht nachgewiesen.
- S29: Aus einem gespeicherten Drei-Knoten-Graphen tatsächlich berechneter SINGLE_POINT_OF_FAILURE. Der reale MCP-Agent liest den gespeicherten Befund. Die als SCRIPTED_TEST gekennzeichnete Entscheidung und Begründung persistieren; eine Modelländerung setzt den Status auf NEEDS_REVIEW. Nachweis: `S29/calculated-finding-mcp.json`. Kein Risiko eines Produktprojekts akzeptiert.
- S39: 100.501 importierte Ereignisse über reale HTTP-Paginierung geprüft. Elf Suchdimensionen finden einen Marker hinter der ersten Scan-Seite; das Zeitfenster 99–100 s enthält über drei Seiten exakt 1.001 Ereignisse ohne Lücke/Duplikat. Dies belegt Freitextfilter und Byte-Cursor-Paging, noch keine vollständige typed-filter/downsampling-Abnahme. Nachweis: `S39/http-filter-results.json`.
- Release `be7b2badede7`: 1.835 Backendtests bestanden, zwei übersprungen; 67 Browserfälle bestanden. Der große Browserfall scheiterte zu Recht am unveränderten Signalvertrag: Strom wurde durch eine fehlerhafte Dezimalkomma-Erkennung von Faktor 0,1 / 8 Bit auf Faktor 1 / 5 Bit verändert. Keine Auslieferung.
- Die Dezimalkomma-Erkennung wurde korrigiert und gegen die originale große Eingabe abgesichert. 51 Spezifikationstests bestanden.
- Anschlusslisten: Auch eine spätere Änderung ausschließlich des primären Anschlusses wird gegen die zuvor bestätigte Liste geprüft. Widersprüchliche Änderungen werden ohne Persistenz abgewiesen.
- Korrelation: Fehlende/ungültige Zeitstempel, explizit verschiedene oder unbekannte Zeitbasen und widersprüchliche Werte desselben Signals zum selben Zeitpunkt werden abgewiesen. Boolesche Zustände werden nicht als numerische Messreihen korreliert.
- Golden/Reasoning: Änderungen ausschließlich am physikalischen Wert oder an route_ref(s)/network_id bleiben bei First Divergence sichtbar. 25 gezielte Draft-/Korrelations-/Golden-Tests und anschließend 46 Golden-/Reasoning-Tests bestanden.
- Neuer vollständiger Release-Lauf: `ac66e0885183`, Quellstand `ce66a86bf647`. Noch kein PASS-Receipt und weiterhin keine Gesamtfehlerquote unter 1 % nachgewiesen.

Die vollständige unveränderte 60-Fälle-Spezifikation ist zusätzlich als Tool-Checker-Auftrag `industry60-completion` registriert. Die Registrierung selbst ist kein ausgeführter oder bestandener Fall.

## Fortsetzung: Gateway-Identität, Fensterränder und Zeitbasis

- S37: Reale kanonische Gateway-Simulation mit zwei freigegebenen Snapshots und tatsächlichen Jobs erzeugt (`canonical-trace/`). Der Vergleich brach zunächst ab, weil Route/Sequenz auf beiden Übertragungsabschnitten gleich sind. Identität berücksichtigt nun den Abschnitt; 47 Golden-/Reasoning-Regressionen bestanden.
- S36/S40 Teilpfad: Nach Korrektur liefert die gespeicherte Ursachenanalyse für Fehlerbeginn und Erholung COMPLETE mit belegter GATEWAY_DELAY-Kette. Im breiten Fenster bleibt die Analyse wegen des transparenten Beobachtungsbudgets INCOMPLETE. Keine Queue-Verursachung der Deadline-Verletzung erfunden; der beobachtete Queue-Anteil der betroffenen Ereignisse ist null.
- S37 zusätzlicher Fehler: Ein reiner Vergleich gleicher Ankunftszeitfenster erklärte verspätete Gegenereignisse außerhalb des Fensters fälschlich als zusätzlich/fehlend. Gegenereignisse werden nun über begrenzte Seiten aus dem vollständigen Lauf zugeordnet. Der reale Recovery-Vergleich enthält danach keine falschen MISSING_EVENT/ADDITIONAL_EVENT mehr. 49 Golden-/Reasoning-Tests bestanden. Nachweis: `canonical-trace/reasoning-recovery-aligned.json`.
- Wizard-AMEND: Geräteanschlüsse, bestätigte Anschlusslisten und Geräte-Spezifikationen ersetzen alte Angaben im wirksamen Header. 54 kombinierte Wizard-/Golden-/Korrelationsprüfungen bestanden.
- S35: MCP-Werkzeuge `resolve_trace_time` und `resolve_trace_event_context` ergänzen die gemeinsame Zeit-/Ereignisauflösung. Unterschiedliche oder unbekannte Zeitbasen werden mit TRACE_TIMEBASE_MISMATCH abgewiesen; Ereignisse außerhalb der gewählten Zeit und fremde Projekte werden abgewiesen. Zehn gezielte Tests plus ein tatsächlicher MCP-/HTTP-Test mit fünf Assertions bestanden. Nachweis: `S35/live-mcp-time-context.json`.
- Browser: Gespeicherte Reasoning-Ergebnisse zeigten ihren eigenen Zeitraum nicht an. Die Anzeige nennt nun das analysierte Zeitfenster und warnt bei einer abweichenden aktuellen Auswahl; Browsernachweis des neuen Frontends noch erforderlich.
- Der isolierte Stack d8a5a6840084 enthält ausdrücklich dokumentierte Entwicklungs-Overlays, kein auslieferbares PASS-Image (`canonical-trace/development-overlay.json`). Produktinstallation unverändert.
- Release ac66e0885183 bestand Typprüfung, Frontend- und Backendtests, wurde wegen weiterer Änderungen korrekt ohne PASS beendet. Lauf 4a4a6a3570ff ist durch die anschließend gefundenen Fensterkorrekturen ebenfalls nicht mehr als Freigabenachweis verwendbar. Ein unveränderter finaler Lauf steht noch aus.

## Kandidat d424cc3e1b44

- Produktionsimage `sha256:828817e80a62e18c849d8ba56e7fd2d23a0dc82ece16994a1ec2f91e14987863` erstellt und ausschließlich im isolierten App-Container eingesetzt. Es ersetzt dort die Entwicklungs-Overlays; produktive Installation bleibt bis PASS unverändert.
- S01-A erneut aus dem Originalauftrag mit den ausdrücklich bestätigten Testannahmen erstellt. Alle neun HTTP-Stufen ausgeführt; Snapshot `97c517fd-28c8-4efa-9d0c-0ef022c16f7b`, Job `002a4c4775314d94aecfd5169041b9fe`. 11/11 Signale im gewählten Umfang beobachtet, keine Routenverletzungen oder fehlenden Netz-/Routennachweise. Browser bestätigt gespeicherten COMPLETED-Lauf und Anforderungserfüllung. Capacity/Preflight/Intelligence bleiben WARNING; keine physische Hardware- oder Funktionsregelkreis-Freigabe. Funktionen TemperatureMonitoring, PressureControl, SpeedControl und SafetyShutdown kanonisch vorhanden. Nachweise unter `S01-A/nis-e2e-completion-s01-723bc43b/`.
- Die vier tatsächlichen MCP-Probes für Golden-Matrix, synchronisierten Zeitkontext, ausgeschöpfte Kanalgrenze und berechneten/persistierten Finding-Status erneut bestanden.
- Alle 40 unveränderten A/B-Originalaufträge erneut frisch über HTTP-Agent, persistierten Entwurf und Gespräch geladen. Nachweise: `intakes/d424cc3e1b44/`. Offene Entscheidungen bleiben offen. Dies ist Intake-Regressionsprüfung, keine Behauptung von 40 abgeschlossenen Architekturabläufen.
- Browsernachweis der sichtbaren Zeitraumwarnung und des korrigierten Golden-Fensterrandes: `canonical-trace/browser-window-scope.txt`.
- Vollständiges Release-Gate auf diesem unveränderten Kandidaten: `d5ea3ac961a0`, noch laufend.

## Freigabe der S01-A-Testannahmen und aktueller Volltest

Die ausdrückliche Nutzerantwort bestätigt die genannten S01-A-Testannahmen für den isolierten Versuch. Sie ist keine Bestätigung weiterer funktionaler Zuordnungen oder produktiver Hardwareeigenschaften. Der frische Neun-Stufen-Nachweis liegt unter `../evidence/industry60-completion/S01-A/nis-e2e-completion-s01-723bc43b/nine-stage-http.json`.

Release-Lauf `d5ea3ac961a0`, unveränderter Kandidat `d424cc3e1b44`: Typecheck bestanden, 395 Frontendtests bestanden, 1.856 Backendtests bestanden, zwei übersprungen. Die Browserprüfung läuft noch. Der große Modellfall erreichte nach dem vorgesehenen Capacity-Reparaturablauf die Simulation und den absichtlichen Restart-Test. Der zwischenzeitliche Capacity-ERROR war ein durch die anschließende Modellreparatur behandelter Zwischenstand, kein abgeschlossener Release-Befund.


## Abgeschlossene Release-Prüfung und Auslieferung

- Receipt `backend/test-output/release-gates/d5ea3ac961a0/receipt.json`: **PASS**, alle sechs erforderlichen Prüfungen exit_code 0.
- TypeScript bestanden; 395 Frontendtests; 1.856 Backendtests bestanden, zwei übersprungen; 68 Browser-E2E bestanden. Kleine und große unabhängige HTTP-Abnahme bestanden.
- Großer Browserfall: originale 50/250/250-Eingabe, alle 1.404 Signaldefinitionen, Capacity-Reparatur, realer Simulationsabbruch und Wiederaufnahme, alle neun Stufen nachgewiesen.
- Deployment am 16.09.2026 um 20:39 CEST über `start-networkis.ps1 -ReleaseReceipt ...`. Installiertes Image: `sha256:828817e80a62e18c849d8ba56e7fd2d23a0dc82ece16994a1ec2f91e14987863`. Build `d424cc3e1b44`. Container läuft; Frontend HTTP 200; Build-Manifest im installierten Container stimmt mit Receipt überein.
- Produktprojekte wurden nicht als Testziele benutzt. Keine pauschale 60/60-Abnahme und keine Fehlerquote unter 1 % behauptet.

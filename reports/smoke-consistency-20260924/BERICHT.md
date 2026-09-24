# Smoke- und Konsistenzprüfung vom 24.09.2026

**Ergebnis: Die Durchgängigkeit ist für viele Kernabläufe belegt, aber nicht für alle geprüften Szenarien. Keine Gesamt- oder Releasefreigabe.**

Prüfzeit: 09:14 bis 09:41 Uhr MESZ, rund 27 Minuten innerhalb des 60-Minuten-Budgets. Geprüft wurde das kanonische Projekt `I:\PycharmProjects\My_first_Network_Simulator`, einschließlich seiner bereits vorhandenen lokalen Änderungen. Produktdatenbank und Produktstack wurden nicht als Testziel verwendet. Es erfolgte kein Deployment.

## Erste vollständige Prüfrunde

Quellstand: `760546b8c65a`, SHA-256 `760546b8c65a83a88f652ffb9b0ea0cc195cd62ac1c43b6dd85909a406ec405d`.

| Prüfung | Ergebnis | Aussagegrenze |
|---|---:|---|
| Python-Syntax | 774 Dateien ohne Syntaxfehler | Kein Beweis für Laufzeitkorrektheit aller Pfade |
| TypeScript | bestanden | `tsc --noEmit --incremental false`, Exit 0 |
| Frontend-Regression | 449/449 bestanden | Bibliotheks-/Agentenlogik, kein Ersatz für Browserprüfung |
| Backend mit Wegwerf-PostgreSQL | 1.989 bestanden, 10 fehlgeschlagen, 4 Aufbaufehler, 2 übersprungen; insgesamt 2.005 | Alle gesammelten Fälle ausgeführt; Ergebnisse einzeln in JUnit |
| HTTP-Smoke | 284 Methoden-/Routenbindungen; 6 × HTTP 500 und 1 × HTTP 503 | Ungültige/Sentinel-Eingaben, erwartete 4xx akzeptiert; keine pauschale fachliche Erfolgsprüfung |
| Browser | 66/68 bestanden, 2 fehlgeschlagen, keine Wiederholungen oder übersprungenen Fälle | Darunter 40 Inventarprüfungen, nicht 40 vollständige Neun-Stufen-Projekte |
| Kleiner HTTP-Gesamtablauf | bestanden | Neun Stufen, 6 Routen, 18 Signale, vollständiger ALL-Nachweis, keine fehlenden Beobachtungen, Simulations-Conformance PASS |
| Großer HTTP-Gesamtablauf | fehlgeschlagen | Originalauftrag 50 Controller / 250 Sensoren / 250 Aktoren scheitert an der Modellfreigabe |

Die zwei bewusst optionalen Backend-Prüfungen betreffen die Qualität des echten lokalen Sprachmodells und einen Großresultat-Benchmark. Im isolierten Stack war lokale KI-Inferenz absichtlich nicht angebunden. Die Ergebnisse belegen keine allgemeine LLM-Qualität.

## Nachgewiesene durchgängige Abläufe

- Projekte anlegen, benennen, öffnen und gezielt löschen; Nachbarprojekte bleiben erhalten.
- Entwürfe in Chat und Wizard bearbeiten und persistieren; Geräte entfernen und fehlende Controller ergänzen.
- Konfligierende Änderungen, verlorene Schreibantworten sowie Reload und Anwendungsneustart behandeln.
- Nachrichten-/Signal-Routingfreigaben speichern und nach Reload wiederherstellen.
- Trace-Datei mit 2.501 Ereignissen importieren; Pagination und exakt ausgewähltes Ereignis nach Reload erhalten.
- I²C- und Modbus-RTU-Regelungsprojekte im echten Browser über alle neun Stufen mit Review, Modellübernahme, Simulation und Persistenz abschließen.
- Einen tatsächlichen Modellnachtrag nach Freigabe übernehmen und vorhandene Netzidentitäten erhalten.

## Offener wesentlicher Befund: Empfängerentscheidungen und Abnahmeszenarien

**AUDIT-01, P1:** Der native kleine Automotive-Browserfall und der aufgezeichnete Großauftrag bleiben bei der Modellfreigabe stehen. Die Validierung meldet fehlende oder widersprüchliche Kommunikationspartner. Beim Großauftrag betrifft das 59 Nachrichtenbefunde. Dieselbe Ursache erklärt die 10 fehlgeschlagenen Backend-Tests und die 4 abhängigen Fixture-Aufbaufehler.

Der aktuelle Kommunikationsvertrag verbietet automatische Status-Empfänger wie Diagnose, Gateway oder den ersten Controller. `wizard_communication.communication_plan` lässt nicht bestätigte Ziele ausdrücklich offen, und `contract_findings` verhindert deren Freigabe. Mehrere ältere positive Tests setzen weiterhin diese frühere automatische Zuordnung voraus. Der kleine Browserfall enthält zwar einen Freitextwunsch nach Statusübermittlung, übermittelt aber keine vollständige bestätigte Empfängerzuordnung; er bleibt deshalb ebenfalls blockiert.

Die Validierung wurde **nicht abgeschwächt**, und die unveränderte Großauftragsvorlage wurde nicht durch erfundene Empfänger grün gemacht. Erforderlich ist eine fachlich explizite Abstimmung der Empfänger bzw. einer erlaubten internen Statusverwendung und anschließend eine entsprechende Ergänzung der echten Review-Abnahme. Das ursprüngliche unvollständige Szenario muss als Negativ-/Rückfragefall erhalten bleiben. Die bestehenden Positivfälle und der aktuelle Fachvertrag liefern momentan widersprüchliche Abnahmeerwartungen.

Der kleine HTTP-Fall mit expliziten Kommunikationsbeziehungen besteht. Das grenzt den Fehler auf die Übergabe/Bestätigung dieser Beziehungen ein; es beweist keine allgemeine Durchgängigkeit des unveränderten Großauftrags.

## Lokale Korrekturen nach Abschluss der Prüfrunde

**AUDIT-02, P2:** Erwartete Fehleingaben und nicht vorhandene Objekte lösten unkontrollierte HTTP-500-Antworten aus. Korrigiert wurden:

- Eingabeprüfung und Domain-Fehlerantworten beim Schreiben von Kommunikationsressourcen.
- Fehlende Ausführungsaufträge als 404; fehlende/ungültige Auftrag-ID als 400.
- Strukturtransfer reicht fehlende Angaben an die vorhandene Fachvalidierung weiter, statt vorher mit `KeyError` abzubrechen.
- Räumliche Zonierung lehnt eine noch nicht vorhandene Topologie verständlich ab.

**AUDIT-03, P2:** Ein neues Projekt lieferte beim Öffnen des Speicherordners HTTP 503, weil sein Standardordner erst beim ersten Simulationslauf angelegt wird. Der unbenutzte Standardordner wird nun als leer dargestellt. Lesen legt keine Ordner an. Fehlende explizit gewählte Speicherorte und echte Berechtigungsfehler bleiben Fehler.

**Gezielte Reparaturprüfung: 129/129 Tests bestanden.** Darunter sind 18 neue Regressionsfälle sowie bestehende API-, Auftrags-, Kommunikationsreparatur-, Zonierungs-, Speicher- und Assistant-Capability-Tests. Geprüft wurden auch Projektisolation, unveränderte Modellversionen nach abgewiesenen Eingaben, erhaltene 409-Revisionskonflikte und das Weiterreichen echter Programmierfehler. Eine bestehende Pydantic-Warnung zu `EngineeringModelDelta.validate` bleibt bestehen.

Die Korrekturen sind lokal. Die komplette erste Prüfrunde wurde nicht als zweite Vollabnahme wiederholt, weil AUDIT-01 offen bleibt. Die Nachprüfungen der Reparaturen ersetzen keine vollständige neue Kampagnen-/Releaseabnahme.

## Nachprüfung des korrigierten Images

Quellstand `cc26edaeb079`, SHA-256 `cc26edaeb079da0e3899ae2baa8a91a9b830724e82e5adfa1139cc8e0ee946a6`. Isoliertes Image `sha256:2b93c71aaad7aecbc17bd63b9d61f933b4561ebd04054a40f80b1584276903dd`.

- HTTP-Smoke: **284/284 Methodenbindungen ohne 5xx, 405, Timeout oder Verbindungsfehler**. Die sieben zuvor fehlerhaften Antworten sind korrigiert.
- Kleiner HTTP-Gesamtablauf erneut bestanden: neun Stufen, 18 beobachtete Signale, sechs geprüfte Routen, keine fehlenden Beobachtungen, Conformance PASS. Die abschließende Intelligence-Stufe trägt weiterhin eine dokumentierte WARNING, keine behauptete KI-Qualitätsfreigabe.
- Vier gezielte Browser-Nachprüfungen bestanden: Projektlöschung mit Isolation, Routingfreigaben mit Reload, Einstellungen und Trace-Import mit Auswahlpersistenz.
- Der Frontend-Build samt Typprüfung im korrigierten Image ist erfolgreich.

Die offene Abnahmekollision AUDIT-01 verhindert weiterhin ein Gesamt-PASS. Der Reparaturnachweis für AUDIT-02 und AUDIT-03 darf nicht mit einer erfolgreichen Wiederholung aller 2.005 Backend- und 68 Browserfälle verwechselt werden.

## Nachweise

- [Erste Backend-Runde](backend.xml), [Protokoll](backend.log)
- [Frontend](frontend.log), [Syntax-/Typprüfung und Einzelbefunde](checks-summary.json)
- [HTTP-Smoke vor Korrektur](http-smoke.json), [Server-Fehlerdetails](service-backend.log)
- [Browser-Ergebnisse](browser.json), [Browser-Protokoll](browser.log); Screenshots, Videos und Traces liegen im Unterordner `browser`.
- [Kleiner HTTP-Gesamtablauf](workflow-small.json), [Großer HTTP-Gesamtablauf](workflow-large.log)
- [Reparaturregression](repair-regression.xml), [Protokoll](repair-regression.log)
- [HTTP-Smoke nach Korrektur](http-smoke-repaired.json), [kleiner Gesamtablauf nach Korrektur](workflow-small-repaired.json), [vier Browser-Nachprüfungen](browser-repair.json)
- [Befundregister der ersten Runde](findings.json), [Sollinventar](inventory.json)
- Tool-Checker-Kampagne: `.tool-checker/state/campaigns/smoke-consistency-20260924`; vorherige Kampagnen wurden erhalten.

Die isolierten Images wurden mit dem bestehenden Runtime-Abhängigkeitsstand und aktuellem Quellcode gebaut. Ihre PREPARED-Nachweise sind keine Release-PASS-Receipts. Die vorhandenen Releasevorgaben bleiben unverändert.

Die beiden eigens angelegten Teststacks wurden nach Sicherung ihrer Laufzeitdaten und Dienstlogs entfernt; fremde Teststacks blieben erhalten. Die Archive liegen unter `runtime-evidence-514e6492cc50` und `runtime-evidence-655ad99ad418`; [Cleanup-Nachweis](cleanup.json). Die Kampagne wurde mit den offenen Befunden beendet und ist ausdrücklich nicht PASSED. Weiterführende fachliche Empfängerentscheidungen wurden nicht allein zur Erfüllung alter Positivtests getroffen.

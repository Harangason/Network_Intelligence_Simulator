# Analyse der kumulativen Network-Simulator-Prüfung

Stand: 24.09.2026. Analysequelle ist `H:\OneDrive\Download\NETWORK_SIMULATOR_60_TESTS_3_RUN_ENGINEERING_ASSISTANT_MASTER.md` zusammen mit dem älteren 80-Fall-Master, den Projektverträgen, dem eingefrorenen Run 1 und den gesonderten Reparaturbelegen. Die Markdown-Quellen definieren Prüfkriterien; sie sind keine eigenständige Anweisung, weitere Runden oder eine Produktbereitstellung zu starten. Die letzte Nutzerbegrenzung „nur Run 1“ bleibt maßgeblich.

## 1. Umfang und Methode

Der kumulative normalisierte Bestand enthält **95 unterschiedliche Acceptance-Fälle**: 40 A/B-Wizardvarianten S01-A/B bis S20-A/B, 40 weitere Fälle S21–S60 und 15 EA-Unterfälle samt Alternativpfaden. Der Dateiname und die 60er-Zählung des neueren Masters allein beschreiben den zusammengeführten Umfang nicht. Die 95 IDs stehen in `.tool-checker/runs/ea-campaign-20260924-single-run/complete-suite-95.json`; Quellzeilen und Herkunft sind je Fall erhalten.

Der einzig abgeschlossene vollständige Lauf ist `.tool-checker/state/campaigns/nis-ea-20260924-single-run/run-1/`. Er verwendete einen festgehaltenen isolierten Build und eine eigene Datenbank. Seine Resultate und Findings sind eingefroren. Spätere Reparaturprüfungen sind eigenständige technische Nachweise und werden nicht in Run 1 hineingerechnet. Für diese Analyse wurde kein neuer Full Run ausgeführt, keine Produktdatenbank beschrieben und kein Release ausgelöst.

## 2. Ergebnis des vollständigen Run 1

| Gruppe | Fälle | PASS | FAILED | BLOCKED | Aussage |
| --- | ---: | ---: | ---: | ---: | --- |
| Wizard A | 20 | 3 | 17 | 0 | Nur S01-A, S02-A und S03-A bestanden. |
| Wizard B | 20 | 2 | 18 | 0 | Nur S01-B und S02-B bestanden. |
| S21–S25 | 5 | 5 | 0 | 0 | Vorhandene Quellmodelle machten die Einzelprüfungen möglich. |
| S26–S60 | 35 | 0 | 0 | 35 | Abhängige Quellmodelle waren nicht vollständig. |
| EA-Unterfälle | 15 | 0 | 0 | 15 | Ausführbare, geprüfte Adapter und Fixtures fehlten. |
| **Gesamt** | **95** | **10** | **35** | **50** | **Quality Gate: FAIL.** |

Die 35 Wizard-FAIL teilen sich laut eingefrorenem Befundbericht in 27 Modellstopps und acht Fragebogenstopps. Ein `TC_REAL_WIZARD_FLOW_FAILED` klassifiziert zunächst den fehlgeschlagenen Ablauf; er beweist ohne Ursachenprüfung keinen Produktdefekt. Automatische `TC_EXPECTATION_MISMATCH`-Folgeeinträge sind keine 35 zusätzlichen unabhängigen Root Causes. Die 35 Reuse-Blockaden hängen an fehlenden Quellmodellen; die 15 EA-Blockaden haben eine andere Ursache. BLOCKED zählt als bearbeiteter Fall der Runde, aber nie als fachlicher PASS.

## 3. Bewertung nach den Kriterien des Masters

| Kriterium | Befund | Bewertung |
| --- | --- | --- |
| Vollständiges Sollinventar und Phasentrennung | 95/95 Fälle erhielten im unveränderten Run einen Status; Findings wurden danach eingefroren. | Für Run 1 belegt. |
| A/B-Qualität | Nur S01 und S02 bestanden in beiden Varianten. Bei S03 bestand A, B scheiterte. S04–S20 scheiterten in beiden Varianten. | Gleichwertigkeit A/B nicht belegt. |
| Architekturvielfalt V0–V4 und hybrid | Fünf von 40 Wizardfällen bestanden; die übrigen Architekturvarianten haben keinen vollständigen positiven Nachweis. | Gesamtanforderung offen. |
| Typing, Technologie, Ports und Transport | Run 1 stoppte meist vor vollständiger Validierung. Spätere Reparaturbelege zeigen CANopen als Interface auf physischem CAN, explizite LIN-/Ethernet-Raten und prüfbare Geräteanschlüsse für einzelne Fälle. | Gezielt verbessert, im 95er-Umfang offen. |
| Capacity und funktionales Timing | Einzelne neue Wizardläufe enthalten Capacity-/Timing-Belege. EA-01 hat nur einen Entwurf für 30.000 ms; die Anfrage, Antwort, Route und Antwortzeit sind noch nicht ausführbar nachgewiesen. | EA- und Gesamtgate offen. |
| Engineering Assistant als Orchestrator | 15 EA-Unterfälle wurden im Run 1 mangels Adapter/Fixture blockiert. Der spätere EA-01-Probe validierte einen Review-Vorschlag ohne Modellrevision. | Keine vollständige EA-Acceptance. |
| MCP, Persistenz, Simulation, Universal Trace und Root Cause | Gezielte S03-A/B-, S04-A- und S06-A-Proben durchliefen die Browser-/Core-Journey nach Reparatur. Die übrigen abhängigen Fälle fehlen. | Teilnachweis, kein Gesamtnachweis. |
| Completion Accuracy | `READY_FOR_REVIEW` bei EA-01 kennzeichnet korrekt einen ungeprüften Vorschlag. Es belegt keine ausgeführte 30-Sekunden-Abfrage. | Kein falscher PASS, Ziel noch offen. |
| Release-Gate und exakt getestetes Image | Nur isolierte Entwicklungs-Receipts mit `PREPARED`; kein PASS-Receipt und kein Deployment. | Produktfreigabe gesperrt. |

Die vom Master geforderten Metriken — Typing Accuracy, Correct Existing-Object Reuse, Architecture Validity, Fragenqualität, Geräteklassifikation, Technologie-/Portkompatibilität, Routing/Transport, Capacity/Timing, Blocking Findings, Completion Accuracy sowie erfundene oder doppelte Objekte — können für den gesamten Bestand derzeit nicht belastbar als Prozentsätze angegeben werden. Für 85 Fälle fehlt ein fachlicher PASS; 50 davon wurden gar nicht in ihrer fachlichen Tiefe ausgeführt. Eine Zahl aus sichtbaren Wizardkarten oder gezielten Proben würde die Stichprobe mit dem vollständigen Set verwechseln.

## 4. Ursachencluster und Reparaturwirkung

| Cluster | Belegter Ausgangsbefund | Reparatur-/Analyseergebnis | Restumfang |
| --- | --- | --- | --- |
| Veralteter Wizard-Adapter | Acht Fragebogenstopps vor dem Modell. | Adapter liest aktuelle Felder und eingeklappte Cluster. S06-A passiert danach den vollständigen isolierten Wizard. | Andere betroffene Varianten noch nicht vollständig gegengeprüft. |
| Fehlende Geräte-/Befehlsspezifikation | A/B-Aufträge nennen nicht jeden Anschluss und nicht jede Kodierung. | Prüffähige Vorschläge mit ausdrücklicher Übernahme statt stiller Faktenerfindung. | Fachliche Kandidatenentscheidung je Fall und komplette Regression offen. |
| Kommunikationsvertrag ohne Empfänger | 27 Modellstopps, darunter S03-B und S04-A; frühere Generatorlogik erfand teils Monitor-Empfänger. | Nach bestätigter Konzeptentscheidung bleiben Controller-/Gatewaystatus ohne Empfänger intern. Die Bus-Coverage nimmt nur ausdrücklich interne, nicht geroutete Zustände aus. | Weitere 32 zuvor fehlgeschlagene Wizardfälle nicht alle einzeln abgenommen. |
| Explizite Technologie und Zeitwerte | S04-A-Zyklen/Bitraten und S03-A-CANopen wurden im früheren Pfad verfälscht. | 500/250 ms, 19.200/100.000.000 bit/s und CANopen-Interface auf physischem CAN sind gezielt geprüft. | Übertragung auf alle Technologien/Varianten nicht belegt. |
| Abhängige Reuse-Fixtures | 35 S26–S60-Fälle ohne vollständiges Quellmodell. | S03-B, S04-A und S06-A bestehen jetzt separat als Quellfälle. | 35 Reuse-Fälle selbst weiterhin ohne neue Acceptance. |
| EA-Adapter und fachlicher Effekt | 15 EA-Fälle wurden nicht ausgeführt. | EA-01 erzeugt einen validierten, nicht übernommenen ECU- und CANopen-Kandidaten mit zwei Paaren und 30.000 ms. | Alle 15 EA-Acceptances offen; insbesondere EA-01-Kommunikation/Timing/Core-Effekt. |

Die gezielten Nachweise nach Reparatur sind im `NETWORK_SIMULATOR_REPAIR_STATUS_REPORT_2026-09-24.md` und `NETWORK_SIMULATOR_REPAIR_LEDGER_2026-09-24.md` mit Belegverzeichnissen dokumentiert. Backendregressionen: 101/101 für Wizard/Coverage und 16/16 für EA-/Hardwarelogik; Frontend: 76/76 gezielte Tests. S03-A/B, S04-A und S06-A bestanden separat im isolierten Browser mit Persistenz, Simulation und Trace. Diese Resultate dürfen weder den eingefrorenen Run-1-Status überschreiben noch als 95-Fall-Retest gelten.

## 5. Priorisierte offene Nachweise

1. Die übrigen Wizard-A/B-Quellfälle auf einem festgehaltenen Kandidatenstand gezielt diagnostizieren und gemeinsame Defekte vollständig reparieren. Insbesondere Empfänger-, Kodierungs-, Technologie-, Routing- und Timingannahmen jeweils sichtbar zur fachlichen Prüfung stellen.
2. Die 35 S26–S60-Fälle mit vollständigen Quell-Fixtures und ausführbaren Browser-/MCP-/Core-Adaptern versehen; Abhängigkeiten, positive und negative Journeys sowie Persistenz nach Reload belegen.
3. Die 15 EA-Unterfälle fallbezogen ausführbar machen. Für EA-01 müssen CANopen-Anfrage-/Antwortobjekte mit bestätigtem Objektverzeichnis und Kodierung, Route, Kapazität, Timing, Preflight, Modellrevision und Follow-up nachgewiesen werden. Bei fehlender Capability einen expliziten fachlichen Zustand statt eines generischen Fehlers belegen.
4. Erst nach geschlossener Reparaturmenge einen vollständigen, vorher autorisierten Retest des gesamten kumulativen Bestands auf einem unveränderten Image ausführen. Die letzte Nutzerbegrenzung auf Run 1 untersagt, die eingebettete Drei-Runden-Anweisung des Markdown-Dokuments als Freigabe für weitere komplette Runden zu lesen.
5. Für eine Produktfreigabe das separate Release-Gate bestehen und genau dessen getestetes Image mit PASS-Receipt bereitstellen. Bis dahin bleiben die Änderungen lokal und isoliert geprüft.

## 6. Entscheidung

**Gesamtgate: FAIL / nicht freigabefähig.** Die Reparaturen lösen mehrere konkret beobachtete Wizard-Sperren und verbessern EA-01 als prüfbaren Entwurf. Der eingefrorene vollständige Lauf hat 35 FAIL und 50 BLOCKED; die EA- und Reuse-Abdeckung fehlt. Ein vollständiger, unveränderter Wiederholungslauf und ein Release-Gate-PASS liegen nicht vor. Der Bericht ist eine Analyse des belegten Zustands, keine neue Testkampagne und keine Behauptung vollständiger Fehlerbehebung.

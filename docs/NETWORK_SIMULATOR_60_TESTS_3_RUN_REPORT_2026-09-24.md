# Network Simulator: 60 Tests, drei Läufe und Engineering Assistant – Prüfbericht

Berichtsstand: 24.09.2026 00:48:10 CEST. Verbindlicher Endtermin laut Klarstellung: 24.09.2026, 08:00 Uhr Europe/Berlin. Die Nutzeranweisung lautet, nach Lauf 3 zu stoppen und vollständig zu berichten.

## Ergebnis und Umfang

Die kumulative Prüfsuite enthält **95 ausführbare Fälle**: 40 Varianten S01-A/B bis S20-A/B, 40 Fälle S21–S60 sowie 15 Engineering-Assistant-Akzeptanzfälle aus EA-01 bis EA-12 (einschließlich der drei zusätzlichen Negativ-/Vorbedingungsvarianten). Das neue Masterdokument ist eine Prüfquelle, keine unmittelbare Arbeitsanweisung für jede darin erwähnte Aktion. Die 60 überlappenden Fälle sind mit ihren neuen Quellabschnitten verknüpft; S41–S60 stammen aus der bestehenden kumulativen Suite.

**Lauf 1: FAIL** – 4 bestanden, 11 fehlgeschlagen, 80 blockiert (95 von 95 einzeln erfasst). Eingefroren am 24.09.2026 00:12:44 CEST. Lauf 2 und Lauf 3 wurden wegen offener Reparaturen nicht begonnen. Damit ist die Gesamtabnahme nicht bestanden; es gibt keinen Release-PASS und keine Bereitstellung.

| Lauf | Zustand | Bestanden | Fehlgeschlagen | Blockiert | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | eingefroren | 4 | 11 | 80 | FAILED |
| 2 | nicht gestartet | – | – | – | durch Reparatur-Gate gesperrt |
| 3 | nicht gestartet | – | – | – | durch Reparatur-Gate gesperrt |

## Prüfstand und Nachweisgrenzen

- Kanonisches Projekt: `I:\PycharmProjects\My_first_Network_Simulator`; Quellcommit vor dem Lauf: `9516b568626368fa1cd69c40f2a2a20da778ca55`. Im Arbeitsverzeichnis waren bereits vor Beginn 2390 verfolgte Löschungen vorhanden; sie wurden nicht rückgängig gemacht.
- Neues Masterdokument: `H:\OneDrive\Download\NETWORK_SIMULATOR_60_TESTS_3_RUN_ENGINEERING_ASSISTANT_MASTER.md`; SHA-256 `98e677944fe7fb7fb50c24398b6f3bfd3c1ae6c160a805b39485c4c95dad1119`.
- Runde 1 begann am 24.09.2026 00:05:50 CEST; Build-Receipt: `I:\PycharmProjects\My_first_Network_Simulator\.tool-checker\runs\ea-campaign-20260923-isolation\619825de332e\receipt.json`. Image `sha256:c4179767ca0ab0ac0f54cd1c1d820bcfc54f5fd04a25a94a061b2b9db0cae6a9`; isolierter Wegwerfstack auf Loopback-Port 56048; `development_only=true`. Produktdienst und Produktdatenbank waren keine Testziele.
- Browser- und Backend-Nachweise wurden für die wirklich ausgeführten Fälle gespeichert. Die 80 blockierten Fälle besitzen nur Blockierungsnachweise, keine fachliche Ausführung. Vier bestandene Einzelfälle belegen nicht den vollständigen neunphasigen Wizard-Ablauf für die gesamte Suite.
- Eingefrorene Runde: `I:\PycharmProjects\My_first_Network_Simulator\.tool-checker\state\campaigns\nis-ea-20260924-final\run-1\results.json` und `I:\PycharmProjects\My_first_Network_Simulator\.tool-checker\state\campaigns\nis-ea-20260924-final\run-1\findings.json`. Maschinenlesbare Fallmatrix: `I:\PycharmProjects\My_first_Network_Simulator\.tool-checker\runs\ea-campaign-20260923\case-results-run-1.csv`; Befundledger: `I:\PycharmProjects\My_first_Network_Simulator\.tool-checker\runs\ea-campaign-20260923\finding-ledger-run-1.csv`.

## Befunde

- **11 FAIL**: 9 am Engineering-Modell und 2 bereits im Fragebogen. Die neun Modellfälle stoppten überwiegend an fehlenden oder widersprüchlichen Nachrichtenempfängern. Die Testautomatisierung hatte keine geprüfte Fortsetzung über `Ergänzen`. Ein offener Empfänger darf fachlich nicht still erfunden werden.
- **25 BLOCKED**: Wizard-Adapter hätte Nachweise in einem gemeinsam genutzten historischen Verzeichnis geschrieben.
- **40 BLOCKED**: Wiederverwendungsadapter verlangte einen anderen Projektpräfix und hätte ebenfalls gemeinsame Nachweise benutzt.
- **15 BLOCKED**: Für EA-Akzeptanzfälle fehlten geprüfte ausführbare Adapter und fallbezogene Startzustände.
- Das Ledger enthält 102 offene Einträge aus Runde 1: 80 Blockierungsbefunde sowie je zwei Einträge zu den 11 FAIL-Fällen. Die Kategorie `TC_EXPECTATION_MISMATCH` ist ein automatisch erzeugter Folgeeintrag und beweist für sich allein keinen falschen Fachvertrag.

## Reparaturphase nach dem eingefrorenen Lauf

- Die Belegablage des Sweep-Moduls verwendet jetzt `TOOL_CHECKER_EVIDENCE_ROOT`; der Rundenausführer setzt ein separates Verzeichnis. Die 80 vorhandenen Adapterpläne verwenden frische Projekt-IDs mit dem vom Wiederverwendungsadapter akzeptierten Präfix.
- Eine gezielte Konfigurationsprüfung aller 80 Adapterpläne, des Evidence-Roots und des Präfix-Guards bestand. Nachweis: `I:\PycharmProjects\My_first_Network_Simulator\.tool-checker\runs\ea-campaign-20260923\repair-1-harness-verification.json`. Diese Prüfung ersetzt keinen Anwendungsfall und keine neue Vollrunde. Der Reparaturnachweis deckt die 65 Harness-Blockierungen ab.
- Die neue Masterquelle wurde für alle überlappenden Fälle abschnittsgenau ergänzt und in der Reparaturphase neu aufgenommen. Dadurch sind alle 95 früheren Fallverträge als `OUTDATED` markiert; ein neuer vollständiger Lauf wäre für eine Abnahme erforderlich.
- Eine bestätigte Erkennungslücke für `CANopen` im Wizard wurde geschlossen. Der neue isolierte Browserlauf zeigte CANopen und Ethernet beide ausgewählt. 73 Frontendtests, der TypeScript-Check und 9 Tests des Generation-Rule-Managers bestanden. Die Registry bleibt die Quelle der Technologieprofile.
- Die AMEND-Schranke akzeptiert jetzt `controller_status_scope` und `functional_routes` für einen noch nicht übernommenen Modellvorschlag; nach Modellübernahme verlangt eine Änderung dieser Kommunikationsentscheidungen weiterhin einen eigenen geprüften Vorschlag. Zwei neue gezielte AMEND-Tests und 16 Kommunikationsplan-Tests bestanden in Wegwerf-PostgreSQL-Instanzen. Der gesamte Testblock `test_wizard_amendment_model.py` hatte vier Setupfehler, weil seine bestehende Fixture ein Modell mit ungeklärten Empfängern freigeben will; sieben andere Tests darin bestanden. Daher wird dieser Block nicht als vollständig bestanden gewertet.
- Auf dem zweiten Reparaturimage gelang S03-A nach expliziter Testentscheidung zur Gateway-Rolle und zu internen Statuswerten bis zu einem gültigen Modellvorschlag (50/50), dessen Übernahme und sechs gültigen, freigegebenen Routen. Der nächste Schritt blieb gesperrt: Der Netzwerkvorschlag hat einen unverbundenen Gateway-Knoten (ein ungültiger Knoten). Die neun Phasen sind nicht abgeschlossen. Nachweis: `I:\PycharmProjects\My_first_Network_Simulator\.tool-checker\runs\ea-campaign-20260923\repair-1-s03-targeted-result.json`; Entwicklungs-Receipt: `I:\PycharmProjects\My_first_Network_Simulator\.tool-checker\runs\ea-campaign-20260923-isolation-repair2\bfa415e8d205\receipt.json`.
- **37 Befunde sind ohne verifizierte Reparatur offen**: 15 fehlende EA-Ausführungen und 22 Wizard-Befunde. Zusätzlich wurde in der Reparaturprobe der unverbundene Gateway-Knoten als Folgeblocker sichtbar. Die Kampagne wurde mit Zustand `STOPPED` beendet. Ein `repair-complete` und Lauf 2 waren mit diesen offenen Befunden unzulässig.
- Eine gezielte S03-A-Diagnose im Wegwerfprojekt zeigte, dass eine natürliche Ergänzung zwar als neue Revision gespeichert wurde, die Empfängerplanung aber nicht auflöste. Eine erste typisierte Graph-Ergänzung zählte das Gateway irrtümlich als zweite ECU (`ecus: 2 > 1`), weil die Gateway-Rolle in dieser Testeingabe nicht markiert war. Die lokale Extraktion des später gespeicherten effektiven Prompts gelang. Im neuen Image wurde die Gateway-Rolle ausdrücklich angegeben und der Modellvorschlag dadurch gültig; die Netzwerktopologie blieb als nächste Grenze offen. Diagnose: `I:\PycharmProjects\My_first_Network_Simulator\.tool-checker\runs\ea-campaign-20260923\repair-1-s03-prompt-diagnostic.json`. Diese Probe ändert das eingefrorene Laufergebnis nicht.

## Einzelinventar: eingefrorene Ergebnisse von Lauf 1

`Reparaturnachweis` bezeichnet nur die gezielte Harness-Korrektur; es ist kein bestandener Wiederholungstest.

| Fall | Titel | Lauf 1 | Reparaturnachweis | Befund / Blockierungsgrund |
| --- | --- | --- | --- | --- |
| S01-A | Kleine lokale Regelung – A | PASSED | – | Frischer Prüflauf abgeschlossen; siehe eingefrorenes Ergebnis und Nachweise. |
| S01-B | Kleine lokale Regelung – B | PASSED | – | Frischer Prüflauf abgeschlossen; siehe eingefrorenes Ergebnis und Nachweise. |
| S02-A | Pumpenregelung – A | PASSED | – | Frischer Prüflauf abgeschlossen; siehe eingefrorenes Ergebnis und Nachweise. |
| S02-B | Pumpenregelung – B | PASSED | – | Frischer Prüflauf abgeschlossen; siehe eingefrorenes Ergebnis und Nachweise. |
| S03-A | Positioniersystem – A | FAILED | – | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. Embedd… |
| S03-B | Positioniersystem – B | FAILED | – | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. Contro… |
| S04-A | Klima-/Lüfterregelung – A | FAILED | – | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. Contro… |
| S04-B | Klima-/Lüfterregelung – B | FAILED | – | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. Steuer… |
| S05-A | Sicherheitsüberwachung – A | FAILED | – | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. Safety… |
| S05-B | Sicherheitsüberwachung – B | FAILED | – | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. Sicher… |
| S06-A | Verteilte Maschinenzelle – A | FAILED | – | Error: Questionnaire blocked at step 4: GEFÜHRTE ANLAGE Engineering-Auftrag erstellen Technische Vorgaben festlegen und anschließend v… |
| S06-B | Verteilte Maschinenzelle – B | FAILED | – | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCCont… |
| S07-A | Mobiles Robotersystem – A | FAILED | – | Error: Questionnaire blocked at step 1: gen geplant 16 Parameter Technologie-Defaults SYSTEMCLUSTER SCHRITTWEISE PRÜFEN Je Cluster zue… |
| S07-B | Mobiles Robotersystem – B | FAILED | – | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCCont… |
| S08-A | Energieverteilung – A | FAILED | – | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCCont… |
| S08-B | Energieverteilung – B | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S09-A | Gebäudezonen – A | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S09-B | Gebäudezonen – B | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S10-A | Wasseraufbereitung – A | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S10-B | Wasseraufbereitung – B | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S11-A | Technischer Prüfstand – A | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S11-B | Technischer Prüfstand – B | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S12-A | Autonomes Fördersystem – A | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S12-B | Autonomes Fördersystem – B | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S13-A | Laborautomatisierung – A | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S13-B | Laborautomatisierung – B | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S14-A | Mobile Arbeitsmaschine – A | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S14-B | Mobile Arbeitsmaschine – B | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S15-A | Technisches Hilfssystem – A | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S15-B | Technisches Hilfssystem – B | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S16-A | Lagerautomatisierung – A | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S16-B | Lagerautomatisierung – B | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S17-A | Verteiltes Messsystem – A | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S17-B | Verteiltes Messsystem – B | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S18-A | Multi-Axis Motion – A | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S18-B | Multi-Axis Motion – B | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S19-A | Große heterogene Automatisierungsplattform – A | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S19-B | Große heterogene Automatisierungsplattform – B | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S20-A | Großes Multi-Technology-System mit Simulation und Trace – A | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S20-B | Großes Multi-Technology-System mit Simulation und Trace – B | BLOCKED | ja | Current wizard adapter writes to the shared historic evidence directory; further execution could overwrite prior evidence. |
| S21 | Fähigkeiten/Wizards: Einstieg „Architektur erstellen“ | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S22 | MCP Capability Discovery und Tool Registry | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S23 | MCP Read Path: bestehendes Modell wirklich verstehen | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S24 | MCP Mutation: fehlenden CAN-Port nach Nutzerentscheidung vollständig umset… | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S25 | MCP Schema-, Fehler- und Timeout-Verhalten | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S26 | Chat Agent: Single-/Multi-Choice und Workload Resume | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S27 | Wizard „Signal prüfen“: MCP bis zur fachlichen Validation | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S28 | Wizard „Trace analysieren“: MCP, Simulation Trace und Root Cause | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S29 | Wizard „Finding bewerten“: Entscheidung, Persistenz und Audit | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S30 | Vollständiger Chat-Agent/MCP/Browser-Systemtest | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S31 | Trace Session laden | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S32 | Botschaften-View | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S33 | Sequenz-View und Gateway-Hops | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S34 | Signale-View und Decode | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S35 | Synchronisierte Trace Views | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S36 | Fault Injection bis Trace Evidence | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S37 | Golden Trace Vergleich | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S38 | Root Cause Analyse | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S39 | Filter, Suche und große Trace-Datenmengen | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S40 | Vollständiger Trace-Analyse-E2E-Test | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S41 | Wizard-Startseite und Capability-Zuordnung | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S42 | Architektur-Wizard vollständig | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S43 | Architektur-Wizard mit bestehendem Modell | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S44 | Signal-prüfen-Wizard vollständig | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S45 | Trace-analysieren-Wizard vollständig | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S46 | Finding-bewerten-Wizard vollständig | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S47 | Wizard State, Zurück, Weiter und Resume | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S48 | Wizard Validation und Pflichtfelder | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S49 | Wizard zu MCP zu Core Vertrags- und Revisionsprüfung | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S50 | Vollständiger Wizard-Regressionslauf | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S51 | Goal Understanding und Typing | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S52 | Model Awareness | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S53 | Decision Detection | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S54 | Engineering Planning | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S55 | Skill- und MCP-Tool-Auswahl | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S56 | Autonomous Execution | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S57 | Workload Persistence und Resume | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S58 | Validation und Repair Loop | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S59 | Completion Evaluator | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| S60 | Vollständiger Engineering-Agent-E2E-Test | BLOCKED | ja | Current reuse adapter requires a different project prefix and writes to the shared historic evidence directory; execution cannot produ… |
| EA-01 | Periodische Stellgliedabfrage | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-02 | Follow-up-Reparatur | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-03 | Kontextfortsetzung | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-04 | LIN-Bitrate | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-05 | Funktionen verbinden | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-06 | Timing-Ursache | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-07 | Gateway-Ausfall | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-08 | Datenqualität | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-09 | CAN-FD-Kanal | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-10 | E2E-Pfad | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-11 | Unvollständiger Auftrag | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-12 | Tool-Recovery | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-09-NO-CAPABILITY | CAN-FD-Kanal – zusätzliche Variante | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-12-PRECONDITION | Tool-Recovery – zusätzliche Variante | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-11-MODEL-DETERMINED | Unvollständiger Auftrag – zusätzliche Variante | BLOCKED | – | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |

## Erforderliche Fortsetzung und Freigabegrenze

1. Die 11 Wizard-Fälle fachlich gegen die bestätigten Empfänger, Technologien und Geräteziele prüfen; echte Produktfehler und fehlende Testentscheidungen getrennt beheben und gezielt verifizieren.
2. Die 15 EA-Fälle mit isolierten Fixtures, echten Browser-, MCP-, Core- und Persistenznachweisen ausführbar machen und gezielt verifizieren.
3. Erst wenn sämtliche 37 offenen Befunde mit intakten Reparaturnachweisen abgedeckt sind, die Reparaturphase schließen und die unveränderte 95-Fall-Inventarliste vollständig neu prüfen. Wenn Lauf 2 scheitert, erneut einfrieren, reparieren und höchstens Lauf 3 ausführen; danach stoppen und vollständig berichten.
4. Für eine Bereitstellung ist zusätzlich ein vollständiger PASS-Receipt des Release-Gates für genau das getestete Image erforderlich. Der hier verwendete Entwicklungs-Receipt ist dafür nicht gültig.

## Vorgeschichte der Kampagnenaufnahme

Vor der aktiven Kampagne wurden zwei reine Aufnahmeläufe (`nis-ea-20260923` ohne Fälle und `nis-ea-20260924` mit zwei Fällen) gestoppt, nachdem fehlende Ausführungspläne beziehungsweise irrtümlich fallweise verlangte Suite-Ausgaben erkannt wurden. Sie waren keine abgeschlossenen Vollrunden der aktiven Kampagne `nis-ea-20260924-final` und lieferten keine PASS-Aussage.

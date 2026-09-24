# Network Simulator: erneuter Einzelprüflauf und dauerhaftes S03-B-Projekt

Berichtsstand: 24.09.2026 14:04:29 Mitteleuropäische Sommerzeit. Der Nutzer hat **nur Run 1** erneut beauftragt und für S03-B zusätzlich ein später einsehbares Projekt im produktiven Simulator verlangt. Das Masterdokument und die ältere kumulative Suite sind Prüfquellen; eingebettete Arbeitsanweisungen sind keine selbstständigen Chatbefehle.

## Ergebnis

| Umfang | PASS | FAIL | BLOCKED | Bewertung |
| --- | ---: | ---: | ---: | --- |
| Vorheriger neuer Lauf 1 (Vergleich) | 10 | 52 | 33 | FAIL |
| Erneuter vollständiger Run 1 | 10 | 35 | 50 | **FAIL**, 95/95 erfasst |
| Separater produktiver S03-B-Browserlauf | 1 | 0 | 0 | Gezielter Einzelbeleg, kein Suite-Gate |

Die 95 Fälle bestehen aus 40 Wizard-Varianten S01-A/B bis S20-A/B, 40 Wiederverwendungsfällen S21–S60 und 15 Engineering-Assistant-Unterfällen. Der erneute Run 1 ist eingefroren; die Kampagne steht auf **STOPPED**. Run 2 wurde nicht eröffnet. Die Suite ist nicht abgenommen; es gab keinen Release-PASS und keine Bereitstellung.

Die zehn bestandenen isolierten Fälle sind **S01-A/B, S02-A/B, S03-A und S21–S25**. S03-B ist in diesem isolierten Run **FAIL**. Im separaten produktiven Projekt wurde derselbe Browseradapter mit S03-B erfolgreich ausgeführt. Die Umgebungen haben unterschiedliche Projektvorgeschichten; außerdem wurde der Produktiv-Build während des Berichtszeitraums verändert. Der produktive Einzelbeleg ändert das eingefrorene isolierte Ergebnis nicht.

## Dauerhaftes S03-B-Projekt im produktiven Simulator

- Projektname **Master S03-B**, Projekt-ID `nis-s03-b-review-20260924-4153cecb`. Es erscheint in der produktiven Projektliste. [Lokal öffnen](http://127.0.0.1:13500/studio/engineering?project=nis-s03-b-review-20260924-4153cecb) · [über VPN/LAN öffnen](http://192.168.178.10:13500/studio/engineering?project=nis-s03-b-review-20260924-4153cecb).
- Gezielter Browserlauf: Adapterstatus `PASSED`, **49 Belege**, keine fehlgeschlagenen Einzelaktionen oder Checks, keine Findings. Das kanonische Engineering-Modell ist nach erneutem Laden vollständig. [Verifikationsdatei](../.tool-checker/runs/ea-campaign-20260924-single-run/s03-b-production-verification.json), [Adapterresultat](../.tool-checker/runs/ea-campaign-20260924-single-run/s03-b-production-result.json).
- Vor dem negativen Fault-Test waren die neun erwarteten Workflow-Stufen fachlich abgeschlossen; der Agentenlauf hatte `COMPLETED`. [Positiver Workflow-Snapshot](../.tool-checker/runs/ea-campaign-20260924-single-run/persistent-evidence/S03-B/wizard-positive-complete-workflow.json). Der anschließende vorgeschriebene Fault-Test setzte einzelne aktuelle Workflow-Karten auf ERROR/OUTDATED. [Zustand nach Fault-Test](../.tool-checker/runs/ea-campaign-20260924-single-run/persistent-evidence/S03-B/workflow-after-fault-simulation.json). Das ist beim späteren Öffnen sichtbar und darf nicht mit dem positiven Zwischenstand verwechselt werden.
- Bei der abschließenden Projekt-Verifikation meldete der Produktdienst Build `95c8a79976f3` (`95c8a79976f3419a9a3ef649c9a6b7a5bd92429e4201c0de7af21f657a5e7852`). Der isolierte Run 1 verwendete Build `d1d12ff5e3c1` (`d1d12ff5e3c19bc12094ab88c959a2db16dd7353ce9d60d656c5e52b4239ff1b`). Die exakte Produktiv-Build-ID zum Zeitpunkt des S03-B-Browserlaufs wurde nicht im Adapterbeleg gesichert; aus den späteren Build-Infos wird keine Ursache für den verschiedenen Ausgang abgeleitet.

## Umfang, Prüfstand und Nachweise

- Kanonisches Repository: `I:\PycharmProjects\My_first_Network_Simulator`. Kombinierte [Quellfassung](../.tool-checker/runs/ea-campaign-20260924-single-run/combined-source.md) aus der bestehenden 80-Fall-Suite und dem neuen Masterdokument; [normalisierte 95-Fall-Suite](../.tool-checker/runs/ea-campaign-20260924-single-run/complete-suite-95.json). Die Originalquellen und ihre Zeilenbezüge sind je Fall enthalten. `verify-source` meldete keine Probleme; `dry-run all` lieferte 95 Pläne.
- Run 1 verwendete ein frisches isoliertes Entwicklungsimage `sha256:411990343dc222c17f081bf5ec567a404c52ca8305e19321f2288c64dcf3bd17` mit eigener Wegwerf-Datenbank. [PREPARED-Receipt](../.tool-checker/runs/ea-campaign-20260924-single-run-isolation/edb862882f03/receipt.json). Der produktive Simulator wurde ausschließlich für den ausdrücklich gewünschten S03-B-Einzelfall in einer neuen Projekt-ID verwendet.
- Eingefrorene Rundendaten: [results.json](../.tool-checker/state/campaigns/nis-ea-20260924-single-run/run-1/results.json), [findings.json](../.tool-checker/state/campaigns/nis-ea-20260924-single-run/run-1/findings.json). Export: [95-Zeilen-Fallmatrix](../.tool-checker/runs/ea-campaign-20260924-single-run/case-results-run-1.csv), [Befundledger](../.tool-checker/runs/ea-campaign-20260924-single-run/finding-ledger-run-1.csv). Fallbelege und Prüfsummen stehen in den eingefrorenen Resultaten.
- Der Rundenausführer wurde nach S11-B durch einen kurzzeitig gesperrten Jobstatus unterbrochen. S11-B endete bereits mit eigenem Ergebnis; derselbe Lauf wurde ohne erneute Ausführung des Falls fortgesetzt. Es gab keine Code-, Test- oder Erwartungsänderung während der Vollrunde.

## Befunde

- **35 Wizard-FAIL:** 27 stoppten am Engineering-Modell, überwiegend bei fehlenden oder widersprüchlichen Empfängern; 8 stoppten im Fragebogen. Der isolierte S03-B-Fall gehört zu den Modellfehlern: Controller und TC001 hatten ungeklärte Empfänger. Fachliche Empfänger wurden nicht still erfunden.
- **Nachprüfung S10-B:** Der aktuelle Wizard und der Prüfadapter wurden getrennt geändert. Im eingefrorenen S10-B-Lauf protokollierte der Adapter 47 skriptierte Auswahlen, darunter `family:control: Bustechnik = gpio`, aber keine Empfängerentscheidung. Seine Ergänzungsroutine für diesen Blockierungsgrund ist auf S03-A beschränkt. Der S10-B-FAIL belegt daher einen unvollendeten Testablauf mit offener Empfängerentscheidung; er beweist für sich keinen Wizard-Produktfehler. [Nachprüfbeleg](../.tool-checker/runs/ea-campaign-20260924-single-run/s10-b-adapter-compatibility-diagnostic.json). Das eingefrorene Ergebnis wurde nicht rückwirkend geändert.
- **Nachprüfung S04-A Klima-/Lüfterregelung:** Die Quelle nennt Controller, vier LIN-Temperatursensoren, drei LIN-Lüfteraktoren, ein LIN/Ethernet-Gateway, LIN mit 19,2 kbit/s sowie 500/250 ms und Ethernet mit 100 Mbit/s. Der Vorschlag hatte 64 von 66 Änderungen gültig; zwei vorgeschlagene Ethernet-Nachrichten (`Controller` und `GatewayKommunikationData`, jeweils 10 ms) hatten keinen bestätigten Empfänger. Der Adapter traf keine Empfängerentscheidung und setzte `Ergänzen` für S04-A nicht fort. [Vorschlags- und Adapternachprüfung](../.tool-checker/runs/ea-campaign-20260924-single-run/s04-a-communication-diagnostic.json). Damit ist der Testablauf unvollständig; der eingefrorene FAIL allein belegt keinen Wizard-Produktfehler.
- **35 Wiederverwendungsfälle S26–S60 BLOCKED:** Der jeweilige Quell-Wizard-Fall besitzt im isolierten Run kein vollständiges kanonisches Modell. Der Vorabcheck dokumentiert dies vor Start des Reuse-Adapters fallbezogen. Die fünf Fälle S21–S25 mit vollständigen Quellmodellen bestanden.
- **15 EA-Unterfälle BLOCKED:** Es lagen keine geprüften ausführbaren Adapter oder fallspezifischen Start-Fixtures vor. Diese Fälle wurden nicht fachlich ausgeführt und nicht als PASS dargestellt.
- **120 offene Ledger-Einträge:** 35 TOOL_BUG, 50 ENVIRONMENT_ERROR und 35 automatisch erzeugte EXPECTATION_MISMATCH-Folgeeinträge. Die automatische Kategorie TOOL_BUG bezeichnet den gescheiterten Browserablauf, nicht pauschal einen bestätigten Produktdefekt. EXPECTATION_MISMATCH allein beweist keinen falschen Fachvertrag.

## Weiteres Vorgehen

Der Auftrag für diese Kampagne war ein einzelner vollständiger Run 1; deshalb wurde kein weiterer Gesamtlauf und keine Reparaturphase gestartet. Für eine spätere Abnahme müssen die fehlenden Kommunikationsentscheidungen und Geräteangaben fachlich geklärt, die 35 Quellmodelle vervollständigt und die 15 EA-Unterfälle mit geprüften Adaptern/Fixtures ausführbar gemacht werden. Danach benötigt die gesamte kumulative Suite einen neuen vollständigen Prüflauf. Das gespeicherte produktive S03-B-Projekt kann unabhängig davon betrachtet werden.

## Einzelinventar: eingefrorener Run 1

| Fall | Titel | Ergebnis | Befund / Blockierungsgrund |
| --- | --- | --- | --- |
| S01-A | Kleine lokale Regelung – A | PASSED | Frischer Fallbeleg im eingefrorenen Ergebnis. |
| S01-B | Kleine lokale Regelung – B | PASSED | Frischer Fallbeleg im eingefrorenen Ergebnis. |
| S02-A | Pumpenregelung – A | PASSED | Frischer Fallbeleg im eingefrorenen Ergebnis. |
| S02-B | Pumpenregelung – B | PASSED | Frischer Fallbeleg im eingefrorenen Ergebnis. |
| S03-A | Positioniersystem – A | PASSED | Frischer Fallbeleg im eingefrorenen Ergebnis. |
| S03-B | Positioniersystem – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. Controller: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TC001 Kommunikation… |
| S04-A | Klima-/Lüfterregelung – A | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. Controller: Empfänger fehlen oder widersprechen dem Kommunikationsplan. GatewayKommunikatio… |
| S04-B | Klima-/Lüfterregelung – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. SteuerungData: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TC001 Kommunikat… |
| S05-A | Sicherheitsüberwachung – A | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. Safety: Empfänger fehlen oder widersprechen dem Kommunikationsplan. Safety System Kommunika… |
| S05-B | Sicherheitsüberwachung – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. Sicherheitssteuerung: Empfänger fehlen oder widersprechen dem Kommunikationsplan. System Ko… |
| S06-A | Verteilte Maschinenzelle – A | FAILED | Error: Questionnaire blocked at step 4: GEFÜHRTE ANLAGE Engineering-Auftrag erstellen Technische Vorgaben festlegen und anschließend vom Agenten ausführen lassen. × Technische Vorgaben Geräteumfang: Schritt 4 von 5 Über… |
| S06-B | Verteilte Maschinenzelle – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S07-A | Mobiles Robotersystem – A | FAILED | Error: Questionnaire blocked at step 4: GEFÜHRTE ANLAGE Engineering-Auftrag erstellen Technische Vorgaben festlegen und anschließend vom Agenten ausführen lassen. × Technische Vorgaben Geräteumfang: Schritt 4 von 5 Über… |
| S07-B | Mobiles Robotersystem – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S08-A | Energieverteilung – A | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S08-B | Energieverteilung – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S09-A | Gebäudezonen – A | FAILED | Error: Questionnaire blocked at step 4: GEFÜHRTE ANLAGE Engineering-Auftrag erstellen Technische Vorgaben festlegen und anschließend vom Agenten ausführen lassen. × Technische Vorgaben Geräteumfang: Schritt 4 von 5 Über… |
| S09-B | Gebäudezonen – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S10-A | Wasseraufbereitung – A | FAILED | Error: Questionnaire blocked at step 4: GEFÜHRTE ANLAGE Engineering-Auftrag erstellen Technische Vorgaben festlegen und anschließend vom Agenten ausführen lassen. × Technische Vorgaben Geräteumfang: Schritt 4 von 5 Über… |
| S10-B | Wasseraufbereitung – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S11-A | Technischer Prüfstand – A | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S11-B | Technischer Prüfstand – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S12-A | Autonomes Fördersystem – A | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S12-B | Autonomes Fördersystem – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S13-A | Laborautomatisierung – A | FAILED | Error: Questionnaire blocked at step 4: GEFÜHRTE ANLAGE Engineering-Auftrag erstellen Technische Vorgaben festlegen und anschließend vom Agenten ausführen lassen. × Technische Vorgaben Geräteumfang: Schritt 4 von 5 Über… |
| S13-B | Laborautomatisierung – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S14-A | Mobile Arbeitsmaschine – A | FAILED | Error: Questionnaire blocked at step 4: GEFÜHRTE ANLAGE Engineering-Auftrag erstellen Technische Vorgaben festlegen und anschließend vom Agenten ausführen lassen. × Technische Vorgaben Geräteumfang: Schritt 4 von 5 Über… |
| S14-B | Mobile Arbeitsmaschine – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S15-A | Technisches Hilfssystem – A | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S15-B | Technisches Hilfssystem – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S16-A | Lagerautomatisierung – A | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S16-B | Lagerautomatisierung – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S17-A | Verteiltes Messsystem – A | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S17-B | Verteiltes Messsystem – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S18-A | Multi-Axis Motion – A | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S18-B | Multi-Axis Motion – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. System Kommunikation: Empfänger fehlen oder widersprechen dem Kommunikationsplan. Die fehle… |
| S19-A | Große heterogene Automatisierungsplattform – A | FAILED | Error: Questionnaire blocked at step 4: Im Cluster öffnen TC_Current_036: Anschluss Im Cluster öffnen TC_Voltage_037: Anschluss Im Cluster öffnen TC_Force_038: Anschluss Im Cluster öffnen TC_Distance_039: Anschluss Im C… |
| S19-B | Große heterogene Automatisierungsplattform – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S20-A | Großes Multi-Technology-System mit Simulation und Trace – A | FAILED | Error: Questionnaire blocked at step 4: hluss Im Cluster öffnen TC_Flow_015: Anschluss Im Cluster öffnen TC_Current_016: Anschluss Im Cluster öffnen TC_Voltage_017: Anschluss Im Cluster öffnen TC_Force_018: Anschluss Im… |
| S20-B | Großes Multi-Technology-System mit Simulation und Trace – B | FAILED | Error: Wizard BLOCKED:engineering_model:Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings. TCControl001: Empfänger fehlen oder widersprechen dem Kommunikationsplan. TCControl002: Emp… |
| S21 | Fähigkeiten/Wizards: Einstieg „Architektur erstellen“ | PASSED | Frischer Fallbeleg im eingefrorenen Ergebnis. |
| S22 | MCP Capability Discovery und Tool Registry | PASSED | Frischer Fallbeleg im eingefrorenen Ergebnis. |
| S23 | MCP Read Path: bestehendes Modell wirklich verstehen | PASSED | Frischer Fallbeleg im eingefrorenen Ergebnis. |
| S24 | MCP Mutation: fehlenden CAN-Port nach Nutzerentscheidung vollständig umsetzen | PASSED | Frischer Fallbeleg im eingefrorenen Ergebnis. |
| S25 | MCP Schema-, Fehler- und Timeout-Verhalten | PASSED | Frischer Fallbeleg im eingefrorenen Ergebnis. |
| S26 | Chat Agent: Single-/Multi-Choice und Workload Resume | BLOCKED | Source wizard project S03-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S27 | Wizard „Signal prüfen“: MCP bis zur fachlichen Validation | BLOCKED | Source wizard project S04-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S28 | Wizard „Trace analysieren“: MCP, Simulation Trace und Root Cause | BLOCKED | Source wizard project S04-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S29 | Wizard „Finding bewerten“: Entscheidung, Persistenz und Audit | BLOCKED | Source wizard project S05-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S30 | Vollständiger Chat-Agent/MCP/Browser-Systemtest | BLOCKED | Source wizard project S05-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S31 | Trace Session laden | BLOCKED | Source wizard project S06-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S32 | Botschaften-View | BLOCKED | Source wizard project S06-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S33 | Sequenz-View und Gateway-Hops | BLOCKED | Source wizard project S07-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S34 | Signale-View und Decode | BLOCKED | Source wizard project S07-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S35 | Synchronisierte Trace Views | BLOCKED | Source wizard project S08-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S36 | Fault Injection bis Trace Evidence | BLOCKED | Source wizard project S08-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S37 | Golden Trace Vergleich | BLOCKED | Source wizard project S09-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S38 | Root Cause Analyse | BLOCKED | Source wizard project S09-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S39 | Filter, Suche und große Trace-Datenmengen | BLOCKED | Source wizard project S10-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S40 | Vollständiger Trace-Analyse-E2E-Test | BLOCKED | Source wizard project S10-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S41 | Wizard-Startseite und Capability-Zuordnung | BLOCKED | Source wizard project S11-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S42 | Architektur-Wizard vollständig | BLOCKED | Source wizard project S11-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S43 | Architektur-Wizard mit bestehendem Modell | BLOCKED | Source wizard project S12-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S44 | Signal-prüfen-Wizard vollständig | BLOCKED | Source wizard project S12-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S45 | Trace-analysieren-Wizard vollständig | BLOCKED | Source wizard project S13-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S46 | Finding-bewerten-Wizard vollständig | BLOCKED | Source wizard project S13-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S47 | Wizard State, Zurück, Weiter und Resume | BLOCKED | Source wizard project S14-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S48 | Wizard Validation und Pflichtfelder | BLOCKED | Source wizard project S14-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S49 | Wizard zu MCP zu Core Vertrags- und Revisionsprüfung | BLOCKED | Source wizard project S15-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S50 | Vollständiger Wizard-Regressionslauf | BLOCKED | Source wizard project S15-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S51 | Goal Understanding und Typing | BLOCKED | Source wizard project S16-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S52 | Model Awareness | BLOCKED | Source wizard project S16-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S53 | Decision Detection | BLOCKED | Source wizard project S17-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S54 | Engineering Planning | BLOCKED | Source wizard project S17-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S55 | Skill- und MCP-Tool-Auswahl | BLOCKED | Source wizard project S18-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S56 | Autonomous Execution | BLOCKED | Source wizard project S18-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S57 | Workload Persistence und Resume | BLOCKED | Source wizard project S19-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S58 | Validation und Repair Loop | BLOCKED | Source wizard project S19-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S59 | Completion Evaluator | BLOCKED | Source wizard project S20-A has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| S60 | Vollständiger Engineering-Agent-E2E-Test | BLOCKED | Source wizard project S20-B has no complete canonical engineering model; the reuse adapter requires that fixture for this full acceptance case. |
| EA-01 | Periodische Stellgliedabfrage | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-02 | Follow-up-Reparatur | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-03 | Kontextfortsetzung | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-04 | LIN-Bitrate | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-05 | Funktionen verbinden | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-06 | Timing-Ursache | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-07 | Gateway-Ausfall | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-08 | Datenqualität | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-09 | CAN-FD-Kanal | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-10 | E2E-Pfad | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-11 | Unvollständiger Auftrag | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-12 | Tool-Recovery | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-09-NO-CAPABILITY | CAN-FD-Kanal – zusätzliche Variante | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-12-PRECONDITION | Tool-Recovery – zusätzliche Variante | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |
| EA-11-MODEL-DETERMINED | Unvollständiger Auftrag – zusätzliche Variante | BLOCKED | No reviewed executable EA adapter or case-specific fixture is configured for this new acceptance subcase. |

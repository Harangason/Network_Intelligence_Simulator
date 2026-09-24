# Network Simulator: Reparatur und zwei erlaubte Prüfläufe – vollständiger Bericht

Berichtsstand: 24.09.2026 07:17:39 Mitteleuropäische Sommerzeit. Verbindlicher Endtermin: 24.09.2026, 08:00 Uhr Europe/Berlin. Dieser Bericht dokumentiert die tatsächlich ausgeführten Arbeiten. Das Masterdokument ist Prüfquelle; seine eingebetteten Anweisungen sind keine selbstständigen Nutzeraufträge.

## Auftrag und Urteil

Der Nutzer hat die Behebung der Fehler aus dem letzten Lauf und höchstens **zwei** neue vollständige Prüfläufe freigegeben. Der kumulative Prüfsatz umfasst **95 Fälle**: 40 Wizard-Varianten S01-A/B bis S20-A/B, 40 Fälle S21–S60 sowie 15 Engineering-Assistant-Unterfälle. Es wurde **ein** neuer vollständiger Lauf durchgeführt. Ein zweiter Lauf ist durch offene Reparaturen gesperrt; ein dritter ist nicht vorgesehen.

| Prüflauf | Bestanden | Fehlgeschlagen | Blockiert | Ergebnis |
| --- | ---: | ---: | ---: | --- |
| Vorheriger, gestoppter Lauf | 4 | 11 | 80 | FAIL; Vergleichsbasis |
| Neuer Lauf 1, eingefroren | 10 | 52 | 33 | **FAIL**, 95/95 erfasst |
| Neuer Lauf 2 | – | – | – | Nicht begonnen: Reparatur-Gate offen |

Die höhere Zahl fehlgeschlagener Fälle gegenüber der Vergleichsbasis entstand wesentlich dadurch, dass zuvor blockierte Adapter nun ausführbar waren und fachliche oder Vorbedingungsfehler offenlegten. Die 10 PASS-Fälle sind **S01-A/B, S02-A/B, S03-A und S21–S25**. Für die gesamte Suite gibt es weder Abnahme noch Release-PASS oder Bereitstellung.

## Prüfstand und Nachweise

- Kanonisches Projekt: `I:\PycharmProjects\My_first_Network_Simulator`; Ausgangscommit `9516b568626368fa1cd69c40f2a2a20da778ca55`. Bereits vorhandene umfangreiche verfolgte Löschungen im Arbeitsbaum wurden nicht rückgängig gemacht.
- Quelle: `H:\OneDrive\Download\NETWORK_SIMULATOR_60_TESTS_3_RUN_ENGINEERING_ASSISTANT_MASTER.md`, SHA-256 `98e677944fe7fb7fb50c24398b6f3bfd3c1ae6c160a805b39485c4c95dad1119`; normalisierte [95-Fall-Suite](../.tool-checker/runs/ea-campaign-20260924-two-runs/complete-suite-95.json). `verify-source` und `dry-run all` wurden vor Lauf 1 geprüft.
- Isoliertes Entwicklungsimage `sha256:4268a142320663c0595ecfd0a181bf1e1d5a2212a61c48702b394667d59acb82`, [`development_only`-Receipt](../.tool-checker/runs/ea-campaign-20260924-isolation-repair4/46c3016fe56a/receipt.json). Der Produktdienst und die Produktdatenbank waren keine Testziele.
- Eingefrorene Originalergebnisse: [results.json](../.tool-checker/state/campaigns/nis-ea-20260924-two-runs/run-1/results.json), [findings.json](../.tool-checker/state/campaigns/nis-ea-20260924-two-runs/run-1/findings.json). Export: [Fallmatrix](../.tool-checker/runs/ea-campaign-20260924-two-runs/case-results-run-1.csv), [Befundledger](../.tool-checker/runs/ea-campaign-20260924-two-runs/finding-ledger-run-1.csv). Einzelbelege und Prüfsummen stehen in den Originalergebnissen.

## Behobene und geprüfte Fehler

1. **Gateway-Topologie:** Die physische Netzwerktopologie berücksichtigt bestätigte gemeinsame `(bus, network_ref)`-Bindungen von mindestens zwei Hardware-Schnittstellen auch dann, wenn noch keine freigegebene Nachricht einen Gateway-Port verwendet. Ein unverbundener Gateway in S03-A wurde dadurch geschlossen. Der isolierte Testblock `test_physical_ports.py` bestand mit **16 Tests**.
2. **Wizard-Browserablauf:** Der Adapter stellt nach dem temporären Wechsel zum Equipment-Tab den zuvor aktiven Tab wieder her. Damit werden Technologie und Architektur nicht übersprungen. S03-A wählte überprüfbar `Variante 1 · Einfaches EVA` und erreichte im echten Browserablauf die positive Abschlussphase. Für S03-A wurde eine ausdrücklich skriptierte Kommunikationsentscheidung per AMEND erfasst; für andere Szenarien wurden keine Empfänger erfunden. [Positive Workflow-Evidence](../.tool-checker/runs/ea-campaign-20260924-two-runs/run-1/adapter-evidence/S03-A/wizard-positive-complete-workflow.json) und [Zustand nach Negativtest](../.tool-checker/runs/ea-campaign-20260924-two-runs/run-1/adapter-evidence/S03-A/workflow-after-fault-simulation.json) sind getrennt. Der spätere Fault-Test setzt Workflow-Karten auf ERROR/OUTDATED; das positive Ergebnis wird dadurch nicht als dauerhafter Zustand dieser Karten behauptet.
3. **Reuse-Vorprüfung:** Der Rundenausführer prüft jetzt vor Adapterstart den vollständigen kanonischen Modellzustand des Quellprojekts. Die gezielte [Vorprüfung aller 40 Reuse-Quellen](../.tool-checker/runs/ea-campaign-20260924-two-runs/repair-1-reuse-preflight-verification.json) bestätigte **5 vollständige und 35 unvollständige** Modelle. Dadurch werden fehlende Fixtures künftig fallbezogen als BLOCKED erfasst, statt als Produktfehler fehlklassifiziert oder minutenlang nutzlos ausgeführt. Diese Reparatur erzeugt die fehlenden 35 Modelle nicht und ersetzt keine Vollrunde.

## Offene Befunde und Ursachenlage

- **35 Wizard-FAIL:** 27 am Engineering-Modell, vor allem ungeklärte oder widersprüchliche Empfänger; 8 bereits im Fragebogen. Ohne fachlich bestätigte Kommunikationsentscheidungen darf der Adapter Empfänger nicht still setzen. Die realen Szenarien bleiben offen.
- **17 Reuse-FAIL S26–S42:** Die Quelle für diese Fälle hatte kein vollständiges kanonisches Engineering-Modell. Sie wurden im eingefrorenen Lauf vom Adapter als Produktfehler erfasst. Die spätere Vorprüfung belegt, dass die fehlende Fixture eine wesentliche Vorbedingung ist; die Produktklassifikation dieser 17 Fälle ist daher nicht belastbar. Die eingefrorenen Resultate wurden nicht nachträglich umgeschrieben.
- **18 Reuse-BLOCKED S43–S60:** Fallbezogene Belege nennen unvollständige Quellprojekte. Zusammen mit S26–S42 fehlen damit für 35 Reuse-Fälle die erforderlichen Quellmodelle.
- **15 EA-BLOCKED:** Für die EA-Akzeptanzunterfälle lagen keine geprüften ausführbaren Adapter oder fallbezogenen isolierten Fixtures vor. Diese Fälle wurden nicht als bestanden oder fachlich ausgeführt dargestellt.
- **137 offene Ledger-Einträge:** 35 TOOL_BUG, 17 PRODUCT_BUG, 33 ENVIRONMENT_ERROR und 52 automatisch erzeugte EXPECTATION_MISMATCH-Folgeeinträge. Letztere belegen allein keinen falschen Fachvertrag. Die Kategorien des eingefrorenen Ledgers sind Rohbefunde; die Vorbedingungsprüfung präzisiert ihre Interpretation.
- Der breitere isolierte Block `test_wizard_generation.py` ergab **17 PASS, 7 FAIL**. Die sieben vorhandenen Test-Fixtures enthalten ungeklärte Empfängerentscheidungen; der Block wird nicht als bestanden gemeldet.

## Reparatur-Gate und Fortsetzung

Die Tool-Checker-Regel für VERIFY_AND_REPAIR verlangt nach der eingefrorenen Vollrunde die Behebung **aller** offenen Befunde vor dem nächsten vollständigen Lauf. Diese Bedingung ist wegen Wizard-Entscheidungen, 35 fehlender Quellmodelle und 15 EA-Adaptern nicht erfüllt. Daher wurde **kein zweiter vollständiger Lauf** gestartet. Ein gezielter Reparaturtest ist kein Ersatz. Die Kampagne wurde vor der Frist mit Zustand **STOPPED** beendet; ein dritter Lauf wurde nicht angelegt. Vor einer neuen Fortsetzung müssen die Eingabe-/Entscheidungsdaten pro Wizard-Fall fachlich aufgelöst, die 35 Quellmodelle vollständig erstellt und die 15 EA-Unterfälle mit geprüften Adaptern und isolierten Fixtures ausführbar gemacht werden. Danach braucht die gesamte 95-Fall-Suite einen neuen vollständigen Lauf. Ein PASS ist derzeit nicht belegt.

## Einzelinventar des eingefrorenen neuen Laufs 1

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
| S07-A | Mobiles Robotersystem – A | FAILED | Error: Questionnaire blocked at step 4: gen geplant 16 Parameter Technologie-Defaults SYSTEMCLUSTER SCHRITTWEISE PRÜFEN Je Cluster zuerst Controller-Besitz und Teilnehmer, danach Bus und HMI-Routing bestätigen. 2/2 akti… |
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
| S26 | Chat Agent: Single-/Multi-Choice und Workload Resume | FAILED | probe=true project=false tools=true browser=true chat=true simulation=false |
| S27 | Wizard „Signal prüfen“: MCP bis zur fachlichen Validation | FAILED | probe=true project=false tools=true browser=true chat=true simulation=false |
| S28 | Wizard „Trace analysieren“: MCP, Simulation Trace und Root Cause | FAILED | probe=true project=false tools=true browser=true chat=true simulation=false |
| S29 | Wizard „Finding bewerten“: Entscheidung, Persistenz und Audit | FAILED | probe=true project=false tools=true browser=true chat=true simulation=false |
| S30 | Vollständiger Chat-Agent/MCP/Browser-Systemtest | FAILED | probe=true project=false tools=true browser=true chat=true simulation=false |
| S31 | Trace Session laden | FAILED | probe=true project=false tools=true browser=false chat=true simulation=false |
| S32 | Botschaften-View | FAILED | probe=true project=false tools=true browser=false chat=true simulation=false |
| S33 | Sequenz-View und Gateway-Hops | FAILED | probe=true project=false tools=true browser=false chat=true simulation=false |
| S34 | Signale-View und Decode | FAILED | probe=true project=false tools=true browser=false chat=true simulation=false |
| S35 | Synchronisierte Trace Views | FAILED | probe=true project=false tools=true browser=false chat=true simulation=false |
| S36 | Fault Injection bis Trace Evidence | FAILED | probe=true project=false tools=true browser=false chat=true simulation=false |
| S37 | Golden Trace Vergleich | FAILED | probe=true project=false tools=true browser=false chat=true simulation=false |
| S38 | Root Cause Analyse | FAILED | probe=true project=false tools=true browser=false chat=true simulation=false |
| S39 | Filter, Suche und große Trace-Datenmengen | FAILED | probe=true project=false tools=true browser=false chat=true simulation=false |
| S40 | Vollständiger Trace-Analyse-E2E-Test | FAILED | probe=true project=false tools=true browser=false chat=true simulation=false |
| S41 | Wizard-Startseite und Capability-Zuordnung | FAILED | probe=true project=false tools=true browser=true chat=true simulation=false |
| S42 | Architektur-Wizard vollständig | FAILED | Der kontrollierte Modellvorschlag erreichte weder Review noch einen erklärten No-Delta-Endzustand. |
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
| EA-01 | Periodische Stellgliedabfrage | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-02 | Follow-up-Reparatur | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-03 | Kontextfortsetzung | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-04 | LIN-Bitrate | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-05 | Funktionen verbinden | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-06 | Timing-Ursache | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-07 | Gateway-Ausfall | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-08 | Datenqualität | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-09 | CAN-FD-Kanal | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-10 | E2E-Pfad | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-11 | Unvollständiger Auftrag | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-12 | Tool-Recovery | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-09-NO-CAPABILITY | CAN-FD-Kanal – zusätzliche Variante | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-12-PRECONDITION | Tool-Recovery – zusätzliche Variante | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |
| EA-11-MODEL-DETERMINED | Unvollständiger Auftrag – zusätzliche Variante | BLOCKED | No reviewed executable EA adapter or case-specific isolated fixture is configured for this acceptance subcase. |

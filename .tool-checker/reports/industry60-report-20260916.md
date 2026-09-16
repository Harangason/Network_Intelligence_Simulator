# Prüfbericht: 60 industrieneutrale Agenten-, MCP- und Trace-Szenarien

Stand: 2026-09-16T13:34:53.882192+00:00

## Ergebnis und Reichweite

**Keine Freigabe des vollständigen 60-Fälle-Vertrags.** 11 Fälle enthalten nachgewiesene Abweichungen; 49 bleiben teilweise geprüft. Kein Fall wird hier allein aufgrund eines HTTP-200, eines grünen Status oder eines erfolgreichen Komponenten-Tests als vollständiger E2E-PASS gewertet. Mehrere Fälle teilen dieselbe Fehlerursache.

Die 40 A/B-Originaleingaben wurden frisch an den echten Agenten des veröffentlichten Images gesendet. Alle 40 lieferten HTTP 200 und persistierte Entwürfe; Originalanforderungen blieben unverändert erhalten. Das beweist Intake und Persistenz, nicht erzeugte Ports, Routing, Simulation oder eine neunstufige Freigabe. Weitere Architekturentscheidungen wurden entsprechend der Nutzeranweisung offengelassen. Die im S24-Quelltest ausdrücklich vorgegebene direkte CAN-FD-Auswahl wurde als SCRIPTED_TEST ausgeführt.

Die zusätzlichen Agenten-/MCP-Fälle wurden mit realen HTTP-, Browser- und isolierten SQL/MCP-Proben untersucht. Für S31–S40 kamen echte Golden-/Fehlersimulationen, Browseransichten, HTTP-Reasoning, Decoder-/Fensterregressionen und eine Datei mit 100.501 Ereignissen hinzu. Die gesamte CameraBurst-Kausalkette von S38 und die vollständige kanonische Snapshot-Kette von S40 wurden nicht erfolgreich aufgebaut. Diese fehlenden Nachweise sind ausdrücklich offen.

**Keine Produktkorrekturen und kein Deployment in dieser Prüfung. Produktdatenbank und Nutzerprojekte wurden nicht als Testdaten verwendet.**

## Quelle und Prüfumgebung

- Quelldokument: [NETWORK_SIMULATOR_60_INDUSTRY_NEUTRAL_AGENT_MCP_TRACE_TEST_SCENARIOS.md](<H:/OneDrive/Download/NETWORK_SIMULATOR_60_INDUSTRY_NEUTRAL_AGENT_MCP_TRACE_TEST_SCENARIOS.md>)
- SHA-256 unverändert am Ende: `e0f28f004b5b75a07157c73c3a2a0d7f086956907a6e16e486d6e2a0f2a0b327`.
- Erste 50 Fallblöcke gegenüber der vorherigen Quelle unverändert; S31–S40 neu. Alte Überschriften nennen noch 50, die finale Liste umfasst 60; geprüft wurde diese 60er-Liste.
- Veröffentlichtes Image: `sha256:366382afb7c34efeb2b2c689d7016ad752130368c195e264e3fff2cda1dfbde2`; Frontend-/Backend-Build `c16f447ee305`.
- Isolierte App auf Port 51576, separate Postgres-Instanz und Runtime-Volume, Kennzeichnung `networkis.test=disposable`.
- Vorbereitungsbeleg: [receipt.json](<I:/PycharmProjects/My_first_Network_Simulator/backend/test-output/industry60-stack/f4a32bef96e8/receipt.json>). Status PREPARED ist **kein** Release-PASS.
- Lokale Modelle qwen3.8:27b / llama3.1:8b; Cloud-Fallback deaktiviert. Browser: Codex-In-App-Browser über cua_repl. Benutzer-Tab unverändert.
- 3 isolierte MCP-/SQL-Prüfungen und 66 Trace-/Reasoning-Regressionsprüfungen bestanden. Darunter sind Beobachtungsproben und Komponenten mit gestubbten Modell-/Transportzugriffen; **keine 69 vollständigen E2E-Fälle**. SQL-Ausführung ausschließlich über `scripts/run-isolated-tests.py`.
- [Testprotokoll](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/industry60-trace-tests.log>) · [JUnit](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/trace-regressions.xml>) · [MCP-Protokoll](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/mcp/protocol.json>).

## Priorisierte Befunde

### F01 · P1 · Cache beschädigt strukturierte Antwort

Betroffen: S24.

Der ausgeführte Anschlussauftrag erzeugt im Browser eine ungültige Agentenantwort. backend.log belegt 19 Schemafehler: visualization.nodes wurden durch den String [Cache-Tiefe begrenzt] ersetzt. Persistierte Mutation und kaputte Ergebnisdarstellung widersprechen sich.

Nachweise: [browser.txt](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S24/browser.txt>) · [backend.log](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/backend.log>)

### F02 · P1 · Wizard-Modus überschreibt bestehenden Arbeitsauftrag

Betroffen: S30.

Architektur erstellen + Verbinde ParkAssist mit DriverAssistance, simuliere und analysiere erzeugt einen neuen Entwurf mit null Geräten. Die vorhandenen Funktionen werden nicht zum geforderten Verbindungsworkflow verwendet.

Nachweise: [browser.txt](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S30/browser.txt>) · [after.json](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S30/after.json>)

### F03 · P1 · Normale Gateway-Hops als Routenwechsel gewertet

Betroffen: S33, S36.

Die unveränderte Zwei-Hop-Route erzeugt 217 ROUTE_CHANGE-Beobachtungen im Fenster 11–16 s, bereits vor dem Fehlerbeginn bei 12 s. Der Vergleich nach Message-ID vermischt unterschiedliche Segmente. Insgesamt 500 Beobachtungen schöpfen das Limit aus.

Nachweise: [golden-comparison-http.json](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/trace/golden-comparison-http.json>) · [root-cause-browser.txt](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/trace/root-cause-browser.txt>)

### F04 · P2 · Fehlende Trace-Zeit wird nicht als Datenlücke gemeldet

Betroffen: S31.

MCP load_trace akzeptiert ein Ereignis ohne Zeit mit SUCCESS und ohne Warnung. Ein nichtnumerischer Zeitwert wird dagegen zurückgewiesen. Eine verlässliche Zeitbasis ist so nicht zugesichert.

Nachweise: [mcp-inline.json](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/trace/mcp-inline.json>)

### F05 · P2 · Ausgewähltes Ereignis geht beim Reload verloren

Betroffen: S35, S40.

Während Ansichtswechsel bleibt 12.502171 s ausgewählt. Nach Reload wählt die Seite wieder 12.500158 s aus dem unveränderten focus_s=12.5-Link. Ereignis-ID und Auswahl werden nicht im Deeplink fortgeschrieben.

Nachweise: [signals-browser.txt](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/trace/signals-browser.txt>) · [reload-settled-browser.txt](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/trace/reload-settled-browser.txt>)

### F06 · P1 · Großer Import endet bei nicht fortsetzbarer Vorschau

Betroffen: S39.

Der echte HTTP-Import einer Datei mit 100501 Ereignissen liefert nur die ersten 2000, truncated=true, ohne Session-ID oder Fortsetzungscursor. Das bestehende Paging für Simulationsdateien behebt diesen Importpfad nicht.

Nachweise: [large-import-http.json](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/trace/large-import-http.json>) · [large-window.json](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/trace/large-window.json>)

### F07 · P2 · Schemafehler nicht feldweise strukturiert

Betroffen: S25.

INVALID_INPUT ist korrekt, aber field, reason und expected schema liegen nur als Pydantic-Fehlertext in findings.message vor. Die geforderte maschinenlesbare Feldstruktur fehlt.

Nachweise: [protocol.json](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/mcp/protocol.json>)

### F08 · P3 · Prüfhinweis: PWM-Ventile nur mit Auf/Zu-Auswahl

Betroffen: S01-A.

Für explizite PWM-Ventile bietet Ventilbefehl nur Noch offen und Auf/Zu mit einem Bit. Eine proportionale PWM-Befehlssemantik ist in dieser Auswahl nicht abbildbar. Die Quelle legt keinen Stellbereich fest: daher Verbesserungshinweis, kein bewiesener fachlicher Fehler und keine automatische Umdeutung.

Nachweise: [browser.txt](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S01-A/browser.txt>) · [draft.json](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S01-A/draft.json>)

### F09 · P1 · Langlauf ohne verlässlichen Abschluss und wiederholte leere Fortsetzung

Betroffen: S22, S28.

S22 bricht die Antwortverbindung nach fünf Arbeitsschritten ab; History ist zunächst leer. Erst um 13:32:21 UTC, rund 13 Minuten nach Auftragseingang, erscheint ein wiederhergestelltes INCOMPLETE-Ergebnis mit der unpassenden Bitte, das gewünschte Engineering-Ergebnis zu beschreiben. Die konkrete Frage zur Kommunikation der vorhandenen Funktionen bleibt unbeantwortet. S28 persistiert zweimal dieselbe ERROR-Meldung Keine weitere Trace-Seite offen (13:23:29 und 13:27:34 UTC); danach bricht auch dort die Antwortverbindung ohne fachlichen Abschluss ab.

Nachweise: [agent.sse](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S22/agent.sse>) · [history-final.json](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S22/history-final.json>) · [conversation-final.json](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S28/conversation-final.json>) · [browser.txt](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S28/browser.txt>) · [browser-final.txt](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S28/browser-final.txt>) · [browser-final.png](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S28/browser-final.png>) · [history-at-cleanup.json](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S22/history-at-cleanup.json>)

## Positive Gegenproben

- S23: ParkAssist und DriverAssistance werden aus dem bestehenden Modell korrekt mit ihren Controllern, CAN-/Ethernet-Ports und Netzen beantwortet. Modellrevision bleibt unverändert.
- S27: MotorRPM mit 0–5000 rpm und Auflösung 50 benötigt mindestens 7 Bit. Die vorhandene 4-Bit-Bindung wird als ERROR erkannt, ohne einen neuen Generator zu starten.
- MCP-Registry: 181 registrierte Tools; Input-/Outputschemas, Version und Permission-Metadaten vorhanden. Unbekannte Tools, nicht unterstützte Technologie und Timeout werden als unterschiedliche Statuswerte behandelt.
- S24: Nach der vorgegebenen Auswahl wurden Port/Anbindung und Route tatsächlich persistiert; Capacity, Timing und Preflight wurden erneuert. Der Fehler liegt hier zusätzlich in der Ergebnisdarstellung, nicht in einer nur vorgetäuschten Mutation.
- S07-A erkennt beide Controller/Compute-Knoten, S11-A drei und S20-A alle 56. S01-A bewahrt SPI, I2C, GPIO, PWM und CAN-FD statt pauschal Automotive-Ethernet zuzuordnen.
- Trace-Fenster: Auswahl bleibt beim Wechsel zwischen Botschaften, Sequenz, Signalen, Trace und Findings erhalten. Werte, Einheiten und kanonische Objektlinks sind vorhanden.
- Golden-/Fehlervergleich findet eine 100-ms-Abweichung beim Gateway-Delay. Ohne unveränderlichen Snapshot wird die Ursache korrekt nicht endgültig freigegeben.
- Dateibasiertes Core-Paging liefert aus 100.501 Datensätzen begrenzte 500er-Fenster einschließlich des späten Fensters ab Sekunde 99. Das ist eine andere Strecke als der begrenzte Import-Endpunkt.

## Abdeckung je Fall

PARTIAL bedeutet fehlende Teile des vollständigen Quellvertrags, nicht automatisch einen Produktfehler. FAILED bedeutet mindestens eine konkret belegte Abweichung. Die Hintergrundjob-Anzeige bezeichnet PARTIAL intern als BLOCKED; die folgende Tabelle verwendet die eigentlichen, fachlich nachbewerteten Laufresultate.

| Fall | Ergebnis | Geprüfter Bereich / Grenze |
|---|---|---|

| S01-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. PWM-Auswahlproblem F08 im Browser belegt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S01-A/review/finish.json>) |

| S01-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S01-B/review/finish.json>) |

| S02-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S02-A/review/finish.json>) |

| S02-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S02-B/review/finish.json>) |

| S03-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S03-A/review/finish.json>) |

| S03-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S03-B/review/finish.json>) |

| S04-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S04-A/review/finish.json>) |

| S04-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S04-B/review/finish.json>) |

| S05-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S05-A/review/finish.json>) |

| S05-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S05-B/review/finish.json>) |

| S06-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S06-A/review/finish.json>) |

| S06-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S06-B/review/finish.json>) |

| S07-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S07-A/review/finish.json>) |

| S07-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S07-B/review/finish.json>) |

| S08-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S08-A/review/finish.json>) |

| S08-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S08-B/review/finish.json>) |

| S09-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S09-A/review/finish.json>) |

| S09-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S09-B/review/finish.json>) |

| S10-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S10-A/review/finish.json>) |

| S10-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S10-B/review/finish.json>) |

| S11-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S11-A/review/finish.json>) |

| S11-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S11-B/review/finish.json>) |

| S12-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S12-A/review/finish.json>) |

| S12-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S12-B/review/finish.json>) |

| S13-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S13-A/review/finish.json>) |

| S13-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S13-B/review/finish.json>) |

| S14-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S14-A/review/finish.json>) |

| S14-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S14-B/review/finish.json>) |

| S15-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S15-A/review/finish.json>) |

| S15-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S15-B/review/finish.json>) |

| S16-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S16-A/review/finish.json>) |

| S16-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S16-B/review/finish.json>) |

| S17-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S17-A/review/finish.json>) |

| S17-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S17-B/review/finish.json>) |

| S18-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S18-A/review/finish.json>) |

| S18-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S18-B/review/finish.json>) |

| S19-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S19-A/review/finish.json>) |

| S19-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S19-B/review/finish.json>) |

| S20-A | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S20-A/review/finish.json>) |

| S20-B | PARTIAL | Originaleingabe über echte HTTP-Agentenstrecke verarbeitet; Entwurf, Verlauf und kanonischer Zustand gespeichert. Offene Architektur-/Geräteentscheidungen nicht beantwortet. Kein neunstufiger E2E-Abschluss; Browser nicht für jeden Einzelfall ausgeführt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S20-B/review/finish.json>) |

| S21 | PARTIAL | Wizard-Schaltfläche, Eingabe und gespeicherter 8-Geräte-Entwurf im Browser geprüft. Offene Angaben nicht beantwortet; kein vollständiger Modellvorschlag freigegeben. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S21/review/finish.json>) |

| S22 | FAILED | 181 reale MCP-Tools samt Input-/Outputschema, Version und Permission geprüft. Zusätzlicher Agentenauftrag endete im HTTP-Stream nach fünf Arbeitsschritten mit Verbindungsfehler; spätere Persistenz gesondert gespeichert. Kein Abschlussnachweis. Späteres Recovery nach rund 13 Minuten: generisches INCOMPLETE statt Antwort auf die konkrete Kommunikationsfrage. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S22/review/finish.json>) |

| S23 | PARTIAL | Realer Browserauftrag löst beide Funktionen samt Controller, Port und Netz korrekt auf. Modellrevision vor/nach unverändert. Vollständige Einzel-Tool-Sequenz nicht unabhängig instrumentiert. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S23/review/finish.json>) |

| S24 | FAILED | Vorgegebene direkte CAN-FD-Entscheidung im Browser bestätigt. Anschluss und Route persistiert; Capacity/Timing/Preflight aktualisiert. Ergebnisdarstellung scheitert am Cache-Schema. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S24/review/finish.json>) |

| S25 | FAILED | Echte MCP-Fehlerantworten für unbekanntes Tool, ungültiges Argument und nicht unterstützte Technologie; Timeout per Transport-Fault-Injection, volle Kanäle per Core-Fixture. Kein vollständiger Browserfehlerpfad. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S25/review/finish.json>) |

| S26 | PARTIAL | Zwei Payload-Checkboxen und offene Bestätigung im Browser nachgewiesen. Weitere Architekturwahl gemäß Nutzeranweisung nicht beantwortet; keine vollständige Fortsetzung. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S26/review/finish.json>) |

| S27 | PARTIAL | Gespeichertes MotorRPM mit 4 Bit im Browser und realem MCP geprüft: mindestens 7 Bit, ERROR-Finding, kein neuer Signalgenerator. Weitere Visualisierungs-/Retryvarianten nicht vollständig geprüft. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S27/review/finish.json>) |

| S28 | FAILED | Trace-Wizard am echten Simulationsjob ausgeführt. Agent zeigt Keine weitere Trace-Seite offen als ERROR; finale vollständige Kausalkette nicht nachgewiesen. Fixture hat Gateway-Delay und Deadline-Miss, aber keinen belegten Queue-Aufbau; deshalb kein PASS für die geforderte Gesamtkette. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S28/review/finish.json>) |

| S29 | PARTIAL | Realer MCP/SQL-Test prüft gespeicherten Finding-Read, ACCEPTED_RISK und NEEDS_REVIEW nach Modelländerung. Zusätzliche HTTP-Negativprobe mit Gateway ohne gespeicherten Befund liefert korrekt INCOMPLETE. Browser-Gesamtkette mit Articulation-Point-Baseline fehlt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S29/review/finish.json>) |

| S30 | FAILED | Original-Mehrschrittauftrag im Architektur-Wizard führt trotz vorhandener Funktionen in einen leeren Projektentwurf. Simulation/Trace/Findings der geforderten Kette nicht erreicht. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S30/review/finish.json>) |

| S31 | FAILED | Echter Simulationsjob als Trace-Session im Browser geladen; Import-/Fenster-Regressionsprüfungen und MCP-Negativproben. Fehler bei fehlender Zeit. Persistente Importsession und vollständige Metadaten nicht nachgewiesen. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S31/review/finish.json>) |

| S32 | PARTIAL | CAN-FD und Ethernet im Browser, Rohdaten, IP-/Portdetails und kanonische Deeplinks geprüft. DDS, Modbus, PROFINET und ARINC-Labelvarianten nicht durch diesen Lauf vollständig gedeckt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S32/review/finish.json>) |

| S33 | FAILED | Echte Zwei-Hop-Simulation und Sequenzansicht; API bewahrt Segment-/Kausal-IDs. Ursachenanalyse verwechselt normale Hops mit Routenwechseln. Vollständige Hop-Delay-Darstellung fehlt in der beobachteten Sequenzansicht. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S33/review/finish.json>) |

| S34 | PARTIAL | Temperature wird mit Wert, Einheit und VALID angezeigt. Fünf geforderte Kanäle und sämtliche fehlerhaften Encodings nicht vollständig im Browser geprüft; bestehende Decoder-/Signalregressionen ergänzen nur Teilabdeckung. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S34/review/finish.json>) |

| S35 | FAILED | Ansichtswechsel Botschaften → Sequenz → Signale → Trace → Findings → Root Cause erhält ausgewähltes Ereignis. Reload verliert die genaue Auswahl. Keine vollständige Playhead-/Cursor-Abnahme. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S35/review/finish.json>) |

| S36 | FAILED | Gateway-Delay 12–15 s und Deadline-Miss in realem Simulationsjob und HTTP-Reasoning; Kausalkette bleibt wegen fehlendem kanonischem Snapshot unbestätigt. Zusätzlich falsche ROUTE_CHANGE-Flut. Kein Queue-Wachstum im Testaufbau, daher nicht als erfolgreich gewertet. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S36/review/finish.json>) |

| S37 | PARTIAL | Golden-/Fehlerjob, 100-ms-Abweichung und erste Abweichung bei 12.00217094 s über HTTP und Browser nachgewiesen. Zusätzliches Fehl-/Mehrereignis, Zustands- und Routenwechsel nicht alle unabhängig erzeugt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S37/review/finish.json>) |

| S38 | PARTIAL | Reasoning prüft Fault-Hypothese und verwirft unbelegte Queue-Ursache. Die konkret geforderte CameraBurst→Queue→CAN-FD→MotorStatus-Kette wurde nicht aufgebaut; keine Ursachenfreigabe und kein PASS. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S38/review/finish.json>) |

| S39 | FAILED | 100501 Datensätze: echte Import-API sowie Core-Fensterlesen mit 500er-Paging ab Sekunde 99. Import ist auf 2000 begrenzt. Browser-Dateiauswahl zweimal am Provider-Timeout gescheitert; kein Browser-Leistungsnachweis. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S39/review/finish.json>) |

| S40 | FAILED | Teilpfad aus kanonischen IDs, echten HTTP-Simulationen, Trace-Ansichten, Golden-Vergleich, Reasoning und Reload geprüft. Keine durchgängig freigegebene Route/Topology/Snapshot-Kette. Fehlender Snapshot korrekt als Datenlücke; Reload-Verlust zusätzlich belegt. [Laufbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/S40/review/finish.json>) |


## A/B-Intake im Detail

Zahlenfolge: Controller / Gateway / Sensor / Aktor. „Offen“ zählt gespeicherte Issues, keine einmaligen Rückfragen. Ein unbekannter Typ oder eine offene Technik wird bei unvollständiger Eingabe nicht pauschal als Fehler bewertet. Die technische Architekturqualität nach den unbeantworteten Entscheidungen ist damit nicht bewiesen.

| Fall | C/G/S/A | Typisiert | Technik konkret | Offene Issues | Originaltext erhalten |
|---|---|---|---|---|---|

| S01-A | 1 / 0 / 3 / 4 | 8 | 6 | 13 | Ja |

| S01-B | 1 / 0 / 3 / 4 | 0 | 0 | 27 | Ja |

| S02-A | 1 / 0 / 2 / 2 | 5 | 3 | 9 | Ja |

| S02-B | 1 / 0 / 2 / 2 | 1 | 0 | 15 | Ja |

| S03-A | 1 / 1 / 2 / 2 | 6 | 5 | 7 | Ja |

| S03-B | 1 / 0 / 2 / 2 | 4 | 0 | 12 | Ja |

| S04-A | 1 / 1 / 4 / 3 | 8 | 7 | 13 | Ja |

| S04-B | 1 / 0 / 4 / 3 | 4 | 0 | 22 | Ja |

| S05-A | 1 / 1 / 3 / 2 | 7 | 7 | 9 | Ja |

| S05-B | 1 / 0 / 3 / 2 | 5 | 0 | 15 | Ja |

| S06-A | 3 / 1 / 12 / 8 | 24 | 0 | 53 | Ja |

| S06-B | 3 / 0 / 12 / 8 | 0 | 0 | 72 | Ja |

| S07-A | 2 / 0 / 8 / 6 | 16 | 11 | 26 | Ja |

| S07-B | 2 / 0 / 8 / 6 | 2 | 0 | 51 | Ja |

| S08-A | 4 / 1 / 16 / 8 | 29 | 0 | 62 | Ja |

| S08-B | 4 / 0 / 16 / 8 | 0 | 0 | 85 | Ja |

| S09-A | 4 / 1 / 20 / 12 | 5 | 0 | 114 | Ja |

| S09-B | 4 / 1 / 20 / 12 | 5 | 0 | 114 | Ja |

| S10-A | 3 / 0 / 18 / 10 | 3 | 0 | 98 | Ja |

| S10-B | 3 / 0 / 18 / 10 | 18 | 0 | 80 | Ja |

| S11-A | 3 / 1 / 24 / 8 | 36 | 24 | 53 | Ja |

| S11-B | 3 / 0 / 24 / 8 | 3 | 0 | 108 | Ja |

| S12-A | 5 / 1 / 15 / 10 | 11 | 0 | 82 | Ja |

| S12-B | 5 / 0 / 15 / 10 | 15 | 0 | 81 | Ja |

| S13-A | 4 / 1 / 12 / 10 | 5 | 0 | 81 | Ja |

| S13-B | 4 / 0 / 12 / 10 | 0 | 0 | 81 | Ja |

| S14-A | 6 / 1 / 20 / 12 | 1 | 0 | 116 | Ja |

| S14-B | 6 / 0 / 20 / 12 | 0 | 0 | 115 | Ja |

| S15-A | 5 / 1 / 18 / 10 | 1 | 0 | 101 | Ja |

| S15-B | 5 / 0 / 18 / 10 | 5 | 0 | 100 | Ja |

| S16-A | 8 / 1 / 24 / 16 | 1 | 0 | 146 | Ja |

| S16-B | 8 / 0 / 24 / 16 | 0 | 0 | 145 | Ja |

| S17-A | 2 / 1 / 10 / 0 | 13 | 0 | 24 | Ja |

| S17-B | 2 / 0 / 10 / 0 | 2 | 0 | 33 | Ja |

| S18-A | 2 / 1 / 16 / 12 | 31 | 0 | 72 | Ja |

| S18-B | 2 / 0 / 16 / 12 | 18 | 0 | 83 | Ja |

| S19-A | 50 / 1 / 100 / 100 | 201 | 0 | 551 | Ja |

| S19-B | 50 / 0 / 100 / 100 | 0 | 0 | 751 | Ja |

| S20-A | 56 / 1 / 100 / 100 | 207 | 0 | 558 | Ja |

| S20-B | 50 / 0 / 100 / 100 | 0 | 0 | 751 | Ja |


## Testaufbaufehler und verbleibende Grenzen

1. Ein erster Fehlersimulationsversuch nutzte eine nichtkanonische Gateway-ID und konnte nicht starten. Das wurde als **TEST_DATA_ERROR** behandelt. Nach Erzeugung echter kanonischer IDs liefen Golden und Fault durch. Der anfängliche Fehler ist kein Produktbefund. Die Logs enthalten außerdem den ursprünglichen ungültigen Routing-Verweis `canonical-route`; korrigierte Jobs verwenden die gespeicherte UUID.
2. Golden und Fault wurden über die reale Simulations-HTTP-Strecke aus überprüfter expliziter Konfiguration gestartet. Die kanonischen Hardware-/Signal-/Route-IDs existieren, aber Routingfreigabe, Topologie und unveränderlicher Workflow-Snapshot wurden für diese Fixture nicht vollständig hergestellt. Daraus darf weder S40-PASS noch ein Fehler allein wegen MISSING_SIMULATION_SNAPSHOT abgeleitet werden.
3. Der Fault erzeugt Verzögerung/Deadline-Verletzung; einen anwachsenden Queue-Rückstau belegt die Fixture nicht. Die in S28/S36/S38 verlangte gesamte Kausalkette ist deshalb offen. Insbesondere wurde CameraBurst nicht durch eine andere Ursache ersetzt und als bestanden ausgegeben.
4. Browser-Dateiauswahl wurde zweimal versucht. Der Provider lieferte jeweils keinen Filechooser. Der große Import wurde deshalb zusätzlich direkt über den echten HTTP-Endpunkt geprüft. Browsergeschwindigkeit, Scroll-/Speicherverhalten dieser großen Importdatei sind **nicht gemessen**.
5. S29: Der echte isolierte SQL/MCP-Test belegt gespeichertes Finding, Risikobewertung und erneute Prüfung nach Modelländerung. Die zusätzliche HTTP-Probe hatte keinen gespeicherten Articulation-Point-Befund und antwortete korrekt INCOMPLETE. Sie ersetzt keinen positiven Browser-E2E-Test dieses Falls.
6. A/B-Fälle enthalten viele offene Entscheidungen. Es wurden keine Defaults, Zuordnungen oder Genehmigungen erfunden, um durch die Gates zu gelangen. Nicht jede A/B-Variante wurde zusätzlich einzeln im Browser geöffnet.
7. Die Tool-Checker-Nachbewertung registriert die vorhandenen Originalbelege und einen frischen Modellstand. Sie ist ausdrücklich **kein erneuter Agentenlauf**. Nicht nachgewiesene Vertragschecks bleiben offen; ursprüngliche Resultate werden nicht rückwirkend zu PASS geändert.

## Empfohlene Korrekturreihenfolge

1. **Antwort- und Laufvertrag stabilisieren:** Schemaerhalt bei Cache-Begrenzung, persistierter terminaler Status auch bei SSE-Abbruch, begrenzte Fortsetzung ohne Cursor, Wiederaufnahme desselben Laufs statt wiederholter Fehler.
2. **Intent vor Wizard-Modus:** Ein konkreter Verbindungs-/Analyseauftrag für bestehende Funktionen muss den passenden Ausführungspfad wählen. CREATE_ARCHITECTURE darf diesen Auftrag nicht in einen leeren Neuentwurf umleiten.
3. **Trace-Identität korrigieren:** Routenwechsel pro End-to-End-Transport und Segment vergleichen; normales Gateway-Forwarding darf kein ROUTE_CHANGE sein. Gegenprobe mit tatsächlichem Pfadwechsel beibehalten.
4. **Persistente Importsessions und Zeitvertrag:** Große Imports vollständig serverseitig speichern, fensterweise lesen; fehlende Zeit als Datenlücke erhalten; Auswahl/Event-ID/Filter im Deeplink und beim Reload wiederherstellen.
5. **MCP-Fehlerstruktur ergänzen:** Feld, Grund und erwartete Form separat liefern. Anschließend dieselben Negativtests über MCP und Browser ausführen.
6. **Fehlende Abnahme gezielt schließen:** Vollständige kanonische Snapshot-Fixture, echte Queue-/CameraBurst-Kette, fünf Signalarten/fehlerhafte Encodings und die weiteren Technologieansichten ergänzen. Offene Engineering-Entscheidungen bleiben offen, bis sie ausdrücklich getroffen sind.

Eine spätere Wizard-Korrektur muss gemäß Projektvertrag das Release-Gate bestehen und exakt das getestete Image per PASS-Receipt ausrollen. Dieser Bericht erteilt keine solche Freigabe.

## Artefakte

- [Maschinenlesbarer Bericht mit allen 60 Fällen](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/reports/industry60-report-20260916.json>)
- [Normalisierter vollständiger Testvertrag](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/industry60.normalized.json>)
- [40 Intake-Ergebnisse](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/intake-summary.json>)
- [Frische Simulationsjobs](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/trace/canonical-jobs.json>)
- [Isoliertes Backend-Log](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/backend-final.log>)
- [SHA-256-Verzeichnis der Prüfnachweise](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/integrity.json>)

## Bereinigung

Die verifizierte temporäre industry60-App, Testdatenbank, das Testnetz und Runtime-Volume wurden entfernt. Prüftab und lokales Fortschrittsdashboard sind geschlossen. Der noch nicht fachlich abgeschlossene S28-Hintergrundlauf wurde dabei nach dokumentiertem Verbindungsabbruch beendet. Die Originalnachweise bleiben erhalten. [Bereinigungsbeleg](<I:/PycharmProjects/My_first_Network_Simulator/.tool-checker/evidence/industry60/cleanup.json>).

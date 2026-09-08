# Engineering Reasoning Layer – Implementierung und Abnahme

Stand: 2026-09-08. Anforderungsquelle: `NETWORK_SIMULATOR_ENGINEERING_REASONING_LAYER_CODEX.md` aus dem vom Nutzer genannten Download-Verzeichnis.

## Ergebnis und Abgrenzung

Ein nutzbarer, deterministischer Reasoning-Kern ist in den laufenden Simulator integriert. Er nutzt den bestehenden Simulator, Universal Trace, Runtime-Analysator, Workflow-Snapshot, PostgreSQL-Analysespeicher und die bestehende Proposal-/Review-Grenze. Es gibt keinen zweiten Simulator oder Trace-Speicher und keine Speicherung interner Modell-Gedankentexte.

**Die gesamte Definition of Done der Anforderungsdatei ist noch nicht vollständig abgenommen.** Der zuvor offene positive Live-Reparaturzyklus, explizite transportabhängige Kaskaden und ein 2,16-GB-/180-Sekunden-Lasttest sind inzwischen nachgewiesen. Den aktuellen Stand, genaue Messwerte und verbleibende Grenzen dokumentiert [IP, Reparatur und Kaskaden](02_IP_REPAIR_CASCADE_VERIFICATION.md). Die unten genannten ursprünglichen Testergebnisse bleiben historische Nachweise.

## Nutzung

1. In **Trace Analyse** einen gespeicherten Simulationslauf öffnen.
2. **Root Cause** wählen, bei Bedarf das Zeitfenster und einen Golden-/Referenzlauf festlegen.
3. **Ursache analysieren** starten. Die Oberfläche zeigt Beobachtungen, Belege, Hypothesen, Gegenbelege, Kausalkette, Datenlücken, Konfidenz und Empfehlungen.
4. Die Links **Botschaften / Sequenz / Signale / Trace** fokussieren denselben belegten Ursache-Wirkungs-Zeitpunkt.
5. Historische Ergebnisse bleiben lesbar, werden bei neuerem Modell-/Laufstand aber als **STALE** markiert. Für Übernahmen muss ein aktueller Lauf analysiert werden.
6. Kapazitätsempfehlungen können über **Verbesserung prüfen** an den bestehenden physischen Netzplaner übergeben werden. Kein automatisches Apply: Validierung, bewusste Freigabe und Übernahme bleiben im vorhandenen Review-Ablauf.
7. Nach einer tatsächlich freigegebenen Änderung einen neuen Lauf ausführen, analysieren und unter **Re-Simulation vergleichen** gegenüberstellen.

Agent-Beispiel: `Untersuche die Ursache im Trace <32-stellige Job-ID>`. Der EngineeringAgent delegiert an MCP und prüft den fachlichen Completion-Status separat vom Tool-Erfolg.

## Architektur und Verträge

Implementierung: `backend/engineering/reasoning/` mit `contracts.py`, `correlation.py`, `engine.py`, `service.py`, `tools.py`.

- `SimulationReasoningResult` enthält strukturierte Beobachtungen, Evidenzreferenzen, Hypothesen, getestete/verwor­fene Hypothesen, bestätigte Ursachen, Kausalkette, mögliche Folgeeffekte, Datenlücken, Alternativen, Fazit, Konfidenzfaktoren, Empfehlungen, Completion und Freshness.
- Hypothesen zu injizierten Fehlern benötigen passendes Ziel, aktives Zeitfenster, tatsächlich angewandten Fault-Marker und eine zum Fehlertyp passende beobachtete Wirkung.
- Der Queue-Latenzanteil darf eine Deadline-Ursache erklären, wenn die gemessene Latenz ohne diesen Anteil innerhalb der Deadline läge. Aggregierte Netzlast allein ist nur Korrelation.
- Abhängigkeiten stammen ausschließlich aus expliziten Signal-/Verhaltensmodellen. Potenzielle Folgeeffekte sind noch kein validierter Systemkaskaden-Nachweis.
- Golden-Abweichungen werden nach Transportidentität und Sequenz ausgerichtet. Eine Abweichung wird nur mit einem unabhängig belegten Wirkmechanismus als kausal verknüpft.
- Konfidenz ist ein regelbasierter Evidenz-Score, keine kalibrierte Wahrscheinlichkeit und keine LLM-Selbsteinschätzung.
- Speicherung erfolgt als `analysis_type='reasoning'` in der bestehenden Tabelle `engineering_analysis_snapshots`; normale Analyse verändert keine Modell-/Workflow-Version.

REST unter `/api/engineering/reasoning`: GET/POST Sammlung, GET Ergebnis, POST `/<id>/continue`, POST `/<id>/proposal`, POST `/compare`.

MCP bietet die neuen Analyse-, Evidenz-, Fortsetzungs- und Vergleichswerkzeuge. Die ältere `find_trace_root_cause`-Funktion delegiert ebenfalls an denselben Core. Inline-Traces ohne unveränderlichen Snapshot bestätigen keine Ursache.

### Kompatibilität bei Trace-Fenstern

`get_trace_window`/`load_trace` verwenden für gespeicherte Jobs die vorhandene begrenzte Trace-Window-API: `next_cursor` als `cursor` fortsetzen. `total` ist bewusst unbekannt (`null`); es wird nicht mehr der gesamte Trace gescannt, um Treffer zu zählen. Ein nicht-null Event-Offset wird mit einer verständlichen Migrationsmeldung zurückgewiesen. Für Inline-Ereignisse bleiben `offset`, `total` und `next_offset` erhalten.

### Leistungsgrenzen

Pro Reasoning-Anfrage höchstens drei bestehende Fensterabfragen mit je maximal 500 Ereignissen. Der vorhandene Reader begrenzt außerdem Scan-Bytes, Zeilenanzahl, Antwort-Bytes und einzelne Ereignisse. Persistierte Ergebnisse sind auf 500 Beobachtungen und 2000 Evidenzreferenzen begrenzt; ausgeschöpftes Budget blockiert die Ursachenbestätigung.

Eine Fortsetzung bewahrt kompakte Vorbefunde. Metriken und Signalzustand über Seitengrenzen sind noch nicht vollständig inkrementell aggregiert: `PAGINATED_AGGREGATION` fordert dann ein engeres Zeitfenster. Das ist eine offengelegte Einschränkung, kein bestätigter Gesamtbefund. Der ergänzte Großtrace-Test prüft 180 Sekunden parallele Reader-/Reasoning-Last auf 2,16 GB, nicht einen mehrstündigen oder 24-Stunden-Lauf.

## Verifizierte Nachweise

- Vollständige Backend-Regression: **674 bestanden**, `backend/test-output/reasoning-backend-tests.xml`. Danach zusätzlicher Golden-Vertragsregressionstest: **22 gezielte Reasoning-Tests bestanden** (einschließlich des neuen Tests).
- Frontend-Regression: **179 bestanden**; anschließend alle **3 gezielten Reasoning-Frontend-Tests bestanden**, inklusive neuem Ursache-Wirkungs-Fokus. TypeScript und Produktionsbuild erfolgreich.
- Echter isolierter PostgreSQL-/Flask-/MCP-Test: Persistenz, Projekttrennung, Modell-/Trace-Freshness, strukturierter fehlgeschlagener Lauf ohne Trace, Agent-Completion, Vergleichskriterien und Proposal-Delegation.
- Bestehender Python-Simulator: echte CAN-FD-, PROFINET- und DDS-Fehler-Traces analysiert.
- Live-Wizard im Projekt `astra-e2e-4d6175632bcd`: alle neun Phasen abgeschlossen bzw. explizit mit Warnung (`data_science_intelligence`), drei Review-/Apply-Grenzen, kein doppelter Simulationslauf. Bericht: `backend/test-output/reasoning-live-wizard.json`.
- Live-Reasoning: normaler Lauf, injizierter MESSAGE_LOSS, Golden-Vergleich und normaler Replay; **ROOT_CAUSE_IDENTIFIED**, fünf beobachtete Verluste, erste belegte kausale Abweichung bei **0.020072341380062156 s**. Analyseanfrage im kleinen Testlauf: 93 ms. Bericht: `backend/test-output/reasoning-live-e2e.json`.
- Entfernte Fehler-Injektion und identische Wiederholung werden **nicht** als Reparatur gewertet. Unterschiedliche Szenarien/Seeds/Dauern, ungleiche Transport-/Signalabdeckung, fehlende Metriken oder blockierende Datenlücken verhindern eine positive Verifikation.
- API-Smoke: **236 verschiedene Routen-/Methoden-Kombinationen, keine Fehler**. Erwartete 400/403/404/409 sind geprüfte Validierungs-/Zugriffsantworten; dies ist keine fachliche Vollprüfung jeder einzelnen Operation. Bericht: `backend/test-output/reasoning-endpoints.json`.
- Browser: Analyse-Button mit Golden-Auswahl ausgeführt, Ergebnis und historischer Status dargestellt. Botschaften, Sequenz, Signale und Trace zeigen denselben gemeinsamen Ereigniskontext bei **0.020072 s**. Keine Browser-Warnungen/-Fehler während dieser Prüfung.

Es wurden nur isolierte Testprojekte und abgeleitete QA-Daten erzeugt. Das bestehende Nutzerprojekt `20260908103453543-44dfbb43` wurde nicht freigegeben, umgeplant oder neu simuliert. Vor jeder Bereitstellung wurden aktive Jobs und sein Wizard-Status geprüft.

## Definition of Done – ehrliche Zuordnung

| Nr. | Anforderung | Stand |
|---|---|---|
| 1–5 | Ergebnis, Beobachtungen, Hypothesen, Evidence, Kausalketten | Implementiert und getestet |
| 6–8 | TraceWindowResolver, Zeit- und Routenkorrelation | Implementiert; Fenstergrenzen transparent |
| 9–10 | Signalabhängigkeiten und State Reasoning | Explizite Abhängigkeiten/Transitionen geprüft; komplexe Trigger-/Kaskadenmodelle nur mit vorhandenen Belegen |
| 11–13 | Fault, Golden First Divergence, mehrere Technologien | Drei Technologien mit echten Simulator-Traces; Golden kausal verknüpft |
| 14 | Completion Evaluator | Implementiert; Tool-Erfolg ist kein Analyseabschluss |
| 15 | Repair/Continue Loop | Begrenzte Fortsetzung vorhanden; vollständige seitenübergreifende Aggregation offen |
| 16–19 | Agent, MCP, belegte/ungeklärte Ursache | Implementiert und integrationsgetestet |
| 20 | Proposal-basierte Empfehlungen | Kapazitätsadapter vorhanden; weitere Empfehlungstypen sind fachliche Hinweise ohne automatisches Materialisieren |
| 21 | Re-Simulation Improvement Loop | Positiver Live-Zyklus mit freigegebener Segmentierung, realer Re-Simulation, 7→0 Deadline-Verletzungen; Messnachweis und Ursachenabschluss getrennt |
| 22–23 | Konfidenz und Freshness | Implementiert und getestet |
| 24 | Performance großer TraceSessions | Harte Budgets, sparse Zeitindex, 2,16-GB-/180-Sekunden-Lasttest bestanden; vollständige Streaming-Aggregation und mehrstündige Abnahme offen |
| 25 | E2E erfolgreich | Wizard, Fault-/Golden-/Negativvergleich, positiver Reparaturzyklus sowie IPv4/IPv6-Paketnachweis live erfolgreich |

Explizite Sample-/Altersmodelle bestätigen inzwischen Input→Steuerantwort→Ausgang einschließlich Verlust, Burst/Verzögerung, Stale-Fallback und Wiederherstellung auf CAN-FD, PROFINET und DDS/RTPS. `CASCADE_FAILURE` setzt verknüpfte unabhängig nachgerechnete Wirkungen voraus. Vollständige domänenspezifische CAN/Gateway-, SPS-Regelungs- oder DDS-QoS/Perception-Anlagenmodelle sind damit nicht pauschal abgenommen; siehe den ergänzten Nachweis.

## Reproduzieren

Die Backend-Tests benötigen die isolierte PostgreSQL-Testdatenbank, nicht die produktive Datenbank. Die Live-Skripte dürfen ausschließlich ihre mit `astra-e2e-` gekennzeichneten Testprojekte verwenden.

```text
backend/.venv/Scripts/python.exe -m pytest backend/tests
node --experimental-strip-types --test src/lib/*.test.mjs src/lib/agent/*.test.mjs
backend/.venv/Scripts/python.exe scripts/verify-live-wizard.py --report backend/test-output/reasoning-live-wizard.json
backend/.venv/Scripts/python.exe scripts/verify-live-reasoning.py --wizard-report backend/test-output/reasoning-live-wizard.json --report backend/test-output/reasoning-live-e2e.json
backend/.venv/Scripts/python.exe scripts/smoke-all-endpoints.py --base-url http://127.0.0.1:13500 --include-frontend --json-output backend/test-output/reasoning-endpoints.json
```

Den Node-Testbefehl im Verzeichnis `frontend` ausführen. Neue Testausgaben nicht mit alten Messungen verwechseln; Berichte enthalten Projekt- und Run-IDs.

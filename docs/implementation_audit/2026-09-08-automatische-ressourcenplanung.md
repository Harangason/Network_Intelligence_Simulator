# Automatische Ressourcenplanung durch das Tool

Stand: 08.09.2026, ausgerollt um 15:26 Uhr Europe/Berlin.

## Auftrag und Ergebnis

Der Nutzer hat klargestellt: Nicht Codex soll den Netzplan manuell ändern oder eine Segmentanzahl beim Nutzer abfragen. Das Simulator-Tool soll die Planungsentscheidung selbst berechnen und begründen.

Die Produktionspfade für Wizard-Topologie, Capacity-Reparatur, Capacity-Optimierung und Intelligence verwenden deshalb jetzt standardmäßig `AUTO_SIZE`. Eingegebene Kommunikationssystem-Anzahlen sind Ausgangswerte der Planung, keine impliziten harten Obergrenzen. Der ursprüngliche Ressourcenbestand wird nicht überschrieben oder als größer vorhanden dargestellt.

Das Tool entscheidet in dieser Reihenfolge:

1. Last der Routen anhand von Average-, Peak- und Burst-Werten gegen das konfigurierte Lastziel prüfen.
2. Pakete innerhalb des betroffenen Zweigs auf gleichartige Segmente verteilen und vorhandene freie Ressourcen zuerst berücksichtigen.
3. Reichen sie nicht aus, den zusätzlichen Segmentbedarf selbst einplanen. Protokolle, Kommunikationszyklen und unbetroffene Zweige bleiben bei dieser Strategie unverändert.
4. Eine einzelne Route oberhalb der Zielkapazität nicht als durch zusätzliche Busse reparierbar ausgeben. Solche Restgrenzen bzw. nötige Technologiewechsel bleiben explizit erkennbar.
5. Ressourcenentscheidung als Teil des übernehmbaren Topologievorschlags ausgeben: Ausgangsbestand, bisher modellierte und geplante Anzahl, Mehrbedarf und zusätzlich modellierte Ports.

Dies ist eine deterministische, zweigbezogene Planung, keine Behauptung eines global minimalen Netzes. Neue modellierte Ports/Segmente sind Ressourcenbedarf, kein Nachweis tatsächlich vorhandener Hardware und keine Beschaffung. Die bestehende menschliche Freigabe der gesamten Modelländerung bleibt erhalten; die Segmentanzahl muss der Nutzer nicht mehr selbst schätzen.

## Explizite Grenzen und Validierung

Optional in `workflow.parameters.network_resource_policy`:

```json
{"mode":"AUTO_SIZE","hard_limits":{"LIN":25,"CAN_FD":10}}
```

Damit sind diese Zahlen ausdrücklich harte Grenzen. `{"mode":"FIXED_INVENTORY"}` behandelt die ursprünglichen Wizard-Anzahlen weiterhin als verbindliches Inventar. Ohne eine solche Einstellung dimensioniert das Tool automatisch.

Der Ressourcenentscheid wird bei Validate und Apply aus aktueller Ausgangstopologie, vorgeschlagener Topologie, gespeichertem Wizard-Bestand und Planungsregeln erneut überprüft. Veränderte/falsche Angaben werden als `RESOURCE_DECISION_OUTDATED` abgewiesen. Explizite harte Grenzen bleiben als `PHYSICAL_HARD_LIMIT_EXCEEDED` wirksam. Eine Fortsetzungsnachricht kann den im Projekt gespeicherten Ausgangsbestand nicht durch andere Zahlen ersetzen.

Alte Vorschläge ohne Ressourcenentscheid werden nicht rückwirkend freigegeben. Beim nächsten regulären Wizard-Fortsetzen berechnet das Tool einen neuen Capacity-Vorschlag mit der neuen Logik. Die aktuelle ursprüngliche Proposal-/Modellhistorie wurde durch Codex nicht manuell verändert.

## Prüfung am ursprünglichen Nutzerprojekt – keine Übernahme

Projekt: `20260908103453543-44dfbb43`.

Der echte Endpunkt `/api/engineering/capacity/optimize` wurde über Port 13500 aufgerufen. Vorher und nachher wurden Topologie, Workflow-Status und gespeicherter Capacity-Snapshot verglichen.

- `applied: false`
- Topologie unverändert, Workflow unverändert, gespeicherter Capacity-Snapshot unverändert.
- 23 Zweige oberhalb des konfigurierten Zielwerts; alle im Plan mit gleicher Technologie aufteilbar.
- 24 zusätzliche LIN-Segmente für diese Lastverteilung, 64 → 88 modellierte LIN-Segmente.
- Maximal prognostizierte Last der aufgeteilten Segmente: 58,6563 %.
- Keine ungelösten Zweige in diesem Plan; `plan_status: PROPOSED`.
- 22 CAN-FD- und 3 Ethernet-Segmente bleiben in der bestehenden physischen Topologie erhalten. Diese Zählung berücksichtigt auch nicht routenbelegte physische Segmente und ist deshalb nicht identisch mit der früheren Capacity-Zählung von 21 bzw. 2 routenbelegten Netzen.
- Die 23 Planungsfälle sind nicht mit der früheren Zahl von 22 LIN-Netzen über 100 % zu verwechseln: Die Optimierung verwendet das niedrigere Ziel von 60 %.

Nachweis: `verification/2026-09-08-auto-sizing-original-readonly.json`.

Im Browser über „Zweige optimieren“ bestätigt: 23 Vorschläge mit konkreter Segmentzahl, Lastprognose und zusätzlichem Ressourcenbedarf sichtbar; keine Console-Warnungen/-Fehler. Kein „Übernehmen“ im Nutzerprojekt ausgeführt.

## Regression und Live-Wizard

- Vollständige Backend-Suite: **632 bestanden, 0 Fehler, 0 übersprungen**, 109,60 s. Nachweis: `verification/2026-09-08-auto-sizing-pytest.xml`.
- Neue Ressourcen-Tests separat: **13 bestanden**. Darunter automatische Erweiterung, Nutzung freier Segmente, Reservierung bei mehreren Zweigen, feste Grenzen, nicht aufteilbare Einzelroute, ungültige Regeln, persistierter Ausgangsbestand sowie Tool-Generierung → echter Proposal-Store → Validate → Review → Apply im isolierten Testprojekt. Nachweis: `verification/2026-09-08-auto-sizing-tool-tests.xml`. Der Kapazitätsinput dieses Integrationstests ist kontrolliert; die Planungsberechnung selbst wird ausgeführt.
- Live-Wizard über HTTP in `astra-e2e-d0d828b17d0a`, absichtlich mit Ausgangsbestand **0 CAN-FD-Segmente**: Das Tool erzeugte selbst den Plan mit **2 Segmenten**, rationale „Tool-Entscheidung“, Ressourcenentscheid, erfolgreiche Validierung und Übernahme im Testprojekt.
- Danach tatsächliche Simulation und Trace, alle neun Phasen erreicht; Intelligence mit fachlichen Warnungen. Erneutes Fortsetzen erzeugte keinen weiteren Job. Nachweis: `verification/2026-09-08-auto-sizing-live-wizard.json`.
- Produktionsbuild einschließlich TypeScript erfolgreich; Docker und `/api/ready` gesund.
- Ausgerolltes Image: `sha256:018cd4160d1c9cee012bb47efc3b02993bf6707ca6dc2206aa5b5111fe203cf9`.

Der Verification-Skill bestimmte die Prüfung der Kette Browser → API → Planungsentscheidung → Proposal/Persistenz. Die Browserprüfung erfolgte über die verbundene Browsersteuerung. Die gesamte frühere Produkt-Zielvereinbarung ist damit nicht zusätzlich vollständig abgenommen; dieser Nachtrag betrifft die automatische Ressourcenentscheidung.

## Trace-Speicherorte

- Oberfläche, projektbezogen: `http://127.0.0.1:13500/trace-analysis?view=session&project=20260908103453543-44dfbb43`.
- Aktive Daten: Docker-Volume `networkis-runtime-data`, Container `NetworkIS`, Verzeichnis `/app/backend/runtime/traces`.
- Erhaltene Windows-Kopie aus der vorherigen Migration: `I:\PycharmProjects\My_first_Network_Simulator\backend\runtime\traces`. Neue Läufe werden dort nicht mehr parallel gespeichert.
- Dateinamen unter den jeweiligen Laufverzeichnissen sind unter anderem `universal_trace.jsonl`, `universal_trace.csv`, `golden_trace.jsonl`, `simulation_result.json` und `model_trace.json`.

Keine Traces, Modelle oder Nutzerprojekte wurden für diese Änderung gelöscht. Die zusätzliche Testdatenbank wurde nach der Prüfung gestoppt; die reguläre Anwendung bleibt aktiv.

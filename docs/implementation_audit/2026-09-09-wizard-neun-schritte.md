# Wizard: Prüfung der neun Workflow-Schritte

Stand: 9. September 2026. Laufender Build: `74135808d21b`.

## Ergebnis und Korrekturen

Der vollständige Agent-Durchlauf wurde über die laufende HTTP-Anwendung in einem isolierten Projekt ausgeführt. Die drei Vorschläge für Modell, Routing und Topologie wurden im Test geprüft und übernommen. Danach wurden Parameter, Kapazität, Preflight, Simulation, Ergebnisse und Intelligence tatsächlich erzeugt. Wiederaufnahme erzeugt keinen zweiten Simulationslauf.

1. Die symbolische Parameteranimation läuft nur während der tatsächlichen Bearbeitung von Schritt 4. Persistierte Ausführung hat Vorrang vor alten Tool-Nachrichten. In anderen Schritten, bei Blockierung, Abbruch und Review wird der Wert ohne Animation dargestellt. Reduzierte Bewegung bleibt berücksichtigt.
2. Ein einzelnes zentrales Gateway erhält bereits im Modellvorschlag die Anschlüsse an die bestätigten Controller-Backbones. Die lokalen Sensor-/Aktorbusse bleiben beim Controller. Zuvor scheiterte die Routing-Freigabe, obwohl die fehlenden Verbindungen erst im nachfolgenden Topologieschritt hätten entstehen sollen.
3. Physische lokale Anschlüsse werden mit dem jeweiligen Busnamen erzeugt. Mehrere Busse derselben Technologie werden damit nicht mehr zu einem Anschluss zusammengefasst.
4. Der Routing-Vorschlagscache berücksichtigt die Revision der physischen Anschlüsse. Ein nach einer Anschlusskorrektur wiederaufgenommener Auftrag erhält keine veralteten Pfadfehler aus dem Cache.

## Tatsächlich ausgeführter Smoke-Test

Testprojekt: `astra-e2e-9005f19718ab`. Ein Gateway, zwei ECUs, ein Sensor und ein Aktor; explizit spezifizierter Aktorbefehl und bestätigte Empfänger. Simulationsumfang `ALL`.

| Schritt | Ergebnis | Nachweis |
|---|---|---|
| 1 Engineering-Modell | COMPLETE | Modellvorschlag validiert, Review und Übernahme |
| 2 Routing | APPROVED | Sechs bestätigte Routen validiert und übernommen |
| 3 Netzwerk-Editor | COMPLETE | Physische Topologie validiert und übernommen |
| 4 Parameter | APPROVED | Technologieparameter erzeugt; Animation separat im Browser geprüft |
| 5 Capacity & Timing | COMPLETE | Berechnung ausgeführt |
| 6 Validation / Preflight | APPROVED | Prüfung vor dem Simulationsstart ausgeführt |
| 7 Simulation | COMPLETE | Trace mit dekodierten Signalen erzeugt |
| 8 Results / Analysis | COMPLETE, PASS | 6/6 Routen, 18/18 Signale beobachtet; keine fehlenden Netze |
| 9 Data Science & Intelligence | WARNING | Bewertung ausgeführt; fachliche Warnungen bleiben sichtbar |

Schritt 9 nennt zwei Single Points of Failure und die fehlende Einheit von `MotorValveValue`. Der generische Aktorwert ist als Schätzwert gekennzeichnet. Dies ist kein Nachweis einer vollständig spezifizierten realen Aktorfunktion. Die Warnungen wurden nicht unterdrückt oder automatisch freigegeben.

## Konsistenz- und Browserprüfungen

- 99 Backend-Tests bestanden: Workflow, Wizard-Erzeugung einschließlich großem Modell, Abbruch, Routing, Gerätekommunikation und Simulationsumfang. Drei zunächst mangels expliziter Testdatenbank-Konfiguration übersprungene Scope-Tests anschließend mit der lokalen Testdatenbank erfolgreich ausgeführt.
- 25 Frontend-Tests bestanden: Fortschritt, Wiederaufnahme, Abbruch und Wizard-Einstellungen.
- Produktionsbuild einschließlich TypeScript erfolgreich.
- Alle neun Browseransichten geladen; keine JavaScript-Seitenfehler.
- Browsermessung: Schritt 1 statisch 0; Schritt 4 RUNNING mit Zwischenwerten bis 90; Schritt 5 statisch 0; Schritt 4 BLOCKED statisch 0. Keine Simulation einer Fertigstellung durch den Fortschrittsbalken.
- Zusätzliche Integrationstests prüfen getrennte CAN-FD-Backbones sowie CAN-FD/Ethernet über das Gateway vor Erzeugung der Topologie.
- Wiederholung des abgeschlossenen Agent-Auftrags erzeugt keine zusätzliche Simulation.

## Aktuelles Benutzerprojekt

Projekt `network-project-20260909134330958-877242ab` war in Schritt 2 blockiert. Der vorhandene Gateway besaß nur einen ungebundenen Ethernet-Anschluss.

Die Korrektur wurde zunächst vollständig in einer zurückgerollten Transaktion geprüft. Anschließend wurden acht fehlende Backbone-Anschlüsse ergänzt und der ungebundene Ethernet-Anschluss dem bestätigten Diagnosebus zugeordnet. Bestehende gebundene Anschlüsse wurden nicht umgehängt.

Ergebnis: **317/317 Routenvorschläge valide, keine Validierungsbefunde**. Der Agent wurde bis `READY_FOR_REVIEW` fortgesetzt. Die Routenvorschläge sind nicht automatisch übernommen. Der vollständige neun Schritte umfassende Lauf ist für das isolierte Testprojekt nachgewiesen; das Benutzerprojekt wartet auf Routing-Review.

## Reproduzierbare Nachweise

- `verification/2026-09-09-nine-step-smoke.json`: echte HTTP-Aufrufe, Simulation, Abdeckung und Review-Grenzen.
- `verification/2026-09-09-nine-step-browser.json`: neun Seiten und gemessene Fortschrittswerte.
- `verification/2026-09-09-nine-step-project-repair.json`: angewandte Anschlusskorrekturen und Routingvalidierung.
- `verification/2026-09-09-nine-step-project-resume.json`: wiederaufgenommener Agent wartet auf fachliche Freigabe.
- `verification/2026-09-09-nine-step-frontend-tests.txt`: Frontend-Testprotokoll.

Testprogramme: `scripts/verify-live-wizard.py`, `scripts/verify-nine-step-browser.mjs`, `scripts/repair-wizard-backbones.py` (standardmäßig Rollback), `scripts/resume-wizard-routing.py` (keine Freigabe/Übernahme).

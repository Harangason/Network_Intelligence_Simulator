# Network Simulator – unabhängige Kampagne, Reparaturphase 1

Stand: 24.09.2026. Diese Datei ergänzt den eingefrorenen Run-1-Bericht. Gezielte Nachtests sind Reparaturnachweise und ersetzen keinen vollständigen neuen 95-Fall-Lauf.

## Kampagnenstand

Kampagne `nis-ea-independent-20260924-run1`, Zustand `REPAIR_1_ACTIVE`. Run 1 bleibt unverändert bei 19 PASS, 21 FAILED und 55 BLOCKED. Run 2 wurde nicht gestartet. Die reparierte Produktversion wurde nach vollständigem Release-Gate-PASS `fdaa1d50fba6` produktiv übernommen; dieses Gate ersetzt den unabhängigen 95-Fall-Run 2 nicht. Der genaue Produkt- und Fallstand steht in `NETWORK_SIMULATOR_PRODUCTION_S01_S20_REPAIR_REPORT_2026-09-24.md`.

## Behobene Ursachen und gezielte Nachtests

| Befund | Änderung | Direkter Nachtest |
| --- | --- | --- |
| Reuse-Adapter sperrte den neuen isolierten Projektpräfix | Präfix für diese unabhängige Kampagne erlaubt, Loopback-Zielbindung bleibt erhalten | S21 auf Run-1-Quelle S01-A: PASS |
| B-Varianten erhielten unangeforderte Gateway-Knoten oder portlose Gateway-Verbindungen | Testentscheidungen auf explizite Architektur begrenzt; Gateway-Controller-Verbindung aus vorhandener, passender Technik abgeleitet | S04-B und S05-B: PASS |
| Fragebogen verlor Geräteentscheidungen nach erneutem Parsen; JSON-Metadaten erzeugten Scheingeräte | Entscheidungen vor Vorschlagsannahme eingetragen; Metadaten von Hardwareinventar getrennt | S09-A: PASS |
| V4 + KI 2+3 fehlte als kombinierte Auswahl | Reviewbare Kombination in Wizard, Parser, Routing und physischer Zuordnung ergänzt | S19-B: PASS |
| S07-A blieb bei offenen Geräten/Industrieabgleich und Browser-Timing hängen | Robotics-Abgleich und sichtbare Geräteentscheidungen im Adapter verarbeitet; Schrittwechsel stabilisiert | S07-A: PASS |
| S60 überschritt durch doppelt eingebettete Quelltexte das Checker-Kontextlimit | Quelltext bleibt im Fallvertrag, zweite Kopie im Ausführungsschritt entfernt | Neuer S60-Vertrag: 33.897 Zeichen, Ausführungsschritt 3.458 Zeichen; noch kein vollständiger S60-Nachtest |
| EA-01 verwendete eine generische Funktion | Reviewbarer Entwurf mit `StellgliedPositionAbfrage`, `REQUEST_RESPONSE` und 30.000 ms | 3 isolierte Tests PASS; echter Browser-/Backend-Probe zeigt validierten Vorschlag, aber noch keine Übernahme und keinen Kommunikations-/Timingnachweis |
| S20-B: fortlaufender Simulationsjob wurde vom Checker nach fünf Minuten abgebrochen | Produkt-Wizard hält dieselbe Job-ID fortsetzbar; Checker wartet innerhalb des Fallbudgets | Vollständiger gezielter Positiv- und Negativfall PASS; negativer Job `completed`, Reasoning `BLOCKED_BY_DATA_GAP` mit 562 Evidence-Referenzen |

Die direkten Browsernachweise liegen unter `.tool-checker/runs/nis-ea-independent-20260924/repair-1/`. Das frühere vorbereitete Entwicklungsimage für EA-01 war kein Releaseimage. Das jetzt produktive Image `sha256:dccaac53b00f6009aa095c84e6eb232e48d4cea5ffa59157b3371c23f77b5bbc` gehört zum PASS-Receipt `backend/test-output/release-gates/fdaa1d50fba6/receipt.json`.

## Offene fachliche Befunde

- S05-A und S18-A stoppen mit einer konkreten Rückfrage. Die 4-ms-Safety-Zyklusangabe belegt allein keine deterministische Ende-zu-Ende-Reaktionszeit. Es fehlen bestätigte Worst-Case-Geräteverzögerungen, FSoE-Watchdog/Timeout, EtherCAT-Topologie und Master-Zeitplan sowie zulässige Ende-zu-Ende-Fristen. Für S18-A ist auch der 1-ms-Motion-Zyklus nachzuweisen. Der Nutzer hat strukturierte Rückfragen statt eines vorläufigen Zeitplans gewählt; beide Fragen sind gestellt. Bis zu den Antworten bleibt die Safety-Freigabe gesperrt.
- EA-01 erzeugt derzeit einen validierten, prüfbaren ECU-Vorschlag. Er ist weder im kanonischen Modell übernommen noch sind CANopen-Objektverzeichnis, Nutzdatenkodierung, Antwortzeit und Fehlerverhalten bestätigt. Deshalb ist EA-01 weiterhin kein bestandener Acceptance-Fall.
- Die gezielten Browser-Proben EA-04 und EA-11 haben eine echte Assistentenantwort mit `BLOCKED_WITH_EXPLICIT_CAUSE` nach überschrittenem Planungslimit ergeben. Die Modellrevisionen änderten sich nicht. Der angezeigte Wiederholungsweg ist noch kein bestandener Auftrag; beide Fälle bleiben offen.
- Für die 15 EA-Unterfälle fehlen noch vollständige fallbezogene Fixtures und ein ausführbarer Browser-/MCP-/Core-/Persistenzadapter. Die gezielte EA-01-Probe behebt diese Lücke nicht für die Suite.
- Die verbleibenden Run-1-Fehlergruppen sind nur durch Stichproben aus ihren Ursachenfamilien nachgeprüft. Alle 95 Fälle benötigen nach Abschluss sämtlicher Reparaturen einen neuen vollständigen Lauf auf genau einem eingefrorenen Image.

## Prüfgrenze und nächster Kampagnenschritt

Die isolierten Backend-Tests für `test_generated_controller_status.py` bestehen mit 3/3; die vorangegangenen Frontend-Tests für Parser und Routing mit 88/88. Die gezielten Wizard-Nachtests S04-B, S05-B, S07-A, S09-A und S19-B bestehen. S05-A und S18-A bleiben fachlich blockiert. Das vollständige Produkt-Release-Gate ist PASS (2048 Backend-PASS, 68 Browser-PASS, beide Live-Wizard-Checks PASS), doch kein Ergebnis der unabhängigen 95-Fall-Kampagne wurde als Gesamt-PASS hochgestuft. Der Tool-Checker-Vertrag sperrt Run 2, solange offene Reparaturen und EA-Fixtures verbleiben.

# Wizard: gemeinsame Prozessgrundlage

## Befund und Korrektur

Die Blockade war keine reine Performance- oder Anzeigeursache. Mehrere Stufen verwendeten unterschiedliche Grundlagen:

1. **Kommunikation:** Das Modell erzeugte ECU-Statusnachrichten, das Routing plante überwiegend Sensor-/Aktorbeziehungen und wenige Anzeigeverbindungen. Ein versionierter Kommunikationsplan weist jeder neu erzeugten Nachricht ihren Producer, Kommunikationszweck und Empfänger zu. Sensoren und Aktoren verwenden die bestätigte Gerätezuordnung. Statusüberwachung und zusätzliche fachliche Empfänger sind Teil des Modellreviews. Vorhandene explizite Empfänger bleiben erhalten. Fehlende Empfänger blockieren die Modellvalidierung.
2. **Auftrag und Ressourcen:** Erzeugung und Ressourcenprüfung lasen Vorgaben aus verschiedenen Quellen. Der bestätigte Auftrag liegt jetzt als `wizard_request` mit Hash im serverseitigen Workflow-Kontext. Planung und Validierung lesen dieselbe Ressourcenbasis. Ein Regressionstest sichert ausdrücklich ab, dass die Kontext-Whitelist diesen Auftrag nicht verwirft.
3. **Physische Architektur:** Zunächst ungeteilte Modellbusse standen später erzeugten Segmenten gegenüber. Die bestätigte Segmentierung wird jetzt vor der Anlage von Hardwareanschlüssen und Nachrichten materialisiert. Das Routing und die Topologie übernehmen diese Identitäten. Lokale I/O-Netze gehören zum bestätigten Controller; das zentrale Gateway terminiert die Controller-Backbones bereits vor dem Routing.
4. **Review und Übernahme:** Verschachtelte Referenzen auf weitere Sendeanschlüsse wurden validiert, obwohl sie bei sequenzieller Übernahme noch nicht auflösbar waren. Vorschläge werden zentral nach ihren vollständigen Abhängigkeiten geordnet. Fehlende, doppelte und zyklische lokale Referenzen werden vor dem Review abgewiesen; die Validierung prüft dieselben verschachtelten Referenzen wie die Übernahme.
5. **Simulation:** `jitter_ms` wurde sowohl als erlaubtes Budget als auch zur Erzeugung zufälliger Störungen verwendet. Das änderte besonders auf LIN die Sendereihenfolge und verursachte künstliche Grenzwertverletzungen. Das Budget bleibt unverändert. Eine explizite Quellstörung wird über `source_jitter_ms`, `jitter_ratio` oder das Fehlerszenario eingestellt. Reale Serialisierung, Queue-Wartezeiten und deren Jitter bleiben Bestandteil der Simulation.
6. **Reproduzierbares LIN-Timing:** Bei gleichzeitig fälligen LIN-Polls hatte die zufällige Route-ID die Reihenfolge bestimmt. Ein 100-ms-Frame konnte dadurch einen 10-ms-Poll verzögern. Gleichzeitig fällige Polls werden jetzt nach kürzester Periode zuerst bedient. Regressionstests vertauschen die IDs; die Zeitvorgaben bleiben identisch.

## Wiederaufnahme und bestehende Projekte

- Die Routing-Erzeugung ergänzt fehlende Producer-/Consumer-/Nachrichtenkombinationen, statt bereits vorhandene Routen erneut anzulegen.
- Fortsetzungszeilen verändern die Identität des bestätigten Routing-Auftrags nicht.
- Fehlende Kommunikationspläne bestehender Projekte werden als reguläre Modelländerung zur Prüfung angeboten. Wiederholungen verwenden den ausstehenden Vorschlag; nach Übernahme entsteht kein zweiter identischer Vorschlag.
- Bereits übernommene Topologievorschläge werden nicht als erneut freizugebende Capacity-Reparatur ausgegeben.
- Freigaben werden nicht allein aus erfolgreicher Erzeugung abgeleitet. Fachliche Review-Grenzen bleiben bestehen.

## Nachweisverfahren

`scripts/verify-live-wizard.py` spielt die vollständige gespeicherte große Wizard-Spezifikation über die echte HTTP-Schnittstelle in ein neues isoliertes Projekt ein. Modell, Routing und Topologie werden dort über den regulären Review-/Apply-Ablauf übernommen. Danach folgen echte Capacity-Berechnung, Preflight, Simulation, Trace-Auswertung und Intelligence. Es gibt keine direkten Datenbankreparaturen, keine Simulation-Stubs und keine Reduktion des Umfangs `ALL`.

Der Test verlangt vollständige beobachtete Signal-, Routen- und Netzabdeckung sowie einen echten Trace mit Signalen. Eine abschließende Wiederholung darf keinen weiteren Simulationsjob erzeugen. Browserprüfungen decken alle neun Seiten und die nur während Schritt 4 aktive Parameter-Fortschrittsanzeige ab.

Die Normal-Simulation umfasst eine Sekunde mit festem Seed 42. Dieser Smoke-Test beweist den vollständigen technischen Ablauf für das große Musterprojekt; er ersetzt keine Freigabe realer Gerätespezifikationen oder eine Dauerlast-/Fehlerszenarienkampagne.

Ergebnisdatei des vollständigen Server-Durchlaufs: `verification/2026-09-09-solid-workflow-large.json`.

## Abgeschlossenes Ergebnis

Getesteter und laufender Build: **67de13e2de0c**. Der Quellmanifest-Hash stimmt mit dem im Simulationssnapshot gespeicherten Release überein.

| Nachweis | Ergebnis |
| --- | --- |
| Neues großes Projekt | `astra-e2e-d26f53b42e9b` |
| Umfang | ALL, 311 Nachrichten, 725 Signale |
| Beobachtete Routen | 370 / 370, keine fehlenden Routen oder Netze |
| Beobachtete Signale | 725 / 725 |
| Laufzeit-Konformität | PASS, 0 fehlgeschlagene Routen |
| Schritte 1–8 | COMPLETE bzw. APPROVED |
| Schritt 9 | Ausgeführt; WARNING wegen 51 SINGLE_POINT_OF_FAILURE-Befunden |
| Review-Runden im Test | Genau Modell, Routing und Topologie; keine nachträgliche Reparaturrunde |
| Gemessene HTTP-Zeit einschließlich Übernahme und Simulation | 124,512 Sekunden; ohne menschliche Review-Wartezeit |
| Backend-Regressionen | 185 bestanden in 81 Sekunden |
| Browser | Neun Seiten geladen, keine JavaScript-Fehler |
| Parameteranimation | Nur Schritt 4 / RUNNING animiert; vor/nach Schritt 4 und bei BLOCKED statisch |
| Neustart und erneute Fortsetzung | PASS; gleicher Auftrag, gleiche Zustände und derselbe einzige Simulationsjob |

Die 51 Warnungen benennen fehlende Architekturredundanz. Sie wurden nicht unterdrückt oder automatisch durch zusätzliche Hardware beseitigt.

Das bestehende Nutzerprojekt `network-project-20260909142156009-65a06f78` wurde nicht mit dem Testprojekt überschrieben. Sein Kommunikationsplan liegt als validierter Vorschlag `e312b242-a982-4399-9223-b3a0e5a198fc` im normalen Agent-Wizard-Review. Die Sichtbarkeit wurde ohne Freigabeklick im echten Browser geprüft. Die fachliche Übernahme dieses Vorschlags steht noch aus; der bestehende Projektstand ist daher noch nicht mit dem vollständig geprüften neuen Testprojekt gleichzusetzen.

Weitere Nachweise: `verification/2026-09-09-solid-workflow-large-resume.json`, `verification/2026-09-09-nine-step-browser.json`, `verification/2026-09-09-solid-existing-review.json`.

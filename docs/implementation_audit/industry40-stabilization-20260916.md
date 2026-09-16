# Stabilisierung nach der industrieneutralen Prüfung

Umsetzung nach Nutzerfreigabe „OK“. Ausgangsbefunde und Einzelbelege in .tool-checker/reports/industry40-report.md bleiben unverändert.
Originalquelle SHA-256: 5f3d9eecb6339412c5deb40d17d7a1504562e1142f4a7db3d29038c50da95aeb.

Die Nutzerentscheidung CAN-FD/Ethernet für S07-B bleibt gültig. Andere offene Architekturentscheidungen werden nicht automatisch beantwortet.

## Korrekturen im Arbeitsstand

- Geräteumfang: qualifizierte und zusammengesetzte Rollen, additive Untergruppen, wiederholte Gesamtmengen und abstrakte Kopplung getrennt behandeln. Frontend und Chat-Entwurf verwenden dasselbe Gerätewortschatz-Artefakt.
- Alle 40 unveränderten Eingaben mit expliziten Mengen als dauerhafte Fixtures. Unbekannte Mengen bleiben im Prüforakel null; keine stillen Architekturannahmen.
- Ganze Inventaraufträge gehen in den Projektentwurf statt in einen einzelnen Funktions- oder Signalgenerator. Der ursprüngliche Auftrag bleibt erhalten.
- Im Entwurf bleiben fehlende Typen/Funktionen/Anschlüsse als offene Angaben sichtbar. Mengen erzeugen keine bestätigten Fähigkeiten oder Modellfreigaben.
- Optionale LLM-Planungsnotizen beim Entwurf haben eine 20-Sekunden-Grenze. Ihr Ausfall verhindert nicht mehr die Speicherung des vollständigen Entwurfs.
- Werkzeugargumente vor Ausführung gegen das veröffentlichte Schema prüfen. Nur schemaabhängiges JSON dekodieren; keine Auswertung von Python-Zeichenketten. Kennungen wie die Zeichenkette „null“ ablehnen.
- Identische fehlgeschlagene Aufrufe durch ein Reparaturbudget begrenzen.
- Bereits beantwortete Entscheidungsschlüssel in Orchestrierung und Fachwerkzeug wiederverwenden statt erneut als offene Frage anzulegen.
- Freie, nicht als Berechnungsartefakt gelieferte numerische Engineering-Aussagen nicht als bestätigte Rechenergebnisse ausgeben.
- Nach Verbindungsabbruch Ergebnisse aus gespeicherten Backendantworten wiederherstellen; doppelte Antworten bei späterer Streamzustellung vermeiden. Terminale Fehler/Abbruchzustände ebenfalls speichern.
- „industrieneutral“ ist keine Auswahl der Branche Industrieautomation.

## Prüfungen und Grenzen

Die 40 Mengenregressionen und bestehenden Frontend-Tests bestanden im Arbeitsstand. Gezielte isolierte SQL-/Agentenprüfungen bestanden, einschließlich Entwurfsrevision, Freigabe, Gesprächswiederherstellung, Projektisolation und wiederholter Entscheidungen. Die vollständige Releaseprüfung wird separat protokolliert; dieser Text ist kein PASS-Beleg.

Neu hinzugefügte Browserprüfungen öffnen alle 40 Anforderungen im echten Wizard und prüfen Sollmengen und die Sperre bei unvollständigem Inventar. Sie sind ausdrücklich keine 40 vollständigen Simulationen und ersetzen keine Live-LLM-Prüfung. Neunstufige E2E-Prüfungen, Wiederanlauf und ALL-Scope-Evidenz bleiben Aufgabe des fachlichen Release-Gates.

## Noch nicht durch diese Änderungen belegt

- Vollständige A/B-Architekturqualität aller 40 Szenarien nach allen notwendigen Nutzerentscheidungen, einschließlich Robotik, Labor, Energie und Gebäude.
- Vollständige Übernahme spezifischer Gerätespezifikationen aus beliebigem Fließtext; ein korrekt gezählter Entwurf ist noch kein fertiges Modell.
- Semantische Konsistenz beliebiger LLM-Auswahltexte (z. B. drei vs. vier Cluster).
- Vollständige Zerlegung und Durchführung der Großaufträge S19/S20 durch den freien Agenten. Die Korrektur verhindert ihre Reduktion auf einen Signalauftrag, weist aber noch keine vollständige Ausführung nach.

Ein Produkt-Rollout ist erst mit einem PASS-Receipt des exakt getesteten Images zulässig.

## Abgeschlossene Produktionsabnahme

Release-Gate `backend/test-output/release-gates/6e18e42d8df8/receipt.json`: **PASS**.
Build `b1297e9bad56`, unveränderliches Image `sha256:8c249e600edeca8dc3f924afbb2d6c10eb4f6776f3d54f85ff7aa2ec7394f3cf`.

Am 16.09.2026 über `start-networkis.ps1 -ReleaseReceipt ...` installiert. Laufender Container, Image-ID und Buildmanifest stimmen mit dem PASS-Receipt überein. Readiness meldet Datenbank und Speicher verfügbar; lokaler und LAN-Endpunkt erreichbar.

- TypeScript erfolgreich; 388 Frontend-Tests bestanden.
- Vollständige isolierte Backend-Suite: 1771 bestanden, 2 übersprungen. Bestehende Pydantic-Warnung zum Feldnamen `validate` bleibt sichtbar.
- 67 Browserfälle auf dem Produktionsimage bestanden, einschließlich aller 40 Inventarprüfungen, direkter Chat-Modellerstellung, I2C und Modbus RTU durch alle neun Schritte, Großmodell, realem Wiederanlauf und Änderung nach Modellfreigabe.
- Unabhängige HTTP-Abnahme klein: 8/8 Routen, 0 fehlgeschlagen, Konformität PASS.
- Unabhängige HTTP-Abnahme groß: 838/838 Routen, 0 fehlgeschlagen, Konformität PASS.
- Die Workflow-Befunde für Kapazität, Validierung und Bewertung können WARNING enthalten; bestandene Ausführung bedeutet keine pauschale fachliche Freigabe aller Annahmen.

Der vorherige Lauf `57199c0b98a4` bleibt als FAIL dokumentiert: Der neue Schutztest hatte zulässige initiale Projektlesezugriffe fälschlich verboten. Nach Korrektur prüft er, dass der ungültige Agentenaufruf keine zusätzlichen Werkzeugaufrufe auslöst. Anschließend wurde das vollständige Gate erneut ausgeführt, nicht nur der Einzeltest.

Diese Abnahme hebt die unten beschriebenen Grenzen für die vollständige Architekturqualität aller 40 Szenarien nicht auf.

## Zusätzliche ausgeführte Nachweise

- 40/40 reale MCP-Auftragsannahmen mit lokalem Modell: Mengen und Originalanforderung erhalten; weiterhin INCOMPLETE statt falscher Gesamtfertigmeldung. 19 Modellantworten, 21 begrenzte Fallbacks für optionale Planungsnotizen. Diese Quellstandprüfung ist kein Image-Freigabenachweis.
- 43/43 Browserprüfungen auf isoliertem Diagnoseimage b1297e9bad56: 40 Inventarszenarien und drei Sensor-/Anschluss-/Freigaberegressionen.
- 2/2 echte neunstufige Nicht-Automotive-E2E-Prüfungen auf demselben Diagnoseimage: Raspberry Pi mit I2C bzw. Modbus RTU, tatsächliche Modellübernahme und Simulation, Reload/Restart, keine Automotive-Technologien. Dies ist weiterhin kein Release-PASS: das Diagnoseimage ist ausdrücklich development_only.

Belege: .tool-checker/reports/stabilization-live40-summary.json und backend/test-output/stabilization-preview/2e1c69ac76d3/. Das vollständige Produktions-Gate wird gesondert abgeschlossen.

## Zuordnung zu den Ausgangsbefunden

| Ausgangsbefund | Korrektur / Nachweis | Verbleibende Grenze |
| --- | --- | --- |
| 27 fehlerhafte Mengenfälle | 40 Mengenregressionen, 40 Chat-Inventare und 40 Browser-Inventare geprüft | Typisierung und technische Auslegung sind eigene Schritte |
| S01-A / S19-A falscher Einzelgenerator | Vollständige Inventaraufträge zuerst als vollständiger Entwurf erfasst | Kein Beleg einer vollständigen S19/S20-Workload-Ausführung |
| S02-A / S05-A falsche Argumenttypen | Schema-Prüfung vor Ausführung, begrenzte Wiederholung | Kein automatisches Erraten fachlich fehlender Argumente |
| S03-A unzulässiges „Übernehmen“ | Sollumfang wieder korrekt erfasst; Browser prüft gesperrte Freigabe bei Lücken | Offene Angaben werden nicht durch Defaults verdeckt |
| S07-B identische Rückfrage | Beantwortete Entscheidungsschlüssel im Orchestrator und Werkzeug wiederverwenden | Eine fachlich neue Entscheidung bleibt eine neue Frage |
| S08-A unbelegte Zahlen | Freie Zahlenbehauptung ist kein bestätigtes Berechnungsartefakt | Keine Qualitätsgarantie für beliebigen LLM-Fließtext |
| S14-A Zeichenkette null als Kennung | Vor Ausführung abweisen | Vorhandene Projekte werden nicht still migriert |
| Antwort-Timeout / verlorene Anzeige | Planungsnotizen begrenzt; dauerhafte Antworten nachladbar und dedupliziert | Reale Langläufe können weiterhin Zeit benötigen |
| Nicht-Automotive bis Schritt 9 | Zwei reale komplette Diagnose-E2Es bestanden | Nicht gleichbedeutend mit allen 40 vollständigen Branchenfällen |

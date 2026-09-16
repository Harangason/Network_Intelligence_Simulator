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

# Industry60 – Korrekturen, 16.09.2026

Grundlage: `.tool-checker/reports/industry60-report-20260916.md`.
Dieser Nachweis ersetzt nicht die ursprünglichen 60 Szenarioergebnisse durch pauschale PASS-Werte.

| Befund | Änderung | Nachweis / Grenze |
|---|---|---|
| F01 | Chat-Verlauf erhält tief verschachtelte typisierte Daten; Speicherbudget entfernt vollständige Nachrichten statt Diagrammknoten durch Strings zu ersetzen. | Frontend-Roundtrip mit 130 verschachtelten Knoten; bestehende kanonische Vorschlagsreferenzen bleiben erhalten. |
| F02 | Konkreter Verbindungsauftrag hat Vorrang vor Einstieg CREATE_ARCHITECTURE. | Originaler S30-Auftrag im Regressionstest; Ziel ist weiterhin der bestehende Verbindungsausführer. |
| F03 | Routenvergleich erfolgt pro physischem Segment und Nachricht. | Reguläre alternierende Gateway-Segmente erzeugen keinen ROUTE_CHANGE; echte Netzänderung desselben Segments bleibt erkannt. |
| F04 | Inline-Zeitfenster erfordern eine gültige Ereigniszeit. | Fehlende, negative, null und NaN-Zeiten werden abgewiesen; keine erfundene Nullzeit. Dateiimport darf unbekannte Zeiten weiterhin sichtbar erhalten. |
| F05 | Auswahl persistiert Ereignis-ID und Fokus im Link; Ereignis-ID hängt nicht mehr vom Seitenindex ab. | Frontend-Identitätstest und zusätzlicher Browsertest für exakte Auswahl nach Reload. |
| F06 | Projektgebundene persistente Import-Sessions mit Originaldatei, SHA-256, normalisiertem JSONL, Zeitindex und Byte-Cursor-Fenstern. | HTTP-Test mit 100.501 Ereignissen einschließlich fremdem Projekt und Reload. Skalare MDF-Kanäle werden blockweise gelesen; nicht unterstützte Array-Kanäle und Busobjekte bleiben ausdrücklich PARTIAL. |
| F07 | Engineering-MCP-Server und Client liefern schema-basierte INVALID_INPUT-Befunde mit Feldpfad, Grund und erwartetem Schema. | Echter MCP-Aufruf mit negativer Payload. Direkter MCP-Aufruf erhält denselben strukturierten Fehlervertrag. |
| F08 | Keine automatische PWM-/Ventil-Encoding-Änderung. | Im Bericht ausdrücklich Verbesserungshinweis, kein bestätigter Fehler. Eine bestätigte Stellgrößenanforderung bleibt erforderlich. |
| F09 | Kommunikationsprüfung erhält deterministischen lesenden Pfad. Trace-Modus übernimmt ausgewählten Lauf und beendet eine begrenzte Auswertung ohne leere Weiter-Seiten-Schleife. Allgemeine Planung erhält Zeit- und Wiederholungsgrenzen. | Test für Trace-PARTIAL ohne Weiter-Aufruf. Backend speichert Ergebnisse weiterhin unabhängig von Browser-Verbindungsabbrüchen. Kein Nachweis allgemeiner LLM-Ergebnisqualität. |

## Prüfung

- Gezielter Backend-Lauf: 39 bestanden (isolierte PostgreSQL-Datenbank).
- Frontend: 390 bestanden; TypeScript erfolgreich im laufenden Release-Gate.
- Vollständiges Release-Gate: läuft, noch keine Auslieferungsfreigabe.
- Produktdeployment: bisher keines für diese Korrekturen.

Die offenen Architekturentscheidungen der ursprünglichen A/B-Szenarien wurden nicht automatisch beantwortet.

Zusatznachweis F01: Die originalen S24-Antworten aus dem Prüfbericht wurden durch
`transportMessages` und einen JSON-Roundtrip geführt. Alle 28 fachlichen Antworten
bestehen anschließend `AgentResponse.model_validate`, einschließlich einer Antwort
mit typisierten Diagrammausgaben. CONTEXT-Transportumschläge sind kein AgentResponse
und wurden separat ausgeschlossen. Nachweis:
`.tool-checker/industry60-S24-cache-verification.json`.

Zusatznachweis F09: Zwei kontrollierte Prüfungen bestätigen den Abschluss mit
INCOMPLETE bei unverändert wiederholtem Werkzeugaufruf und bei Inferenz-Timeout:
`.tool-checker/industry60-loop-correction-evidence.json`.

Zusatznachweis F03: Wiederholung des originalen kanonischen Trace-Fensters mit
400 Ereignissen. Die gemeinsame route_id reicht nicht als Abschnittskennung;
die Korrektur berücksichtigt nun segment_id/segment_index. Keine falsche
ROUTE_CHANGE-Beobachtung mehr, während die realen Delay-/Deadline-Befunde erhalten
bleiben. Extrakt als dauerhafte Regression:
`tests/fixtures/industry60-gateway-segments.json`. Gegenprobe mit verändertem Netz
desselben Abschnitts bleibt positiv. Vollständiger Replay-Nachweis:
`.tool-checker/industry60-route-correction-replay.json`.

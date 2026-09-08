# Wählbarer Speicherpfad – 8. September 2026

## Ergebnis

Einstellungen im Studio erweitert: projektbezogener Trace-/Ergebnisordner mit direkter Pfadeingabe, begrenztem Ordnerbrowser, Schreibprüfung, Speicherbestätigung und Rückkehr zum Standard. Backend prüft Pfade und schreibt Einstellungen atomar im stabilen Runtime-Volume. Jeder neue Job erhält bei Einreichung einen unveränderlichen Ausgabepfad; Thread- und Prozess-Worker sowie spätere Downloads verwenden diesen gespeicherten Pfad. Alte Jobs ohne Pfadfeld bleiben kompatibel.

Keine Migration und keine Löschung bestehender Traces. Kein Eingriff in das ursprüngliche Engineering-Projekt oder seine Freigaben. Getestet im gesonderten Projekt `astra-storage-ui-20260908`.

## Nachweise

- Backend: **647 Tests bestanden**, einschließlich 15 neuer Speichertests; 112,74 Sekunden. [JUnit](verification/2026-09-08-storage-pytest.xml).
- Frontend: **177 Tests bestanden**, TypeScript ohne Fehler, Docker-Produktions-Build erfolgreich.
- Browser: Pfad eingeben → prüfen → speichern; Ordnerbrowser mit Eltern-/Unterordner-Navigation; relativen Pfad ablehnen; gültige Einstellung bleibt nach Neuladen erhalten.
- Live-Simulation über den Frontend-Proxy: Job `88986a88c2744f2e8ab6b8a1b50b7513`, fünf echte Dateien im ausgewählten Unterordner. Trace enthält drei Ereignisse; Download und Trace-Ansicht funktionieren auch nach Zurücksetzen des Projektpfads. [E2E-Bericht](verification/2026-09-08-storage-live.json).
- Dateiprüfung direkt im Container bestätigt `universal_trace.jsonl` (4314 Byte), CSV, Modelltrace, Manifest und Ergebnis-JSON.
- Job-Neustart-Kompatibilität, wartende Thread-/Prozess-Jobs bei Pfadwechsel, Projektisolation, unbeschreibbare Ziele, korrupte Einstellungen, Windows-Mapping und Ausbruch aus erlaubten Docker-Wurzeln durch automatisierte Tests geprüft.
- Optionales Compose-Override syntaktisch geprüft; weder das Runtime-Volume noch die Datenbank-Einbindung werden ersetzt.
- Alle **230 API-/Methoden-Kombinationen** über den Frontend-Proxy erreichbar, keine 5xx-/405-Antworten. Erwartete Validierungs- und Nicht-gefunden-Antworten sind kein Nachweis erfolgreicher Fachoperationen. [Endpoint-Bericht](verification/2026-09-08-storage-endpoints.json).

## Offene Umgebungsgrenze

Zwei Versuche, neue Windows-Testordner auf I: bzw. F: einzubinden, wurden von Docker selbst mit `input/output error` abgewiesen. Deshalb ist die tatsächliche Host-Bind-E2E-Prüfung **nicht erfolgreich** und kein beliebiger Windows-Ordner im produktiven Container verfügbar. Die Anwendung zeigt die Grenze ausdrücklich an. Interne persistente Ordner sind wählbar und live verifiziert. Kein globaler Docker-/WSL-Neustart und keine Änderung anderer Container vorgenommen. Der separate Testdatenbank-Container wurde nach der Testsuite wieder gestoppt; seine Daten blieben erhalten.

Details zur Bedienung und zur optionalen Host-Einbindung: [TRACE_SPEICHERORT.md](../TRACE_SPEICHERORT.md).

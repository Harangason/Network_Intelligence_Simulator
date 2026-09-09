# Wizard-Performance

Build `d0c7ff36fb17`, 9. September 2026. Untersucht wurde das Projekt `network-project-20260909141231587-a29bc00f`.

## Messung und Änderung

- Statusabruf: 0,085 Sekunden, ca. 191 KB; vollständiger Workflow: 0,200 Sekunden, ca. 200 KB. Das Öffnen des Wizards verwendet jetzt die Zusammenfassung.
- Routenliste: ca. 1,07 MB pro Abruf. Bisher erfolgte der Abruf alle fünf Sekunden auch bei unverändertem Projekt. Der Wizard lädt diese Daten jetzt nur bei geänderter Workflow-Revision oder Routing-Prüfung. Status wird bereits vor Abschluss des Routenabrufs angezeigt.
- Browserprüfung: während zwölf Sekunden unverändertem Zustand genau ein initialer Routenabruf; nach Änderung der Revision genau ein weiterer Abruf. Keine JavaScript-Seitenfehler. Der Status wurde weiter regelmäßig aktualisiert.
- Der aktuelle Auftrag war bereits blockiert, nicht langsam rechnend: 317 Routen waren freigegeben, die Wiederaufnahme erzeugte sie dennoch erneut und scheiterte an Duplikaten. Der Agent erkennt jetzt die vollständig freigegebenen vorhandenen Routen, bevor er den Generator aufruft, und benennt die unvollständige Scope-Abdeckung direkt.
- Live-Wiederaufnahme nach Korrektur: 2,064 Sekunden, keine neuen Routenvorschläge. Konkretes Ergebnis: fehlende bestätigte Transporte für 48 Nachrichten und 240 Signale. Es wurden keine Empfänger erfunden oder freigegebene Routen verändert.

## Prüfung und Grenzen

14 Scope-/Wiederaufnahmetests bestanden, Produktionsbuild einschließlich TypeScript erfolgreich. Die Browserprüfung prüft unveränderte Polls und Neuladen bei Revisionserhöhung. Dies ist keine Messung sämtlicher Eingabeschritte oder ein Nachweis allgemeiner Beschleunigung der Modellerzeugung.

Der aktuelle Gesamtumfang bleibt fachlich unvollständig. Die fehlenden Transporte benötigen bestätigte Empfänger oder einen begründeten kleineren Simulationsumfang. Diese Einschränkung wird nicht durch eine neue Generierungsrunde verborgen.

Nachweise: `verification/2026-09-09-wizard-performance-browser.json`, `verification/2026-09-09-wizard-performance-resume.json`. Browserprüfung reproduzierbar mit `node scripts/verify-wizard-performance.mjs`.

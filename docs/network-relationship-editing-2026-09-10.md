# Bearbeitung von Buslinien und Interface-Namen

Stand: 10.09.2026, Build `8df3b5821d49`.

## Fehlerursachen

- Busstämme besaßen nur einen Handler zum Verschieben. Der Doppelklick zur Bearbeitung war ausschließlich an Abzweigen und einzelnen Kanten angeschlossen; die Beschriftung nahm keine Mausereignisse an.
- Die Synchronisation von HardwareNetworkInterface übernahm Anschluss-Metadaten, aber nicht den eingegebenen Namen. Anschließend ersetzte die Materialisierung Namen generierter Anschlüsse und sichtbarer Ports durch den Busnamen. Die Antwort an den Browser enthielt deshalb erneut den alten beziehungsweise automatisch erzeugten Namen.

## Änderung

- Doppelklick auf Busstamm, Abzweig oder Beschriftung öffnet die Beziehung. Bei mehreren Beziehungen auf demselben Abschnitt erscheint eine alphabetisch nach Endpunkten sortierte Auswahl. Zusätzlich öffnet „Verbindung bearbeiten“ die ausgewählte Linie.
- Quell- und Ziel-Interface werden im kanonischen Anschluss gespeichert. Mehrere sichtbare Ports desselben Hardwareanschlusses und sämtliche betroffenen Kanten erhalten denselben Namen. Widersprüchliche Aliasnamen werden atomar abgelehnt.
- Interface-Name, physischer Busname und technische IDs bleiben getrennte Angaben. Die Namensänderung verschiebt keinen Anschluss auf einen anderen Bus. Die Bearbeitung zeigt den vollständigen gespeicherten Namen, ohne die Kürzungslogik für Busbeschriftungen anzuwenden.
- Vorhandene Gateway-Interfacenamen werden bei automatischer Anordnung beibehalten.

## Nachweis

- TypeScript-Prüfung und Produktionsbuild erfolgreich.
- 13 lokale Python-Tests bestanden; 4 SQL-Tests lokal übersprungen, ein separater Proposal-Test ausgenommen.
- 7 Tests in einer separaten PostgreSQL-Datenbank bestanden, einschließlich Umbenennen, erneutem Speichern und Laden, konsistenten Aliasnamen, unveränderten Anschluss-/Netz-IDs, Konfliktprüfung und vollständiger Rücknahme bei einem Speicherfehler.
- 5 bestehende Frontend-Tests für Verbinden und Löschen bestanden.
- Browserprüfung mit 1371 × 1272 Pixeln im isolierten Projekt `network-project-relationship-editing-ui-1789071034731`: acht Leitungsabschnitte, Beschriftung, Toolbar, alphabetische Auswahl, Quell-/Ziel-/Verbindungsnamen, Aliasangleichung, Fehler mit erneutem Speichern und Neuladen erfolgreich. Keine JavaScript-Seitenfehler.
- Das Anwenderprojekt wurde für diese Prüfung nicht verändert.

Prüfskripte: `frontend/scripts/verify-relationship-editing.mjs` und `scripts/verify_relationship_editing_sql.py`.

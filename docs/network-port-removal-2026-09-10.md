# Ports und Buslinien löschen

## Befund

Die gespeicherte Busansicht verwendete eine eigene Busauswahl, während Löschknopf und Entf nur Geräte und einzelne Kanten prüften. Ports konnten nicht gezielt für Entf ausgewählt werden. Ihr Rechtsklick verwendete einen älteren Speicherweg: Er verlor die Szene, speicherte freie Ports nicht im Engineering-Modell und wartete bei verbundenen Ports nicht auf das Speicherergebnis.

## Verhalten

- Port anklicken und Entf oder „Auswahl löschen“ verwenden. Rechtsklick auf den Port entfernt ihn ebenfalls. Seine zugehörigen Verbindungen werden mit entfernt; das Gerät bleibt bestehen.

- Einen Abzweig anklicken und löschen trennt den betreffenden Anschluss. Ein Busstamm wählt die Linien des gesamten Busses. Ports bleiben nach dem Löschen von Linien als freie Anschlüsse erhalten und können erneut verbunden werden.

- Geräteauswahl, Portauswahl und Linienauswahl lösen sich gegenseitig ab. Der markierte Port ist sichtbar hervorgehoben.

- Tastatur und Werkzeugknopf verwenden denselben asynchronen Speicherweg. Bei einem Fehler bleiben Auswahl und Projektzustand bestehen; erneutes Löschen ist möglich. Texteingaben und offene Dialoge bleiben vor globalem Entf geschützt.

- Die gespeicherte Szene und manuelle Layoutdaten bleiben beim Speicheraufruf erhalten. Der Server baut die betroffenen Linien aus der tatsächlichen Topologie neu auf.

- Entfernte Engineering-Verbindungen werden innerhalb derselben SQL-Transaktion entfernt. Freigewordene Kanäle verlassen den bisherigen Bus, behalten aber ihre Hardware-ID, Kanalnummer und Anschlussidentität. Bei entfernten Canvas-Ports wird die alte Kanal-Netzbindung einschließlich veralteter Topologie-Metadaten gelöst. Geräte-, Kanal- und Nachrichtendefinitionen werden dabei nicht gelöscht. Der vorhandene Routing-Abgleich und die Invalidierung nachgelagerter Bewertungen laufen weiterhin über den gemeinsamen Speichervorgang.

## Prüfung

- Fünf Frontendtests für Anschlussplanung und Löschumfang erfolgreich; 13 lokale Backendtests erfolgreich.

- Vier Prüfungen in einer separaten PostgreSQL-Datenbank: Anschließen, Löschen, Freigeben und Wiederverbinden, gespeicherte Relationen und Netzbindungen, Neuladen, veralteter Bearbeitungsstand und vollständiger Rollback bei injiziertem Fehler.

- Browserprüfung mit eigenem Projekt: freie Ports per Entf, verbundene Ports per Rechtsklick, Abzweige per Entf, Busstamm über Löschknopf, Gerät per Entf, Fokus auf Werkzeugleiste, geschützte Texteingabe, Fehler und Wiederholen, Neuladen und erneutes Verdrahten. Keine JavaScript-Fehler.

- Die Verbindungsprüfung aus der vorherigen Änderung wurde erneut erfolgreich ausgeführt, einschließlich Port → Bus, Bus → Port, Busabzweig als Ziel, Linienverschiebung und Umschalt+Portverschiebung.

- Produktionsbuild und TypeScript erfolgreich. Im Nutzerprojekt wurden für diese Prüfung keine Ports oder Verbindungen gelöscht.

Prüfprogramme: `frontend/scripts/verify-port-removal.mjs` (aus `frontend` ausführen), `scripts/verify_topology_removal_sql.py` (separate Datenbank `nis_topology_removal_tests`, pytest erforderlich). Ergebnis: `backend/runtime/port-removal-browser-result.json`.


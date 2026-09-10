# Entf im Netzwerkeditor

Build `3a1111882e49`, 10.09.2026.

Nutzerauftrag: Delete/Entf soll für markierte Verbindungen und Geräte global
funktionieren. Die Rückfrage, ob Geräte zusätzlich aus dem kanonischen
Engineering-Modell entfernt werden sollen, blieb während dieser Umsetzung
unbeantwortet. Deshalb entspricht der Umfang dem bestehenden Button
„Auswahl löschen“: Entfernen aus der gespeicherten Netzwerktopologie.
Kanonische Hardware, Nachrichten und Signale werden nicht gelöscht.

## Änderung

- Globaler Tastatur-Handler für Entf bei vorhandener Editor-Auswahl, auch mit
  Fokus auf einem Werkzeugknopf. Texteingaben, Selects, Contenteditable und
  offene Dialoge sind geschützt. Tastaturwiederholung und parallele
  Löschvorgänge werden abgefangen.
- Verbindungsauswahl ist in der gespeicherten Busansicht sichtbar. Ein
  unsichtbarer 16-Pixel-Trefferbereich erleichtert das Anklicken der Linie.
- Taste und Toolbar verwenden denselben asynchronen Speicherpfad. Die
  Auswahl wird erst nach erfolgreichem Speichern entfernt. Ein Fehler lässt
  Auswahl und Topologie bestehen. Auch Geräte ohne Verbindungen werden
  über den Speicherpfad verarbeitet.
- Entfernen eines Geräts entfernt seine incidenten Topologie-Verbindungen.
  Beim Löschen der letzten Verbindung wird die gespeicherte Szene neu
  aufgebaut; bei leerer Topologie wird eine alte Szene entfernt.

## Nachweise

- 53 Backend-Szenen-/Workflow-Tests bestanden, einschließlich leerer
  Verbindungsmenge und Entfernen des letzten Knotens.
- Produktionsbuild einschließlich TypeScript bestanden.
- Vollständige Projektkopie `network-project-delete-key-test-7f61273a41`:
  CAN-FD-Verbindung und Gerät Drehmomentkoordination per Entf entfernt,
  SQL-Speicherung und erneutes Laden geprüft. Entf wurde mit Fokus auf
  einem Werkzeugknopf ausgelöst. HTTP-409-Speicherfehler erhält Auswahl
  und Modellansicht. Entf im Umbenennungsfeld löscht nur Text; ein offener
  Dialog schützt das Gerät ebenfalls. Keine JavaScript-Seitenfehler.
- Kanonische Hardware bleibt bei diesem Topologie-Löschvorgang erhalten;
  auch das wurde nach dem Neuladen geprüft. Die Testkopie wurde entfernt.

Browserprüfung: `frontend/scripts/verify-network-delete-key.mjs`.
Ergebnis: `backend/runtime/delete-key-browser-result.json`.

# Geräte direkt im Systemrahmen anlegen

Nutzerauftrag: Doppelklick auf den Systemrahmen öffnet + ECU, + Sensor,
+ Aktor und speichert das neue Gerät direkt im gewählten Rahmen.
Aktiver geprüfter Build: `b3d5a2c8599e`.

## Umsetzung

- Doppelklick auf den Rahmenkopf öffnet einen modalen Dialog mit Typ und
  Gerätename; Enter/Leertaste auf dem fokussierten Rahmenkopf ebenfalls.
- Ziehen bleibt erhalten. Bewegungen unter fünf Bildschirmpixeln lösen beim
  Rahmen keine Layoutspeicherung aus. Abbrechen/Escape schreibt kein Gerät.
- Ein eigener POST `/api/engineering/workflow/frame-device` speichert
  Hardware, bestätigte funktionale Zugehörigkeit, Cluster und SQL-Szene in
  einer Projekttransaktion. Der aktuelle Topologie-Token schützt gegen
  veraltete Änderungen. Namenskonflikte bleiben im Dialog sichtbar.
- Zusätzliche ECUs gehören zum ausgewählten Rahmen und erzeugen keinen
  separaten Systemrahmen. Geräte werden als Entwurf angelegt; Anschlüsse,
  Funktionen und Kommunikation können anschließend spezifiziert werden.
- Bestehende Busse/Routen bleiben erhalten; abgeleitete Workflow-Ergebnisse
  werden ungültig. Eine funktionale Zugehörigkeit bestätigt keinen Einbauort.
- Vorhandene Gerätepositionen bleiben erhalten; wächst der Rahmen, wird
  erforderlicher Platz unterhalb geschaffen. Alle Layoutdaten werden gespeichert.
- Das Dialogformular liegt in einem Portal außerhalb des übergeordneten
  Workflow-Formulars. Sein Submit wird nicht zum Parameterformular weitergereicht.

## Regeln und Nachweise

`SPATIAL_ARCHITECTURE_CONTRACT.md`: kanonische Zuordnung und physischer Ort
bleiben getrennt; kein nur visuell zugeordnetes Gerät.
`COMMUNICATION_DESIGN_CONTRACT.md`: keine erfundene Kommunikation oder
funktionale Freigabe für einen gerade angelegten Geräteentwurf.

32 lokale Tests bestanden (10 Geräteplanungsprüfungen und 22 Szenenprüfungen).
Zusätzlich vollständiger API-Test gegen separate PostgreSQL-Datenbank
`nis_frame_device_tests`: alle drei Gerätetypen, erneutes Laden, veralteter
Token, doppelte Namen und Rollback nach bereits erfolgten SQL-Schreiboperationen.
Dieser SQL-Lauf umfasst die zehn Planungsprüfungen erneut: 11 bestanden.
Produktionsbuild einschließlich TypeScript bestanden.

Browserprüfung in einer vollständigen Kopie des Nutzerprojekts:
`network-project-frame-create-test-432f2d7be2`.
261 → 264 Geräte, unverändert 51 Systemrahmen und alle vorhandenen Verbindungen.
ECU, Sensor und Aktor im Rahmen Fahrerassistenz gespeichert; Zuordnung auch
in kanonischer Hardware und nach Neuladen geprüft. Ziehen, Abbrechen,
simulierter HTTP-409-Speicherfehler und Eingabeerhalt geprüft. Keine JavaScript-
Seitenfehler. Die Testprojektkopie wurde danach entfernt.

Tests: `backend/tests/test_frame_device.py`, `backend/tests/test_network_scene.py`,
`scripts/verify_frame_device_sql.py`, `frontend/scripts/verify-network-frame-device.mjs`.
Browsernachweise: `backend/runtime/frame-create-browser-result.json`,
`frame-create-dialog.png` und `frame-create-verified.png` im selben Ordner.

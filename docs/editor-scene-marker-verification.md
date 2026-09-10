# Busbeschriftung und Anschlussmarkierungen

Aktuelle Nutzerentscheidung vom 10.09.2026: Sämtliche Verbindungslinien im
Netzwerkeditor werden ohne Pfeilspitzen dargestellt, auch seitliche Zweige
und Verbindungen ohne gespeicherte Szene. Diese Entscheidung ersetzt die
nachfolgend dokumentierte frühere Pfeildarstellung. Kommunikationsrichtungen
bleiben im Datenmodell erhalten.

Geprüft auf Build `ccc9b9e57c12`: Produktionsbuild einschließlich TypeScript
erfolgreich. Browserausschnitt Fahrerassistenz mit CAN FD, LIN und Ethernet:
66 Linienpfade, keine SVG- oder CSS-Pfeilmarker, keine Seitenfehler.
Die aus SQL geladene Topologie war vor und nach der Anzeige identisch.
Nachweise: `backend/runtime/network-lines-without-arrows.json` und
`backend/runtime/network-lines-without-arrows.png`.

10.09.2026 · Build `706af335c0a8` · Szenenversion 4

Senkrechte Backbone-Beschriftungen haben jetzt 26 Zeichnungseinheiten Abstand zwischen Linie und Textgrundlinie. Parallele Backbone-Linien stehen 44 Einheiten auseinander. Lokale Beschriftungen verwenden 20 Einheiten Versatz innerhalb der bestehenden, schmaleren Zwischenräume.

Gerade Anschlüsse am Gateway und am lokalen Steuergerät erhalten keine Pfeile. Punkte kennzeichnen ausschließlich tatsächliche Verzweigungen mit mindestens drei Leitungsrichtungen. Gerade Fortsetzungen, doppelte Endpunkte und reine Winkel erzeugen keinen Punkt. Tatsächliche seitliche Kommunikationszweige behalten ihre bidirektionalen Pfeile. Dieselbe Verzweigungslogik gilt für SQL-Szenen, die Darstellung älterer Szenen und die Vorschau beim Verschieben.

## Prüfung

- 22 Backend-Tests bestanden, darunter Speicherung, erneutes Laden, Konfliktschutz und unveränderte Modellzuordnung.
- 223 Frontend-Tests bestanden; die drei betroffenen Geometrietests nach der abschließenden Abstandsänderung erneut bestanden.
- Produktionsbuild mit TypeScript-Prüfung erfolgreich.
- Browser bei 100 % und 150 % geprüft. Bei 150 % beträgt der gemessene Abstand zwischen Backbone-Linie und Schriftbegrenzung 22 Pixel. Die geraden Gateway-Anschlüsse haben keine SVG-Pfeilmarker und keine Punkte.
- Das aktuelle Projekt enthält 261 Geräte, 95 physische Busse und 95 gerade Anschlüsse. Die bereinigte Szene wurde gespeichert und identisch zurückgelesen. Modellinhalt, Verbindungen, manuelle Positionen, Gerätekoordinaten und Workflow-Versionen blieben unverändert.
- Verschieben der freien Zeichenfläche mit gedrückter linker Maustaste im Browser erneut geprüft.

Maschinenlesbarer Datenvergleich: `editor-scene-marker-verification.json`.

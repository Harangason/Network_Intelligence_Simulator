# Leitungsüberführungen und automatische Portpositionen

Nutzerentscheidung: Kreuzungen durch die Portanordnung möglichst vermeiden.
Verbleibende Kreuzungen verschiedener physischer Busse mit Überführungsbogen
zeichnen; ein Punkt bezeichnet weiterhin einen echten Verbindungsabzweig.
Linien bleiben ohne Richtungspfeile.

Die automatische Anordnung verteilt Ports in der geometrischen Reihenfolge ihrer
Leitungen innerhalb der Gerätekante. Auch bei vielen Leitungen an einem schmalen,
manuell skalierten Steuergerät fallen Ports nicht mehr auf dieselbe geklemmte
Position. Seitliche Ports werden nach der Lage ihrer Kommunikationspartner
geordnet. Verschachtelte Abgänge erhalten versetzte Abknickhöhen. Explizit
gespeicherte Portpositionen werden weiterhin respektiert.

Die Kreuzungsberechnung verwendet unveränderte orthogonale Leitungskoordinaten
und physische Bus-IDs. Sie fügt Lücken und separate SVG-Bögen in die Zeichnung ein.
Eine Unterlegung des Bogens trennt die überführte Leitung optisch auch bei
gleicher Farbe und unabhängig von der Zeichenreihenfolge. Dicht benachbarte
Kreuzungen können unter einem gemeinsamen Bogen liegen. Abzweige desselben
physischen Busses bekommen keinen Bogen. Übereinanderliegende parallele Linien
und zusammenfallende Endpunkte sind keine inneren Kreuzungspunkte.

`crossingVersion`, `wireBridges` und `displayPath` werden mit der Szene in SQL
gespeichert. Die Drag-Vorschau berechnet sie unmittelbar neu. Auch ältere Szenen
erhalten die Darstellung beim Laden ohne vorgelagerte asynchrone Layoutphase.
Unsichtbare Trefferflächen bleiben zusammenhängend: Auswahl und Linien-Drag
funktionieren auch an einem Bogen. Technische Verbindungen ändern sich nicht.

## Verifikation

- 101 Backendtests und 8 Frontendtests bestanden; Produktionsbuild mit TypeScript
  bestanden. Ein unabhängiger SQL-Test zur Systemrahmen-Erstellung blieb ohne
  dessen spezielle Test-DB-Konfiguration übersprungen.
- Browserprüfung mit einer vollständigen Projektkopie: absichtliche Kreuzung am
  Bus „Bremsregelung LIN VL“, sofortige Vorschau, SVG-Bögen, SQL-Speicherung,
  Neuladen und identische Kreuzungsgeometrie in Python und TypeScript.
- 57 Bögen in der automatisch berechneten Projektkopie, 66 nach dem absichtlichen
  Verschieben; Vorschau, gespeicherte Szene und Browser liefern denselben Stand.
- Keine Browser-Ausnahmen, keine Pfeilmarker; Topologiekanten und Workflow-Versionen
  beim Test unverändert. Screenshot: `backend/runtime/network-crossings-browser.png`.
- Die Bestandsansicht wird mit erhaltenen Gerätepositionen, manuellen Ports und
  manuellen Leitungsführungen aktualisiert. Der vorherige Stand ist unter
  `backend/runtime/network-crossings-project-before.json` gesichert.
- Partielles Speichern von Koordinaten erhält vorhandene manuelle Portpositionen;
  zusätzlich im SQL-Test über `scripts/verify_crossing_port_preservation.py` geprüft.

Prüfskript: `frontend/scripts/verify-network-crossings.mjs`.

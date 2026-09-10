# Netzwerk-Editor: Leitungen verschieben und automatisch führen

Die physische Busansicht hatte keine Drag-Handler für Leitungen. Lokale Buslinien
wurden nach technischen IDs mit festem Rechtsversatz angeordnet. Die Zuordnung
zu den tatsächlich links/rechts liegenden Teilnehmern ging dabei verloren;
geklemmte ECU-Anschlüsse und gemeinsame Abknickhöhen erzeugten Überlagerungen.

## Umsetzung

- Senkrechte Buslinie mit der linken Maustaste seitlich ziehen. Waagerechte
  Abzweige lassen sich vertikal versetzen; nötige rechtwinklige Zwischenstücke
  halten den Anschluss am Gerät fest. Eine Klickschwelle trennt Auswahl und Drag.
- Vorschau während des Ziehens, Speicherung beim Loslassen, Escape/Pointer-Abbruch
  verwirft die Vorschau. Bei abgewiesener Speicherung bleibt der bestätigte Stand
  erhalten und die Korrektur kann erneut gespeichert werden.
- `scene.manualBusRoutes` speichert Stammkoordinate und Abzweighöhen in der
  bestehenden SQL-Topologie. Validierung und bestehender Edit-Token schützen
  gegen ungültige Koordinaten und konkurrierende Änderungen. Alte Szenen bleiben
  lesbar. Bestehende Bus-IDs und technische Referenzen ändern sich dadurch nicht.
- „Linien automatisch“ setzt manuelle Linienführungen und die Platzierung
  verbundener Ports zurück. Gerätepositionen und unverbundene Ports bleiben erhalten.
- Lokale Leitungen werden nach der Lage ihrer Teilnehmer sortiert: kurze äußere
  Zweige außen, tiefere Zweige innen. Der Zwischenraum wird mittig genutzt;
  Linienabstand 28 px, bei bestehenden engen Rahmen mindestens 24 px.
  Neu erzeugte Rahmen reservieren genügend Platz für die benötigten Leitungen.
- Unzureichender Platz bei manuell positionierten Geräten wird kenntlich gemacht.
  Die Automatik behauptet keine kreuzungsfreie Lösung für beliebige Anordnungen.
  Linien bleiben ohne Pfeile; Punkte kennzeichnen tatsächliche Verzweigungen.

## Nachweis

- 95 Backendtests bestanden: Szene, Workflow, Buswechsel, Systemrahmen-Erstellung
  und Zuordnung. Ein separater SQL-Test zur Systemrahmen-Erstellung wurde mangels
  Test-DB-Konfiguration übersprungen; der aktuelle Layoutpfad wurde im laufenden
  SQL-System auf einer vollständigen Projektkopie geprüft.
- 4 Frontendtests bestanden; Produktionsbuild einschließlich TypeScript bestanden.
- Browser: Drag bei 100 % und 150 %, Abzweig mit festem Geräteanschluss,
  SQL-Speicherung und Neuladen, Escape, 409-Rollback, automatischer Reset,
  keine Pfeilmarker und keine Browser-Ausnahmen.
- Bremsregelung, sieben LIN-Busse: 22 geometrische Kreuzungen und zwei Paare
  überlagerter Busleitungen vorher; jeweils null nach automatischer Führung.
- Verglichen wurden Gerätekoordinaten, Topologiekanten, Modell-Signatur und
  Workflow-Versionen. Layoutänderungen verändern keine dieser fachlichen Daten.

Reproduzierbare Prüfungen: `scripts/verify_wire_layout.py`,
`frontend/scripts/verify-network-wire-layout.mjs`. Laufartefakte liegen unter
`backend/runtime/wire-layout-*.json` und `wire-layout-browser.png`.

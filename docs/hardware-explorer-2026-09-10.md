# Hardware-Topologie: 2D und 3D

Nutzerauftrag: den vorhandenen radialen Hardware-View um die Fähigkeiten des
Musters `H:/OneDrive/Download/project-3d/` ergänzen.

## Übernommene Bedienfunktionen

Die bestehende Umschaltung Hardware / Functions / Combined enthält nun zusätzlich
2D / 3D, Suche, alphabetische Trefferlisten, Typ- und Bustypfilter, einen
Detailbereich mit navigierbarem Zuordnungspfad, Vollbild und echtes Einpassen.
Zweige können per einfachem Knotenklick oder Detailaktion eingeklappt werden. Anfang,
Schritt, Aufbau abspielen/Pause und Alle ausklappen erschließen die Hierarchie.
Die Suche erreicht auch zuvor eingeklappte Knoten und zeigt deren Strukturpfad.

2D: linke Maustaste ziehen zum Verschieben, Mausrad zum Zoomen am Mauszeiger.
3D: Ziehen zum Drehen, Umschalt/Rechts und Ziehen zum Verschieben, Rad zum Zoomen;
zusätzlich Auto-Rotation, Kamera folgt Auswahl und Auswahl zentrieren.
Die Auswahl bleibt beim Wechsel zwischen 2D und 3D erhalten.
Beschriftungen werden anhand von Zoom, Sichtbarkeit und Überlappung ausgewählt;
vollständige Namen stehen im Detailbereich und in der Suche.

Das Referenzmuster wurde über `src/routes/index.tsx`, `GraphEditor.tsx`,
`graphEngine.js`, `nodesApi.ts` und die zugehörigen Darstellungsstile untersucht.
Seine separate Supabase-Datenhaltung und Demo-Inhalte werden nicht importiert.
Das Bearbeiten des kanonischen Modells erfolgt weiter über die NIS-Editoren.

## Datenvertrag und Befunde

`hardware-graph.ts` projiziert die vorhandene SQL-Topologie und Engineering-
Funktionen. Die bisherige zweite Namensklassifikation in der radialen Ansicht
entfällt. Cluster und Systemrahmen kommen aus der gespeicherten Szene.
Exakte IDs unterscheiden auch gleichnamige Geräte. Gateways erscheinen als
tatsächliche Geräte; die virtuelle Projektwurzel ist als Struktur erkennbar.
Offene Zuordnungen bleiben offen. Technologie stammt aus Ports/Verbindungen,
niemals aus einer technischen Namensendung. Hardware-, Funktions- und
Strukturverbindungen werden getrennt dargestellt, alle ohne Pfeilspitzen.

Die 3D-Verteilung ist eine deterministische sphärische Darstellung der Hierarchie.
Sie definiert keine neuen Einbauorte und verändert weder Raumcluster noch
manuelle Positionen des Netzwerk-Editors. Maßgeblich bleibt
`SPATIAL_ARCHITECTURE_CONTRACT.md`.

## Laufzeit

Three.js und OrbitControls werden erst beim Wechsel auf 3D geladen.
Instanzierte Knotengeometrie und zusammengefasste Linien vermeiden einen
separaten Draw Call pro Gerät. Ohne Kamerabewegung, Auto-Rotation oder aktiven
Datenfluss wird nur bei Änderungen gerendert; außerhalb des sichtbaren Bereichs und bei verborgenem
Browser-Tab pausiert die Darstellung. Beim Schließen werden Controls, Observer,
Geometrien, Materialien und WebGL-Kontext freigegeben. Bei WebGL-Fehlern ist
eine direkte Rückkehr in die 2D-Ansicht verfügbar.
Die Kamera verwendet die dokumentierten
[OrbitControls](https://threejs.org/docs/pages/OrbitControls.html).

## Verifikation

Ursprünglich geprüfter Produktionsbuild: `8beeb19bd7c3`, 10.09.2026, 20:32:46 MESZ.
Produktionsbuild inklusive TypeScript erfolgreich.

14 gezielte Frontendtests bestanden: Hardwaregraph, bestehende Topologie und
Leitungskreuzungen. Die Graphprüfungen decken vollständige Geräteidentität,
bestätigte Zugehörigkeit, Funktionsmapping, offene Zuordnungen, Suche in
eingeklappten Zweigen, Technologie aus Daten statt Namen, zyklische physische
Verbindungen, deterministische Geometrie und tatsächliche Fit-Grenzen ab.

`frontend/scripts/verify-hardware-explorer.mjs` prüft im Chrome-Browser am Projekt
`network-project-20260910042736034-d11591d0`:

- 262 Hardwaregeräte, 260 physische Verbindungen; 323 Knoten einschließlich
  Struktur, 386 Knoten in Combined.
- 2D-Fit innerhalb des Viewports, Mausziehen, Zoom ohne Seitenscrollen,
  Suche, Auswahl, Ein-/Ausklappen und schrittweiser Aufbau.
- Echtes WebGL-Rendering, Kameradrehung per Maus und Auto-Rotation,
  Auswahl beim Wechsel zwischen 2D und 3D, erneuter Renderer-Aufbau.
- Vollbild und Rückkehr zu 2D nach gezielt ausgelöstem WebGL-Kontextverlust.
- Anpassung des Explorers an ein 800 Pixel breites Fenster.
- Identische SQL-Topologie und Modellversionen vor/nach dem Durchlauf;
  keine Schreiboperationen des Explorers. Die bestehende Workflow-Kopfzeile
  setzt lediglich `active_workflow_step: network_editor` im Ansichtskontext.
- Keine JavaScript-Laufzeitfehler.

Ergebnis: `backend/runtime/hardware-explorer-browser-result.json`.
Sichtprüfung: `backend/runtime/hardware-explorer-2d.png` und
`backend/runtime/hardware-explorer-3d.png`.

## Erweiterung vom 11.09.2026: Kommunikation und Knotennavigation

Nutzerauftrag: Linien an der zugewandten Knotenseite anschließen, mehrere Knoten
mit „und“ suchen, gerichtete Beziehungen animieren, Zweige per einfachem Klick
öffnen/schließen, Eigenschaften im Graphen sowie optional Beleuchtung anzeigen.

- 2D und 3D verbinden die einander zugewandten Kreis-/Kugeloberflächen direkt.
  Die bisherige Kurve zurück zur Graphmitte entfällt. Es gibt keine Pfeilspitzen.
- `Motorsteuerung und Infotainment` sucht beide Namen gemeinsam und erhält ihre
  Strukturpfade. Anführungszeichen schützen Namen, die selbst „und“ enthalten.
  Die Suche bleibt eine Teilnamensuche; nicht gefundene Teilanfragen werden angezeigt.
- Der einfache Klick wählt aus und öffnet/schließt vorhandene Unterknoten, auch
  aus der auf eine Ebene begrenzten Anfangsansicht. In Hardware/Combined werden
  Sensoren und Aktoren nur anhand ihrer ausdrücklich gespeicherten `systemOwnerId`
  unter der zugehörigen ECU geführt, und nur innerhalb desselben gespeicherten
  Systemrahmens. In Combined liegen Funktionen unter ihrer kanonisch zugeordneten
  Hardware. Diese Projektion verändert keine Raumcluster, Einbauorte oder Busse.
- Die auswählbare Eigenschaftskarte zeigt Typ, Zuordnung, Anschlüsse/Techniken,
  Lifecycle/Version, Beschreibung sowie ein- und ausgehende Kommunikationswege.
  Eine Beziehung ohne bekannte Richtung wird separat als „Richtung offen“ gezählt.
- Die 3D-Beleuchtung ist abschaltbar. Kugeln verwenden bei aktivem Licht
  [MeshStandardMaterial](https://threejs.org/docs/pages/MeshStandardMaterial.html)
  mit [HemisphereLight](https://threejs.org/docs/pages/HemisphereLight.html) und
  zwei gerichteten Lichtquellen; ansonsten bleibt die flache Farbdarstellung.

### Herkunft und Bedeutung der Kommunikationslinien

Die Richtung stammt aus Nachrichtentransporten der Routing-Tabelle und aus
kanonischen `COMMUNICATES_WITH`-Beziehungen mit expliziter Richtung. Reine
physische Busverbindungen erzeugen keinen erfundenen Nachrichtenaustausch.
Hardware-, Interface- und Funktionszuordnungen werden ausschließlich über IDs
aufgelöst. In Functions wird ein Routing-Endpunkt nur bei passender expliziter
Interface-/Funktions-/Hardwarezuordnung angezeigt. Relations- und Interfaceabfragen
laden alle Seiten, nicht nur die ersten 100 Datensätze.

Mehrere Routen zwischen demselben Sender und Empfänger teilen sich eine Linie;
die Details nennen die einzelnen Routen und ihren Status. Gegenrichtungen bleiben
separate Beziehungen. Abgelehnte/ersetzte Routen und leere Routing-Platzhalter
werden nicht als Kommunikation dargestellt. Veraltete oder ungeprüfte Wege
bleiben als Absicht sichtbar, ohne aktive Datenpunkte; Linien mit mindestens
einem gültigen Weg sind türkis. Fehlende Richtungsangaben erzeugen keine Animation.

Bewegte Punkte laufen vom gespeicherten Sender zum Empfänger. Sie visualisieren
die modellierte Richtung, keinen aufgezeichneten oder gerade simulierten Verkehr;
ihre Geschwindigkeit ist keine Messung der Zykluszeit. Der Schalter „Datenfluss“
pausiert die Animation. Die Betriebssystempräferenz für reduzierte Bewegung wird
berücksichtigt. „Kommunikation“ blendet diese Linien unabhängig von physischen
Busverbindungen ein/aus. Bei Auswahl werden deren Kommunikationspartner betont.

### Nachweis

Produktionsbuild `fe5facfe6e12`, gebaut am 11.09.2026 um 05:58:08 UTC und lokal
auf Port 13500 gestartet. TypeScript und Produktionsbuild erfolgreich.

11 Graph-Tests bestanden, einschließlich zugewandter Endpunkte in allen
Quadranten/3D, stabiler Identitäten, räumlicher Mitgliedschaften, UND-Suche,
Suchtreffern hinter eingeklappten Zweigen, gezieltem Öffnen einer Ebene sowie
Senderichtung, unbekannter Richtung, veralteten Wegen und Funktionszuordnung.

Beide Chrome-Prüfungen bestanden:

- `frontend/scripts/verify-hardware-explorer.mjs`: bestehende Bedienung, Fit,
  Verschieben/Zoom, Aufbau, 2D/3D-Umschaltung, Kameradrehung, Vollbild,
  Wiederaufbau nach Kontextverlust und schmales Fenster.
- `frontend/scripts/verify-hardware-relationships.mjs`: Mehrfachsuche und
  Kommunikation am realen Projekt, darunter `RT-FBF09272`, Motorsteuerung →
  Infotainment. Sichtbar bewegte Datenpunkte bei stillstehender Kamera, statisches
  Bild nach Abschalten, tatsächlich veränderte Kugelbeleuchtung, Canvas-Klick zum
  Aufklappen, erneuter Klick zum Einklappen, ECU-Unterknoten, Overlay und reduzierte
  Bewegung. Topologie und Modellversionen vor/nach der Prüfung identisch;
  keine JavaScript-Laufzeitfehler.

Ergebnisse und visuelle Prüfung:
`backend/runtime/hardware-relationships-browser-result.json`,
`backend/runtime/hardware-relationships-2d.png` und
`backend/runtime/hardware-relationships-3d-lit.png`.

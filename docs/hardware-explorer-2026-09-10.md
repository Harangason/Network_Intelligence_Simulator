# Hardware-Topologie: 2D und 3D

Nutzerauftrag: den vorhandenen radialen Hardware-View um die Fähigkeiten des
Musters `H:/OneDrive/Download/project-3d/` ergänzen.

## Übernommene Bedienfunktionen

Die bestehende Umschaltung Hardware / Functions / Combined enthält nun zusätzlich
2D / 3D, Suche, alphabetische Trefferlisten, Typ- und Bustypfilter, einen
Detailbereich mit navigierbarem Zuordnungspfad, Vollbild und echtes Einpassen.
Zweige können per Doppelklick oder Detailaktion eingeklappt werden. Anfang,
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
separaten Draw Call pro Gerät. Ohne Kamerabewegung/Auto-Rotation wird nur bei
Änderungen gerendert; außerhalb des sichtbaren Bereichs und bei verborgenem
Browser-Tab pausiert die Darstellung. Beim Schließen werden Controls, Observer,
Geometrien, Materialien und WebGL-Kontext freigegeben. Bei WebGL-Fehlern ist
eine direkte Rückkehr in die 2D-Ansicht verfügbar.
Die Kamera verwendet die dokumentierten
[OrbitControls](https://threejs.org/docs/pages/OrbitControls.html).

## Verifikation

Aktiver Produktionsbuild: `8beeb19bd7c3`, 10.09.2026, 20:32:46 MESZ.
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

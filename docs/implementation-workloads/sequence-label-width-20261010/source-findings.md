# Markierte Sequenzbeschriftung

Projekt: 20261009072206008-4bb505f1; Simulation SEQUENCE.
Nutzer: Die lange Beschriftung „Ultraschall…“ überlagert Pfeile und Balken.
Quelle: bereitgestelltes Browserbild; keine neue Laufzeitprüfung durchgeführt.

Gemeinsamer Renderer: frontend/src/features/simulation/ui/e2e-sequence-diagram.tsx.
SequenceDiagramModel.events liefert route, technology, status und technische Details.
Der Renderer zentriert die Beschriftung bisher über der ganzen Pfeillänge und
begrenzt sie nur auf 64 Zeichen, unabhängig vom 184px-Teilnehmerabstand.
Bei mehreren Hops liegt die Mitte auf einer Lebenslinie; der Text bei y-8
überschneidet zudem den Aktivierungsbereich y-9 bis y+9.

Soll: sichtbare Beschriftung und technische Unterzeile innerhalb eines einzelnen
Zwischenraums, mit Abstand zu Lebenslinien, Aktivierungen und Pfeilen. Lange Texte
mit nativer Ellipse; volle Beschriftung weiterhin per Tooltip und Auswahl abrufbar.
Selbstnachrichten behalten ihre Schleife; ihre Beschriftung liegt rechts davon.
Dies gilt im bestehenden gemeinsamen Renderer für SIMULATED und OBSERVED.

Bestehende Abdeckung: frontend/e2e/studio-export-controls.spec.ts umfasst Auswahl,
transparente Hervorhebung und Aktivierungen. Pixelabhängige Beschriftungsbreite und
mehrere Teilnehmer/Selbstnachrichten sind darin noch nicht geprüft. Keine zweite
Registry und keine neuen Testdateien angelegt. Tests ausdrücklich vom Nutzer pausiert.
Produktivlieferung bleibt vom vollständigen PASS und dem offenen Image-Budget abhängig.

# Verzeichnisstruktur des Network Simulators

Diese Übersicht beschreibt den vorhandenen Arbeitsbaum des kanonischen Projekts
`I:\PycharmProjects\My_first_Network_Simulator`. Erstellt am 02.10.2026 für den
Auftrag „genaue Verzeichnisstruktur mit Inhaltsbeschreibung je Datei“.

## Übersicht öffnen

- [Durchsuchbarer Dateikatalog](index.html): Pfad, Inhalt, Klassen/Funktionen,
  Imports und erkannte HTTP-Routen; Suche und Dateitypfilter funktionieren offline.
- [Verzeichnisbaum](directory-tree.txt): erfasste Dateien, leere Verzeichnisse
  und explizite Ausnahmen an ihren tatsächlichen Pfaden.
- [Dateiinhalte als Markdown](file-descriptions.md): ausführliches Nachschlagewerk
  nach Verzeichnissen mit Quellenlinks und Symbol-Zeilennummern.
- [Strukturierte Daten](inventory.json): exakte Pfade, Dateigrößen, SHA-256,
  Inhaltsbelege, Parserstatus und Ausnahmen.
- [Quellengeprüfte Architekturübersicht](analysis.md).
- [Automatischer Scannerbericht](scan/audit.md): getrennte Stil- und
  Docstring-Befunde; keine Funktions- oder Releasefreigabe.

## Grenzen

Der Katalog enthält Inhaltsbeschreibungen, keine vollständigen Dateikopien.
Vorhandene englische Modultexte und Testnamen sind Originalbelege. Die zentralen
Architekturbeschreibungen wurden gezielt am Quellcode geprüft; die Dateiübersicht
extrahiert zusätzlich Struktur mit Python-AST und dem TypeScript-Compilerparser.
Das ist keine semantische Vollprüfung aller Implementierungen.

Geheimnisdateien werden nicht gelesen. Von Konfigurationen erscheinen
Feld-/Bereichsnamen, keine Werte. Abhängigkeiten, generierte Laufzeit-/Builddaten,
lokale Arbeitsarchive und Scanner-Ausgaben werden sichtbar ausgenommen und
nicht rekursiv aufgelistet. Symlinks/Junctions werden nicht verfolgt. Binärdateien
und Dateien über 2 MB erhalten einen offenen Inhaltsstatus. Parserfehler sind
dateiweise ausgewiesen. Daher ist „vollständig“ auf den ausdrücklich ausgewiesenen
Erfassungsumfang begrenzt.

Git-Commit und Erfassungszeit stehen im jeweiligen Inventar. Lokale Änderungen
werden berücksichtigt. Parallele Änderungen nach der Erfassung können den Stand
verändern; einzelne Hashes erlauben den Vergleich. Die Scannerprüfung verwendet
eigene Ausschlussregeln und kann deshalb eine andere Dateianzahl ausweisen.
PEP-8-Befunde beziehen sich auf den expliziten Basiswert 79 Zeichen, nicht auf
eine behauptete projektspezifische Formatierungsfreigabe.

Es wurde kein Anwendungsverhalten geändert und keine Produktdatenbank abgefragt.
Anwendungstests und Deployment sind für diesen Dokumentationsauftrag nicht
ausgeführt worden.

## Erneut erstellen

Vom Projektverzeichnis aus:

```powershell
python docs/project-scanner/directory-structure/build_inventory.py
node docs/project-scanner/directory-structure/parse_typescript.cjs
python docs/project-scanner/directory-structure/build_inventory.py
```

Der erste Python-Aufruf erfasst die Dateiliste. Der Node-Aufruf liest alle
erfassten JavaScript-/TypeScript-Dateien mit dem unter `frontend/node_modules`
installierten Compilerparser. Der abschließende Python-Aufruf integriert die
Parserdaten. Projektmodule werden dabei weder importiert noch ausgeführt.

Scanner-Befunde sind separat und werden durch diese drei Befehle nicht erneuert.

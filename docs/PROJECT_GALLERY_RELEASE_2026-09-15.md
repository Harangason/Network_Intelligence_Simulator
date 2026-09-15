# Startseite und Projektübersicht

## Umsetzung

- Die vier markierten Aktionen Neu, Clear, Speichern und Öffnen wurden aus der
  Marketing-Kopfzeile entfernt. Projekt aktualisieren bleibt verfügbar.
- Die Orbitgrafik besitzt umlaufende Knoten und einen sanft pulsierenden Kern.
  Die Inspect-Balken bewegen sich. Animationen lassen sich pausieren und werden
  bei aktivierter Systemeinstellung für reduzierte Bewegung abgeschaltet.
- Start simulating führt zu `/projects`. Die übrigen Marketing-Einstiege ins
  Studio führen ebenfalls zur Projektübersicht.
- Gespeicherte Projekte erscheinen als Kacheln mit Namen, vorhandener
  Kurzbeschreibung, aktuellem Arbeitsschritt, Status und Änderungsdatum.
  Suche und Nachladen weiterer Projekte sind vorhanden. Die Suche bezieht sich
  auf die bereits geladenen Projekte; dieser Umfang wird angezeigt.
- Die Plus-Kachel speichert einen neuen leeren Projektkontext mit eigener ID
  und öffnet dessen Engineering-Wizard. Das Ursprungsprojekt bleibt bestehen.
  Ein wiederholter Speicheraufruf nach verlorener Antwort benutzt innerhalb
  desselben Anlageversuchs dieselbe Projekt-ID.
- Die Liste liest den tatsächlichen Backendbestand; sie ist kein nur lokal im
  Browser gespeichertes Kachelverzeichnis. Ohne Beschreibung erscheint ein
  neutraler Hinweis auf Modell, Kommunikation und Simulation.

## Prüfung

- Isolierter SQL-Test für Projektliste, gespeicherten Namen, leere Projektanlage,
  wiederholtes Speichern, Paginierung und ungültigen Offset bestanden.
- Zwei zusätzliche echte Browserfälle auf Produktionskandidat R2 bestanden:
  Navigation, vorhandenes Projekt, neue Projekt-ID, Wizardöffnung, Reload,
  mobile Breite sowie Animation, Pause und reduzierte Bewegung.
- Die visuelle Nachkontrolle fand in R1 eine globale SVG-Größenüberschreibung;
  R2 begrenzt die Pfeile und prüft Pfeilbreite sowie Kartenhöhe im Browser.
- Screenshots: `backend/test-output/gallery-desktop.png` und `gallery-mobile.png`.

## Releasebeleg

Die abschließende Gesamtprüfung ist PASS. Maßgeblich ist
`backend/test-output/gallery-release-gates/383272a585b8/receipt.json`.

- TypeScript und 341 Frontendtests bestanden.
- 1646 Backendtests bestanden, 3 übersprungen; eine bekannte Pydantic-Warnung.
- Alle 19 Browser-E2E-Fälle bestanden, keine übersprungenen oder instabilen Fälle.
- Beide HTTP-Neun-Stufen-Läufe bestanden: kleiner Lauf 8 Routen / 18 Signale,
  großer Lauf 838 Routen / 1404 Signale, jeweils Conformance PASS.
- Das Produktionsimage wurde zuvor im Vorbereitungslauf `be38cb76ecfb` gebaut
  und unverändert als Image-Eingabe des vollständigen Gates geprüft.
- Image `sha256:601e55ab77122a2518144026bd0262b09be4f16f76fafeadd821a33bf7f7c44a`
  am 15.09.2026 ausgeliefert; Build `aa9541b15189`.
- Konsistentes Datenbankbackup mit 254745258 Bytes erstellt; SHA-256
  `d14a218ccc4e71d84066b5293c429ac59b4d26361abb1cb07c39c4b2d125af32`.
- 18 Auslieferungsprüfungen bestanden: Vergleich des aktuellen Projekts
  `network-project-20260910042736034-d11591d0`, Volumes, Datenbankimage,
  Laufzeit-/KI-/GPU-Einstellungen und geprüfte Quellidentität auf beiden Ports.
  Dieses Projekt war vor der Auslieferung bereits ohne kanonische Modellobjekte.
- Die neue Projektseite antwortet im Produkt mit HTTP 200.
- Die eigenen vorbereiteten und finalen Testcontainer wurden entfernt;
  Nachweise und Backup bleiben unter dem Gate-Verzeichnis erhalten.

Der erste vollständige Kandidat R1 wurde vor Auslieferung wegen des bei der
Sichtprüfung gefundenen SVG-Fehlers abgebrochen. Nur R2 besitzt den hier genannten
vollständigen Release-PASS. PREPARED-Images allein sind keine Releasefreigabe.

Quelle R2: `aa9541b151897e8242eca548136bff5c10ad90d1af239583a618f3ca02a1fda7`.
Prüfmanifest: `4e2acdfa40dd649e7d641636a9a1489f1db940400ceeb231d5639b1f09c98f6d`.
Neun Dateien ergänzen den vorherigen PASS `3990c4575c55`; der eingefrorene
Lieferumfang ist in `project-gallery-release-scope.json` des Kandidaten erfasst.

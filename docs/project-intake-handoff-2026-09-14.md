# Projektbeschreibung und erreichbare Prüfung vor dem Start

Stand: Implementiert, vollständig geprüft und am 14.09.2026 installiert.
Release-Prüfung `15ad5944b936`: PASS. Build `9acaa3f89b46`.

## Befund

Der bisherige Übergang übernahm die Anforderung in `taskText`, zeigte sie aber erst
auf der späteren Wizardseite „Aufgabe“. Die erste Seite „Projektname“ bot keine
Projektbeschreibung. Das erzeugte den Eindruck einer verlorenen Anforderung.
Die letzte Karte „Statusübersicht“ war vor einem START immer deaktiviert; dadurch
war keine abschließende Vorschau mit konkreten fehlenden Angaben erreichbar.

## Änderung

- Die erste Seite enthält eine editierbare Projektbeschreibung. Sie verwendet
  denselben Zustand wie der Aufgabentext; beide Eingabestellen und die Übernahme
  an den Agenten bleiben konsistent. Intake-Änderungen bleiben im projektgebundenen
  Entwurf im Browsertab erhalten.
- Die letzte Seite ist vor dem START als Entwurfsprüfung erreichbar. Sie zeigt
  Projektname, Beschreibung und fehlende Voraussetzungen mit Navigation zur
  zugehörigen Eingabe. Erst der ausdrückliche Start führt den Auftrag aus.
- Startbutton und Starthandler verwenden dieselben Voraussetzungen einschließlich
  Kommunikationsanzahlen und Bereitschaft der geladenen Wizardpräferenzen.
  Eine ungenannte Ventilanzahl wird nicht automatisch ergänzt.
- Der bisherige Start über „Übernehmen“ auf der Geräteumfangseite bleibt erhalten.
  Ein bereits gespeicherter Auftrag bleibt an seine bestehende Revision gebunden.

## Nachweis und Grenze

Zwei echte Browserfälle bestehen im isolierten Entwicklungsstack `490c4dcbdcbe`:
Workspace und Seitenassistent, kompakte Projekt-ID, gespeichertes Gespräch,
erneutes Laden der Aktionskarte, unmittelbar sichtbare Projektbeschreibung,
erreichbare Entwurfsprüfung bei fehlender Ventilanzahl, gesperrter Start bei
unvollständigem Auftrag, Geräteumfang, Textänderung und Reload. Vor START entstehen
keine Hardwareobjekte. Laufzeit: 8,8 Sekunden für beide Fälle.

Ein zusätzlicher realer Browserlauf mit vollständig ausgefülltem kleinen Auftrag
prüft den neuen Button auf der letzten Seite: Button aktiv, START HTTP 200,
Projektbeschreibung unverändert im `wizard_context.task`, Wechsel aus der Vorschau
in den Auftragszustand. Nachweis: `backend/test-output/intake-handoff-diagnostics/490c4dcbdcbe/review-start.json`.
Vorläufe dieses separaten Diagnoseskripts scheiterten am noch nicht bereiten
Diagnose-Stack bzw. an einem zu strikten Textfeld-Selektor. Nach Bereitschaft und
Verwendung des eindeutigen Feldplatzhalters besteht der Lauf.

Der erste Diagnoselauf lud die Seite noch vor der bestätigten verzögerten
Gesprächsspeicherung neu und verlor deshalb die sichtbare Chatantwort. Der Test
wartet jetzt auf die tatsächliche erfolgreiche History-PUT-Antwort, bevor er
die Wiederherstellung gespeicherter Karten prüft. Dieser Nachweis behauptet
keine sichere Wiederherstellung einer noch unbestätigten Gesprächsspeicherung.

Der Releasekandidat basiert ausschließlich auf dem vorherigen PASS-Stand
`6edcdd977ed0`. Deklarierte Änderungen: `agent-chat-core.tsx` und
`project-intake.spec.ts`. Andere Änderungen im gemeinsamen Arbeitsverzeichnis
werden nicht mit ausgeliefert. Die Quelle bleibt während des Gates eingefroren.

## Abgeschlossene Freigabe

Alle sieben Gateprüfungen bestanden: TypeScript, 331 Frontendtests,
1552 Backendtests (2 übersprungen; bekannte Pydantic-Warnung), Produktionsbuild,
7 Browser-E2E-Fälle sowie kleine und große HTTP-Akzeptanz bis Stufe neun.
Der gesamte Browserabschnitt dauerte 11,9 Minuten, die Backendtests 16 Minuten.
Die zusätzlichen Einstiege wurden auch im endgültigen Produktionsimage geprüft.

Installiertes unveränderliches Image:
`sha256:ddde26af41ccd1704642d3223419faa748ffbe2652189a4ee8bacca62583420f`.
Quellabgleich: genau 2 deklarierte geänderte Dateien, 1502 unverändert.
Vor Installation: konsistentes Datenbankbackup, 254571284 Bytes.
Nach Installation: 18/18 Kontrollen bestanden (Image, Bereitschaft und Build auf
beiden Produktports, Projektbestand, Revision, Jobs, Snapshots, Datenbankimage,
Volumes, Laufzeiteinstellungen und GPU-Konfiguration).

Nachweise liegen unter `backend/test-output/intake-handoff-release-gates/15ad5944b936`:
`receipt.json`, `source-provenance.json`, `product-backup.json`,
`product-deployment-verification.json`. Es wurden keine Testaufträge im Produkt
angelegt und keine fachlichen Voraussetzungen zugunsten eines Erfolgsstatus entfernt.

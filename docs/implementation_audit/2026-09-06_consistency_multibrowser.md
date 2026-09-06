# Konsistenz, Workflow und gleichzeitige Browserzugriffe

Stand: 6. September 2026. Geprüft und geändert wurde ausschließlich das kanonische
Projekt `I:\PycharmProjects\My_first_Network_Simulator`.

## Ergebnis

Die gefundenen und unten beschriebenen Fehler sind behoben. Der gemeinsame
Projektzugriff wurde mit getrennten Chrome- und Edge-Prozessen nachgewiesen.
Der vollständige Workflow wurde mit einem CAN-FD-Testprojekt bis zur
Intelligence-Bewertung ausgeführt. Das Ergebnis ist ein überprüfter Stand für
diese Szenarien; es ist keine Aussage, dass sämtliche möglichen Modelle,
Technologien und externen Integrationen fehlerfrei sind.

Der fachliche Abgleich berücksichtigt die vorhandenen Architektur- und
Model-View-Dokumente, die beigefügte ECU-Hierarchie und den Gesprächskontext
„MCP erklärt“. Eine ECU darf mehrere unterschiedliche Funktionen besitzen.
Logische Funktionsschnittstellen und physische Hardwareports bleiben eigene
Objekte. Ein neuer MCP-Server war für die angefragte Fehlerbehebung nicht nötig.

## Befunde und Änderungen

| Bereich | Nachgewiesenes Problem | Änderung |
| --- | --- | --- |
| Projektidentität | Eigene IDs mit `network-project-` wurden beim Verkürzen verändert. Ein global gemeinsam verwendetes Workflow-Promise konnte die Antwort des falschen Projekts liefern. | Nur tatsächlich generierte Zeitstempel-IDs werden verkürzt; parallele Workflow-Anfragen sind nach Projekt getrennt. Projektwechsel ändern die URL; der neue Projektlink erhält die Identität. |
| Gleichzeitiges Speichern | Veraltete Editoren konnten neuere Objekt- und Routingdaten überschreiben. | Objektversionen, Routingrevisionen und Inhaltstoken für Parameter/Topologie werden verglichen. Der Server antwortet bei Konflikten mit 409. Offene Entwürfe bleiben erhalten. |
| Transaktionen | Einzelne Repository-Commits trennten Modelländerung, Synchronisierung und Invalidierung. Ein späterer Fehler hinterließ Teiländerungen. | Ein Engineering-Schreibrequest verwendet eine Transaktion, verschachtelte Savepoints und eine PostgreSQL-Sperre je Projekt. Fehler bei der Invalidierung führen zum Rollback. |
| Request-Kontext | Der aktivierte Projektkontext wurde nicht zuverlässig zurückgesetzt. | Teardown stellt den vorherigen Kontext wieder her. |
| Topologie | Wiederholte Synchronisierung konnte IDs gleichartiger erzeugter Interfaces vertauschen; eine volle Sperrentabelle konnte noch verwendete Sperren entfernen. | Generierte Ports behalten ihre IDs. Die begrenzte Sperrentabelle verwendet bestehende Sperren weiter, ohne sie zu entfernen. HTTP-Zugriffe verwenden die Datenbanksperre. |
| Workflow-Fortsetzung | Nach Routingänderungen konnte eine unverändert bestätigte Topologie dauerhaft `OUTDATED` bleiben. Kanonische Änderungen durch Sync invalidierten nicht zuverlässig das Engineering-Modell. | Bestätigung aktualisiert den Workflowstatus; tatsächliche Modelländerungen durch Sync invalidieren abhängige Ergebnisse. |
| Layouts | Speichern einer Ansicht löschte Layouts anderer Ansichten derselben Version. | Löschbereich enthält jetzt Projekt, Topologieschlüssel und Layoutversion. |
| ECU-Hierarchie | Jede ECU mit mehr als einer Funktion wurde als Funktionsdopplung gezählt. | Nur gleiche normalisierte Funktionsnamen innerhalb derselben ECU werden als Dopplung gezählt. |
| Objektanlage | Nicht angegebene Felder überschrieben Datenbankdefaults mit `NULL` beziehungsweise `{}`. Hardwareports erhielten ungültige Ausgangswerte. | Nur übergebene Felder werden eingefügt; `UNMAPPED` und leere Listen bleiben gültige Datenbankdefaults. |
| Objekt-Wizard | Der letzte „Weiter“-Klick konnte durch Wiederverwendung des Submit-Buttons bereits speichern. | Eigene Button-Identitäten und eine Prüfung im Submit-Handler halten Prüfschritt und Speichern getrennt. |
| Editorstabilität | Späte Listenantworten konnten nach einem Registerwechsel die falsche Objektliste anzeigen. Paginierte Anfragen konnten beim Projektwechsel IDs mischen. | Veraltete Antworten werden ignoriert; jede paginierte Abfrage behält ihr Ausgangsprojekt. Schreibtimeouts berücksichtigen längere Berechnungen. |
| Import | Der Browser griff auf eine fest eingetragene lokale Backendadresse zu. | Import verwendet denselben Origin und Proxy wie die übrige Engineering-API. |
| Simulation | Derselbe fertige Snapshot konnte parallel mehrfach gestartet werden. Startdaten konnten von seiner Konfiguration abweichen. Das Signalmodell wurde erst beim Lauf aus dem aktuellen Projekt gelesen. | Atomare Snapshotreservierung; der Job erhält ausschließlich die eingefrorene Konfiguration. Modell- und Transportdaten werden beim Snapshotaufbau gespeichert. |
| Transportkonfiguration | Der Workflow konnte vereinfachte Browser-Kommunikationen verwenden. Der alternative Routing-Builder konnte wegen ungeeigneter Interfacefilter ohne ausführbare Ports bleiben. | Workflow-Snapshots bauen den Transport serverseitig aus freigegebenen aktuellen Routen. Nutzlast, Zyklusanforderungen und Bitraten verwenden die Auflösung der Kapazitätsberechnung; referenzierte Ports werden ausführbar projiziert. Historische/veraltete Routen werden ausgeschlossen. |
| Ergebnisse | Ein gekürzter Joblisteneintrag verdeckte vollständige Snapshotdaten. Die UI zeigte trotz gespeicherter Messwerte keine Runtime-Analyse. | Jobübersicht und Snapshotdetails werden zusammengeführt, auch beim Laufvergleich. |
| Tests und Startdiagnose | Die Backendtests ließen sich vom Projektroot nicht vollständig sammeln; ältere DB-Fixtures waren nicht wiederholbar. Zwei deutsche Clusteringbegriffe führten zu falschen Ersatzclustern. Eine unzugängliche Konfigurationsdatei konnte die Startdiagnose abbrechen. | Testpfad und isolierte Fixtures korrigiert; Begriffe ergänzt; Dateizugriffsfehler abgefangen. README nennt die unterstützten Python-Versionen 3.12/3.13. |

## Verifikation

- **461 Backendtests bestanden**, einschließlich echter PostgreSQL-Transaktionen;
  keine übersprungenen Tests beim abschließenden Lauf mit Testdatenbank.
- **109 Frontendtests bestanden**, einschließlich Projektisolation und Ergebniszusammenführung.
- TypeScriptprüfung und Next.js-Produktionsbuild mit Webpack erfolgreich.
- Keine doppelt registrierten Flask-Kombinationen aus URL und HTTP-Methode.
  Historische Routingrevisionen sind fachliche Historie und werden nicht pauschal gelöscht.
- Sechs parallele Änderungen derselben Objektversion: ein Erfolg, fünf Konflikte.
  Vier parallele Routingänderungen: ein Erfolg, drei Konflikte.
- Vier parallele Starts desselben Snapshots: ein Job, drei Konflikte.
- Vier parallele Topologiesynchronisierungen: identische IDs ohne zusätzliche Objekte.
- Echte Browser: Chrome **152.0.7977.82**, Edge **152.0.4191.62**.
  ECU-Anlage über alle Wizard-Schritte, beide Editoren auf derselben ID,
  Fremdänderungshinweis, 409 bei veraltetem Speichern, unveränderter Entwurf.
  Alle neun Workflowansichten und Einstellungen laden ohne JavaScriptfehler.
- Frisches CAN-FD-Projekt mit zwei ECUs, Funktionen, Interfaces, Nachricht und Signal:
  Routing freigegeben, Topologie bestätigt, Kapazität berechnet, Preflight erfolgreich,
  Simulation abgeschlossen, Signalverlauf und Ergebnisse sichtbar, Intelligence bewertet.
  Der Lauf erzeugte **201 Frames**, keine Drops und keine Timeouts. Fachliche Warnungen
  werden weiterhin angezeigt; sie wurden nicht unterdrückt, um einen grünen Status zu erzeugen.

Maschinenlesbare Details: [Verifikation](2026-09-06_verification.json).
Screenshots: [Konflikt in Edge](2026-09-06_multibrowser.png),
[vollständige Ergebnisansicht](2026-09-06_results.png).

## Wiederholen

Backendtests vom Projektroot, mit einer ausschließlich für Tests vorgesehenen Datenbank:

```powershell
$env:ENGINEERING_TEST_DATABASE_URL = 'postgresql://TESTBENUTZER@TESTHOST:TESTPORT/TESTDB'
backend/.venv/Scripts/python.exe -m pytest backend/tests -q
```

Frontendtests und Build aus `frontend`:

```powershell
npm ci
npm test
npm run build -- --webpack
```

Die Browsertests verwenden Playwright aus den Entwicklungsabhängigkeiten und
installiertes Chrome/Edge. Sie erzeugen Testdaten und sind ausdrücklich auf
eine isolierte Simulator-Instanz zu richten:

```powershell
# Aus frontend; URLs passend zur eigenen Testinstanz setzen.
$env:SIMULATOR_TEST_URL = 'http://127.0.0.1:13502'
node scripts/verify-collaboration.mjs

# Aus dem Projektroot: vollständiges Testmodell vorbereiten.
$env:SIMULATOR_TEST_BACKEND_URL = 'http://127.0.0.1:15051'
backend/.venv/Scripts/python.exe backend/tests/manual/prepare_browser_workflow.py
$env:SIMULATOR_TEST_PROJECT = (Get-Content backend/test-output/audit-flow-state.json -Raw | ConvertFrom-Json).project
node frontend/scripts/verify-simulation-workflow.mjs
```

Logs, Browserberichte und Screenshots werden unter `backend/test-output` abgelegt.
Für diesen Audit liefen PostgreSQL auf 15432, das Backend auf 15051 und die
Vorschauen auf 13501/13502. Diese Testdienste werden nach Abschluss beendet.

## Grenzen und Betriebszustand

Die bestehende Docker-Engine war auch bei der Abschlussprüfung nicht erreichbar
(`dockerDesktopLinuxEngine`-Pipe fehlt). Deshalb erfolgten die Tests mit einer
separaten PostgreSQL-18.4-Instanz und ausschließlich erzeugten Testprojekten.
Eine Bestandsdatenbereinigung oder Prüfung vorhandener Projektinhalte war damit
nicht möglich. Die Testdatenbank ersetzt nicht die eigentliche Projektdatenbank;
der reguläre Betrieb auf Port 13500 benötigt weiterhin die gestarteten Dienste.

Die Zusammenarbeit verwendet periodischen Abgleich und Konflikterkennung. Sie
führt gleichzeitig geänderte Felder desselben Objekts nicht automatisch zusammen.
Die Vergleichsfelder bleiben für ältere API-Clients optional; eigene Clients
müssen sie für Schutz vor veralteten Entwürfen mitsenden. Administrative
Import-/Ersetzungsaktionen sind keine gemeinsam verschmelzenden Editoren.

Die vorhandene Aufteilung zwischen TypeScript-Wizardlogik und Python-Domänenlogik
wurde nicht vollständig migriert. Die Python-Zentralisierung aus den ergänzenden
Architekturpapieren bleibt eine eigene größere Umstellung. Ebenso wurden keine
umfassenden Lasttests großer Projekte oder externen KI-Dienste durchgeführt.

## Nachtrag: MCP-Umsetzung

Die spätere [MCP-Abnahme](2026-09-06_agent_mcp.md) ergänzt diese Prüfung. Docker war wieder erreichbar; die reguläre Anwendung wurde nach Datenbanksicherung auf den geprüften Stand mit Schema 21 aktualisiert.

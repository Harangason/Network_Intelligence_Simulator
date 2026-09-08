# Speicherort für Traces und Ergebnisse

Im Studio unter **Einstellungen → Speicherort für Traces und Ergebnisse**:

1. Absoluten Ordnerpfad eingeben oder **Ordner auswählen** öffnen.
2. Optional **Pfad prüfen**: Schreibprobe und freier Speicher werden geprüft.
3. **Speicherpfad speichern**. Noch nicht vorhandene Unterordner werden angelegt.

Die Einstellung gilt ausschließlich für neue Läufe des aktiven Projekts. Jeder Lauf schreibt in `<Speicherpfad>/<Job-ID>/`. Die Job-Verwaltung merkt sich diesen Pfad dauerhaft. Bereits gestartete oder wartende Läufe, vorhandene Traces, Downloads und das Engineering-Modell bleiben unverändert. Ein Zurücksetzen auf den Standard löscht oder verschiebt keine Dateien. Ein ungültiger oder nicht beschreibbarer Pfad wird abgewiesen, nicht durch einen stillen Ersatzpfad kaschiert.

Die Konfiguration liegt im stabilen Runtime-Verzeichnis unter `storage/trace-storage.json`; die Job-Pfade stehen in `jobs/registry.json`. Diese Dateien nicht von Hand bearbeiten.

## Windows und Docker

Bei nativ unter Windows laufendem Backend sind erreichbare Windows-Ordner direkt wählbar. Der Browser schreibt nicht selbst Dateien, sondern lässt das Backend den gewählten Ordner prüfen und verwenden.

Beim derzeitigen Docker-Betrieb bleibt das zuverlässige Volume `networkis-runtime-data` der Standard; Traces liegen darin unter `/app/backend/runtime/traces`. Unterordner dieses Volumes lassen sich sofort auswählen. Windows-Pfade sind erst erreichbar, nachdem der betreffende Host-Ordner ausdrücklich eingebunden wurde. Es werden keine Laufwerke automatisch freigegeben.

Für einen vorhandenen, selbst gewählten Windows-Ordner, Beispiel `D:/NetworkIS-Traces`, im Projektverzeichnis in PowerShell:

```powershell
$env:NETWORKIS_TRACE_HOST_PATH = 'D:/NetworkIS-Traces'
docker compose -f docker-compose.networkis.yml -f docker-compose.trace-storage.yml up -d --no-deps networkis
```

Vor diesem einmaligen Neustart laufende Simulationen und Wizard-Läufe beenden lassen. Der Ordner muss bereits existieren; Docker legt nicht unbemerkt einen falsch geschriebenen Host-Pfad an. Bei späteren Compose-Starts dieselben beiden Dateien und dieselbe Umgebungsvariable verwenden. Normale Container-Neustarts behalten die bestehende Einbindung.

Danach erscheint `D:\NetworkIS-Traces` in der Ordnerauswahl. Unterordner können ebenfalls angegeben werden. Intern entspricht das `/trace-output`. Nur dieser zusätzliche Ordner wird eingebunden; die bisherige Runtime, Datenbank und alten Ergebnisse bleiben bestehen. Solange historische Jobs auf den Host-Ordner verweisen, muss er für ihre Downloads weiter unter derselben Einbindung erreichbar bleiben.

Ein nicht eingebundener Windows-Pfad, relative Pfade, Dateien statt Ordnern und Pfade außerhalb der verfügbaren Docker-Wurzeln werden verständlich abgewiesen. Bei einem Ausfall eines gewählten Datenträgers wird der neue Lauf nicht an einem unerwarteten Ort gestartet.

### Aktuelle Einschränkung auf diesem Rechner (8. September 2026)

Die Docker-Daemon-Prüfung zweier isolierter Windows-Testordner auf **I:** und **F:** scheiterte bereits beim Anlegen des Bind-Mounts mit `input/output error`. Deshalb wurde kein Windows-Ordner an den produktiven Container angebunden. Die Auswahl innerhalb des vorhandenen Docker-Volumes funktioniert und wurde bis zur realen Trace-Datei geprüft. Freie Windows-Zielordner können hier erst genutzt werden, wenn die Host-Dateifreigabe von Docker Desktop wieder funktioniert. Ein globaler Docker-/WSL-Neustart ist nicht Teil dieser Änderung, weil er auch andere laufende Projekte unterbrechen könnte.

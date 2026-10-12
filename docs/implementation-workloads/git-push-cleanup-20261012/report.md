# Git-Push-Bereinigung am 2026-10-12

Alle sechs Dateien ueber 100 MiB wurden erstmals im ungepushten Commit
0ecc11b6 am 2026-10-11 aufgenommen. Die bisherigen Ignore-Regeln erfassten
diese lokalen Arbeitsartefakte nicht. Der genaue damalige Staging-Befehl
ist aus Git nicht rekonstruierbar.

## Herkunft

Alle folgenden Pfade liegen unter docs/implementation-workloads/.

| Datei | Herkunft und Nachweis |
| --- | --- |
| studio-toolbar-trace-defaults-20261009/failed-candidate-fc5d3079141e.tar | Docker-Sicherung eines fehlgeschlagenen Kandidaten. archive_failed_candidate.py ruft docker image save auf; failed-candidate-archive.json dokumentiert Identitaet, Archivhash und Wiederherstellung. |
| stranded-capacity-channels-20261010/previous-production-42a674cad1bc.tar | Docker-Sicherung des frueheren Produktionsimages; archive_previous_production.py, previous-production-archive.json und storage-review.json. |
| automatic-channel-reassignment-20261010/previous-production-debee1861880.tar | Docker-Sicherung des frueheren Produktionsimages; archive_previous_production.py, previous-production-archive.json und storage-review.json. |
| wizard-simulation-continuity-20261007/native-preflight-browser.sql | PostgreSQL-Dump laut Dateikopf von pg_dump 16.15. profile_native_preflight_plugin.py spielt ihn zur Diagnose ausschliesslich in eine disposable Testdatenbank ein. Der urspruengliche Exportaufruf ist nicht belegt. |
| parameter-review-loop-20261008/human-completed-simulation.json | Workflow-/Simulationssnapshot mit workflow, snapshot und snapshots. coverage.md dokumentiert den abgeschlossenen realen Wizard und das Simulationsergebnis. Der genaue Erzeugungsaufruf dieser Datei ist nicht belegt. |
| wizard-simulation-continuity-20261007/workflow-polling-frozen-fixture.json | capture-workflow-polling-fixture.py exportiert neun Engineering-Tabellen aus der disposable E2E-Testdatenbank. profile-workflow-polling.py verwendet den eingefrorenen Diagnosedatensatz. |

## Bereinigung

Die sechs Dateien werden aus allen fuenf ungepushten Commits entfernt.
Gezielte .gitignore-Regeln halten sie und gleichartige Docker-Sicherungen
kuenftig lokal. Sonstige Commit-Inhalte, Autoren, Zeitstempel und Nachrichten
bleiben erhalten; die Commit-IDs aendern sich.

Die lokalen Dateien, Docker-Images, Archivbelege und offenen Arbeitsaenderungen
bleiben erhalten. Diese Repository-Bereinigung aendert kein Produktverhalten
und fuehrt kein Deployment oder Image-Cleanup aus.

Die urspruengliche Historie bleibt lokal unter
refs/backup/main-before-large-file-cleanup-20261012 erhalten.
Diese Sicherung enthaelt weiterhin die grossen Git-Objekte und soll nicht
gepusht werden. Plan, Commit-Zuordnung und Pruefergebnisse liegen lokal
unter .tmp/git-push-cleanup-20261012/.

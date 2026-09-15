# Projektablage und Laufbereinigung

## Auftrag

Standardablage: `I:\PycharmProjects\My_first_Network_Simulator\SAVED`.
Jedes Projekt erhält einen eigenen Ordner. Die Bestandsbereinigung erhält
insgesamt die fünf jüngsten Läufe, unabhängig von Projekt und Erfolgsstatus.
Projektmodelle werden dabei nicht gelöscht. Die Projektgalerie erhält eine
gesonderte Löschaktion mit Bestätigung.

## Umsetzung

- Standard-Speichern schreibt atomar `<Projekt-ID>/project.nis-project.json`.
- Neue Simulationen verwenden standardmäßig `<Projekt-ID>/runs/<Lauf-ID>`.
- Explizit gewählte Export- und Trace-Pfade bleiben unterstützt.
- Docker bindet `SAVED` als `/trace-output` ein. Runtime-Einstellungen,
  bestätigtes Agentenfeedback und Modellregistrierungen bleiben erhalten.
- Projektlöschen entfernt das kanonische Modell, zugehörige Aufträge und den
  geprüften Projektordner. Aktive Simulationen und Agenten verhindern die
  Löschung. Ein Löschvermerk verhindert Wiederanlage durch veraltete Tabs.
- Alte Laufbefunde werden vor der Bereinigung in `SAVED/_knowledge` gesichert.
  Sie sind Untersuchungsevidenz, keine ungeprüften Trainingslabels.

## Bestandsnachweise

- `runtime-evidence-20260915.json`: Inventar und kompakte Befunde von 698 Läufen.
- `retained-run-copy-proof.json`: SHA-256-Nachweise aller erhaltenen Dateien.
- `host-runtime-evidence-20260915.json`: zusätzliche lokale Laufordner.
- `organized-bundles.json`: unverändert verschobene bestehende Projektdateien.
- `all-models-before.json` / `all-models-after.json`: projektübergreifende
  Modell-Fingerabdrücke zum Nachweis des Datenerhalts.
- `project-migration.json`: Projektablage nach der Umstellung.
- `retention-applied.json` / `host-retention-applied.json`: tatsächliche Bereinigung.

## Prüfung und Freigabe

Gezielte SQL-Prüfungen laufen ausschließlich in isolierten Testdatenbanken.
Browserprüfungen decken Speichern, Abbruch der Löschung, endgültiges Löschen,
Erhalt anderer Projekte und Schutz gegen Wiederanlage durch veraltete Tabs ab.
Zusätzlich werden aktive Agenten und sichere Projektpfade geprüft.

Release 40972398d891: PASS und bereitgestellt.

- 1654 Backend-Tests bestanden, drei uebersprungen; 341 Frontend-Tests bestanden.
- 21 Browser-Tests bestanden; kleine und grosse HTTP-Neun-Schritte-Abnahme PASS.
- Grossfall: 838/838 Routen, 1404 Signale, keine fehlende Abdeckung, null fehlgeschlagene Routen.
- Image: sha256:32b7cbd80da75a9d5fde80e9ccd652bb5a3ff982e36c1253efa7b75794624c31.
- Bereitstellung: 20 Nachpruefungen PASS; bisherige Einstellungen und Mounts erhalten.
- 181 Projekte gespeichert; alle 121242 kanonischen Modelldatensaetze unveraendert.
- Insgesamt fuenf Laeufe erhalten: 32 Dateien per SHA-256 verifiziert, 24 Downloadpfade erreichbar.
- 87688484524 Bytes alte Produkt-Laufdateien und 1695879469 Bytes lokale Laufdateien entfernt.
- Bestaetigtes Feedback und Modellregistrierungen erhalten; kein automatisches Nachtrainieren.

Der vorherige Prueflauf wurde ersetzt, um den Endzustand `canceled` bei der Projektloeschung
korrekt zu behandeln. Fuenf Statusfaelle sichern die Unterscheidung aktiver und beendeter Jobs ab.

## Nachpruefung bestehender Datenbanken

Der produktive Speicherversuch deckte eine fehlende Upgrade-Version auf:
Die neue Tabelle `engineering_deleted_projects` war zwar im Schema enthalten,
wurde in einer bereits mit Version 26 markierten Datenbank aber uebersprungen.
Die additive DDL aus dem freigegebenen Image wurde nachgeholt; Speichern unter
SAVED wurde danach erfolgreich am aktuellen Projekt nachgewiesen.
Schema-Version 27 und ein isolierter Upgrade-Test sichern die automatische
Aktualisierung bestehender Datenbanken in der Header-Version ab. Diese Version
wurde mit PASS-Nachweis `416e20f03f9d` bereitgestellt; Schema-Version 27 und die
Loesch-Tabelle sind produktiv bestaetigt. Die erneute Retentionspruefung
bestaetigt weiterhin insgesamt fuenf Laeufe, 32 Dateien und 24 Downloadpfade.

## Zusaetzliche Projektbereinigung nach ausdruecklicher Bestaetigung

Am 15.09.2026 wurden auch 176 der 181 Projekte ueber die regulaere
Projektloeschung entfernt, einschliesslich Modelldaten und SAVED-Ordnern.
Erhalten bleiben die fuenf zuletzt geaenderten Projekte. Technische
Export-Zeitstempel der Speicherumstellung wurden anhand des vorhandenen
Backups auf die urspruenglichen Projektzeitpunkte zurueckgefuehrt;
spaetere Aenderungen wurden beruecksichtigt.

Drei weitere alte August-Projekte, die ausschliesslich als Importdateien
vorlagen, wurden nach Pfad-, Inhalts- und Hashpruefung ebenfalls entfernt.
SAVED enthaelt damit genau fuenf Projektordner sowie `_knowledge`.
Die Projektliste meldet fuenf Eintraege, die erhaltenen Projektdateien sind
unveraendert. Auch die fuenf Simulationslaeufe, 32 Dateien und 24 Downloadpfade
wurden nochmals erfolgreich geprueft.

Pruefbelege: `SAVED/_knowledge/project-retention-plan.json`,
`project-retention-evidence.json`, `project-retention-applied.json` und
`old-import-project-evidence.json`. Historische Befunde sind keine automatisch
bestaetigten Trainingsdaten. Vorhandene technische Datenbanksicherungen wurden
durch diese Bereinigung nicht geloescht.

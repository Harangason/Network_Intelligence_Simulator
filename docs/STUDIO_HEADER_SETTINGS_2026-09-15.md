# Studio-Kopfleiste und Protokollierung

Die Studio-Kopfleiste zeigt weder „Neu“ noch „Projekt aktualisieren“.
Die Projektanlage über die Plus-Kachel der Projektübersicht bleibt verfügbar.
„Clear“, „Speichern“, „Öffnen“, „Importieren“ und „Einstellungen“ bleiben erhalten.

Die bisherige Aktion „Loggen an/aus“ befindet sich jetzt unter
**Einstellungen → Agent-Protokollierung**. Der Schalter verwendet die vorhandene
Diagnose-API und zeigt den bestätigten gespeicherten Zustand an. Während des
Ladens und Speicherns ist er gesperrt. Fehler werden angezeigt; ein Fehler
setzt den sichtbaren Zustand nicht fälschlich auf „aus“.

Zusätzlich erhöht die Version das Datenbankschema auf 27, damit bestehende
Datenbanken die bereits eingeführte Tabelle `engineering_deleted_projects`
erhalten. Ein isolierter Migrationstest beginnt beim Zustand der Version 26,
prüft die Anlage der Tabelle und den unveränderten vorhandenen Projektkontext.

Der gezielte Browser-Test prüft die entfernten Kopfleistenaktionen sowie
Umschalten, Neuladen und den tatsächlich gespeicherten Protokollzustand.
Er hat gegen das Produktionsimage `b8ae6128252408cd877e86788150d0ecb9873e48ba46fdee2ea5cfbea2806ed1`
bestanden. Die vollständige Release-Prüfung `416e20f03f9d` ist PASS:
TypeScript, 341 Frontend-Tests, 1655 Backend-Tests (3 übersprungen),
22 Browserfälle sowie kleine und große HTTP-Durchläufe über alle neun Stufen.
Der große Durchlauf erfasst 838 von 838 Routen und 1404 Signale ohne
fehlgeschlagene Route. Fachliche Warnungen bleiben dabei sichtbar;
der Testnachweis ersetzt keine funktionale Timing-Freigabe.

Das exakt geprüfte Image wurde am 15.09.2026 bereitgestellt. Alle 18
Nachprüfungen zu Erreichbarkeit, Build-Identität, Speicher und Einstellungen
sind PASS. Die 181 Projekte mit 121242 kanonischen Modelldatensätzen sind
unverändert. Schema-Version 27 und die Lösch-Tabelle sind produktiv bestätigt.
Die fünf erhaltenen Läufe bestehen weiterhin aus 32 verifizierten Dateien;
alle 24 geprüften Downloadpfade sind erreichbar.

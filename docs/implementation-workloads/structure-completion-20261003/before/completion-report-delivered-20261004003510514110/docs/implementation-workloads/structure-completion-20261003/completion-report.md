# Abschluss der NIS-Strukturmigration

Stand: 2026-10-03. Status: **IMPLEMENTIERT; VOLLSTÄNDIGE RELEASEPRÜFUNG LÄUFT**.

Dieser Nachweis ergänzt die ursprüngliche Migration und schließt die fünf Befunde aus `docs/project-scanner/migration-review-20261003/analysis.md`.

| Befund | Ergebnis | Nachweis |
| --- | --- | --- |
| R1 | Frontend nutzt die kanonische Technologieprojektion. MODBUS RTU bleibt MODBUS RTU; unbekannte und im Editor nicht unterstützte Technologien bleiben offen. Routing erzeugt keine ersetzte oder teilweise Strecke und zeigt die offene Zuordnung. | Bus-Technologie-Tests; Projektionstest; vollständiger Frontendlauf |
| R2 | Framing, Timing, Scheduling, CAN-Arbitrierung sowie konkrete PHY-Definitionen und Regeln liegen bei den Technologiepaketen. Bitratenvorschläge stammen ausschließlich aus profile.json. Generische Dienste delegieren an diese Eigentümer. | 1.664 Berechnungsfälle, 600 Timingadapter-Aufrufe und 1.458 PHY-Fälle ohne Abweichung; alle 125 Registryprofile und vier Katalogexporte unverändert |
| R3 | 3933 Zuordnungen; alle 927 Übergangswrapper mit Eigentümer, beobachteten Verbrauchern und pfadspezifischem Entfernungskriterium. Neue Build-, Test- und API-Dateien sind erfasst. | docs/migrations/structure_mapping.csv; Abdeckungstest |
| R4 | Zwölf Architektur-/Regressionsprüfungen schützen die Verantwortungsgrenzen, einschließlich eingeschleuster Protokollregeln, kopierter Ratenvorschläge und des vollständigen alten Katalogexportvertrags. Fünf Fälle laufen in der vorhandenen Tool-Checker-CLI mit frischer automatischer Vorprüfung. | 5/5 Tool-Checker-Fälle PASS; migration-risk-tests.xml |
| R5 | Alle 125 Technologiepakete dokumentieren Profile, tatsächlichen Status, Schnittstellen, vorhandene Adapter und Tests. Gemeinsamer Einstieg für Erweiterungen vorhanden. | Dokumentationsprüfung; backend/nis/communication/technologies/README.md |

Die Kompatibilitätswrapper bleiben begründet erhalten. Der interne Scan findet konkrete Verbraucher bei 130 Wrappern; ein leerer interner Scan schließt externe oder persistierte Verbraucher nicht aus. Ihre Entfernung setzt die jeweils dokumentierte Vertragsmigration voraus. Es wird keine zusätzliche Technologieunterstützung behauptet.

Zusätzliche Absicherung: Der Projektionsgenerator gehört jetzt zur Quellidentität eines Releases. Änderungen daran verhindern die Wiederverwendung eines älteren Images; temporäre Backend-Buildartefakte bleiben ausgeschlossen. Ein Regressionstest belegt beide Fälle.

## Verifikation

- Abschließende gemeinsame Prüfung sämtlicher im Migrationsplan genannter Risiken: 829 Tests bestanden; migration-risk-tests.xml.
- 147 gezielte Timing-/Kapazitäts-/Registry-/Serialtests bestanden.
- 36 PHY-/Port-/LIN-/Architekturtests bestanden.
- Nach Entfernung der Ratenkopien 66 gezielte Architektur-/Registry-/Serialtests bestanden.
- 28 Release-Skripttests bestanden.
- TypeScript-Prüfung und 564 Frontendtests bestanden.
- Tool Checker: eigene Suite nis-structure-completion-20261003, fünf Fälle PASS; historische EA-Kampagne unverändert.

SQL-Prüfungen liefen ausschließlich auf temporären Postgres-Containern über scripts/run-isolated-tests.py. Die Produktionsdatenbank wurde für Tests nicht verwendet. Vorzeitig angehaltene Gate-Läufe sind als ABORTED dokumentiert; sie bauten kein Kandidatenimage. Der nachfolgende vollständige Gate-Nachweis ist maßgeblich.

Bekannte Modellfeldwarnungen bleiben als Warnungen ausgewiesen. Die gezielten Teilprüfungen ersetzen den vollständigen Release-Nachweis nicht.

Tool-Checker-Beleg: I:\PycharmProjects\My_first_Network_Simulator\.tool-checker\runs\standalone\session-b156585d421048558c1b2ff77485fc50.json

Vorher-/Nachher-/Diff: before-index.json, after-index.json, changes.patch. Vorhandene Nutzeränderungen wurden erhalten.


# Aufgabenbezogenes Regelregister

## Engineering-Agent — 15.09.2026

Aktueller Befund und ausführbarer Ausbauplan: [Engineering-Agent-Audit](engineering-agent-audit-2026-09-15.md).
Der Bericht trennt Quellbefund, Reproduktion, Tests und offene Abnahme. Er ändert die bestehenden Verträge nicht.

| Kennung | Quelle | Wirkung |
| --- | --- | --- |
| EA-01 | Nutzerauftrag 15.09.2026 | Projektanlage und fachliche UI-Aktionen auch über den Agenten; Wizard optional |
| EA-02 | WIZARD_EXECUTION_CONTRACT | Projekt, Originalanforderung, Operation und Revision bleiben gebunden; Blocker brauchen konkrete nächste Handlung |
| EA-03 | Branchenregel im WIZARD_EXECUTION_CONTRACT | Keine fremden Branchen, Protokolle oder Beispielgeräte als bestätigte Eingabe |
| EA-04 | COMMUNICATION_DESIGN_CONTRACT | Lokale I/O und externer Funktionsoutput getrennt; keine erfundene Kodierung oder technische Freigabe |
| EA-05 | SPATIAL_ARCHITECTURE_CONTRACT / NETWORK_NAMING_CONTRACT | Funktionaler Owner, Einbauort, Transport und persistierte Namen getrennt behandeln |
| EA-06 | WIZARD_RELEASE_GATE | Isolierte SQL-/E2E-Abnahme; ausschließlich exaktes PASS-Image ausliefern |

Vorschlag aus dem Audit, noch nicht implementiert: gemeinsamer persistierter EngineeringDraft, fachliche Befehle im Python-Core, Chat und Wizard als gleichwertige Bedienwege. Keine zusätzliche Freigabeanforderung wird aus diesem Register abgeleitet.

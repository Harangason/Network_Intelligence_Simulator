# Projektbezogene Nutzerparameter

Globale und netzbezogene Workflow-Parameter werden beim Speichern atomar in `<Projektordner>/user_defined_values.json` geschrieben. Die Datei enthält `USER_DEFINED_VALUE`, normalisierte Projekt-ID, Revision, Zeitstempel und die Projektparameter. `technology_defaults` und `defaults_source` werden als Katalogreferenzen nicht übernommen. Die bestehenden Hardware-/Messnachweise sowie Simulationsannahmen behalten ihre Herkunft.

Das Lesen bevorzugt die Projektdatei, sofern ihre Revision zum SQL-Projektstand gehört. Die bestehende Engineering-Datenbank bleibt eine projektbezogene Laufzeitkopie für Berechnungen und Validierung; der Technologie-Katalog wird nicht geändert. Während eines offenen Commits bleibt die zuvor bestätigte Laufzeitkopie lesbar. Dateifehler rollen SQL zurück; fehlgeschlagene SQL-Commits stellen die vorherige Datei wieder her. Ein fehlender Projektwertbestand nutzt den bisherigen Projektstand bis zum nächsten Speichern.

Klonen und Import materialisieren eine Datei für das Zielprojekt. Ein Workspace-Reset entfernt dessen Datei innerhalb derselben Transaktion. Die neue lesende API `/api/engineering/workflow/parameters/user-defined-values` liefert ausschließlich den revisionsgleichen Projektbestand.

Die Änderung betrifft die Workflow-/Netzparameter. Geräteobjekte bleiben im vorhandenen kanonischen Engineering-Modell und im vollständigen Projektbundle. Dieses Vorhaben ersetzt keine Engineering-Modellpersistenz durch einen zweiten Objektkatalog.

Produktionsziel des ausgewählten Projekts ist der bestehende SAVED-Bind-Mount, also `I:/PycharmProjects/My_first_Network_Simulator/SAVED/network-project-20261005103106027-d3a78a2c/user_defined_values.json`. Bereits vorhandene Projektwerte sollen nach der erfolgreichen Auslieferung unverändert in diesen Speicher übernommen werden.

Der Abschluss und der vollständige Prüfumfang sind in `completion.md` dokumentiert. Release-Gate und Produktionsprüfung sind bestanden.

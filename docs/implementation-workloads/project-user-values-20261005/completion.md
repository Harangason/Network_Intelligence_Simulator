# Abschluss: projektbezogene Nutzerparameter

Die Änderung ist vollständig geprüft und als exakt getestetes Image ausgeliefert. Globale und netzbezogene Workflow-Parameter werden als `USER_DEFINED_VALUE` atomar in `user_defined_values.json` im bestehenden Projektordner gespeichert. Die Datei ist der führende Parameterspeicher; die projektbezogene Engineering-Datenbank bleibt Laufzeitkopie für Berechnung und Validierung. Zentrale TechnologyProfile-Defaults werden nicht geändert. Katalogreferenzen werden nicht als eigene Defaultdefinitionen in die Datei kopiert.

Für das ausgewählte Projekt wurden alle 54 vorhandenen Parametereinträge unverändert über den normalen Projektspeicherweg übernommen. Werte, Versionsstände und Bearbeitungstoken sind identisch geblieben. Die vollständige Katalogantwort mit 125 Technologien ist byteinhaltlich/strukturell unverändert. Herkunft, Simulationsannahmen und echte Gerätenachweise werden bewahrt; `USER_DEFINED_VALUE` ersetzt keine technische Evidenz.

Dateischreibfehler rollen SQL zurück. SQL-Commitfehler stellen die vorherige Datei wieder her. Korrelierte Revisionen verhindern, dass ein Leser noch nicht bestätigte Dateiinhalte mit einem alten SQL-Stand verbindet. Die interne Revision bleibt beim Kontextwechsel erhalten und wird getrennt als Speichermetadatum geführt. Klonen, Import und Workspace-Reset berücksichtigen die Datei. Vorhandene Altprojekte ohne Datei bleiben bis zum nächsten Speichern lesbar. Geräteobjekte bleiben im kanonischen Engineering-Modell und im vollständigen Projektbundle; die Änderung betrifft Workflow-/Netzparameter.

Projektdatei: `I:\PycharmProjects\My_first_Network_Simulator\SAVED\network-project-20261005103106027-d3a78a2c\user_defined_values.json`

## Tatsächlicher Prüfumfang

- 137 gezielte Speicher-, Projekt-, Netzwerk-, Workflow- und Simulationsumfang-Prüfungen: PASS.
- Vollständiges Release-Gate: 28 Release-/Speichertests, Typprüfung, 570 Frontendtests, 21.578 Backendtests und 56 Untertests bestanden; 2 bestehende übersprungene Tests und 1 bestehende Warnung.
- Browser am unveränderlichen Release-Image: 88 bestanden, einschließlich tatsächlicher Datei-/API-Persistenz nach einer CAN-FD-Änderung, aller registrierten Parameteransichten sowie der kleinen/großen Wizard-Abläufe.
- Kleine HTTP-Prüfung: 6 erwartete/ausgewertete Routen, 0 fehlgeschlagen.
- Große HTTP-Prüfung: 766 erwartete/ausgewertete Routen, 0 fehlgeschlagen, keine fehlenden beobachteten Signale, Conformance PASS. Bestehende fachliche Kapazitäts-/Preflight-/Assessment-Warnungen bleiben erhalten.
- Produktion: getestete/laufende Image-ID identisch, Container healthy, Localhost und VPN/LAN ready. Projektdatei auf dem Host und über beide API-Adressen identisch; zentraler Katalog unverändert. Reale Oberfläche: 73 Parameterfelder, 0 leer, neuer Speicherhinweis sichtbar.

## Ausgelieferte Version

Image: `sha256:1ac99a2cc7e07158bba2f8d459ec21188840faf877927798480bfc7a55b6ca17`

Quelle: `4b035b018e82fd96b526d4496a144a73a7c5a9a223e5eb3c4fbd30e505e55fe9`

Git-Basis: `f0c9ffde83a1e2edec525de4edfaa8d907abe2ed`

PASS-Nachweis: `backend/test-output/release-gates/delivery-80aa4e6828c7/bcae78949b5f/receipt.json`

Der erste vollständige Lauf blieb wegen zweier Integrationsfehler FAIL. Nach Korrektur von Kontextabgrenzung und authentischer Legacy-Testvorbereitung wurde das gesamte Gate erneut erfolgreich ausgeführt. Fehlgeschlagene Nachweise bleiben erhalten. Die Produktdatenbank wurde nicht als Testziel benutzt; die Übernahme der tatsächlichen bestehenden Projektwerte war eine autorisierte Migration ohne erfundene Datensätze oder Wertänderungen. Historische Images, fremde Änderungen und die vorhandene Benutzeransicht wurden bewahrt. Ein separater temporärer Browsertab diente der Produktionsprüfung. Der historische Tool-Checker-Campaign wird damit nicht als PASS erklärt.

[Lokales Projekt](http://localhost:13500/studio?mode=parameters&project=20261005103106027-d3a78a2c) · [VPN/LAN-Projekt](http://192.168.178.10:13500/studio?mode=parameters&project=20261005103106027-d3a78a2c)

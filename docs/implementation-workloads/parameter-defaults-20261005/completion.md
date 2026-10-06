# Abschluss: vollständige Simulationsvorgaben in NIS

Die Änderung wurde über das vollständige Release-Gate geprüft und als exakt getestetes Image ausgeliefert. In der gemeldeten CAN-FD-Ansicht des Projekts `20261005103106027-d3a78a2c` sind alle 73 skalaren Parameterfelder vorbelegt: vorher 33 leere Felder, jetzt 0.

## Umsetzung und Ursache

UNKNOWN-Felder besaßen bislang keine ausdrücklich getrennten Simulationsvorschläge. Zusätzlich verdeckten leere gespeicherte Werte vorhandene Defaults; alte unbestätigte globale Werte konnten gespeicherte Szenarioänderungen beim erneuten Laden überschreiben.

TechnologyProfile und seine Feldschemas liefern nun typgerechte Vorschläge für 125 eindeutige Technologien mit 14.133 Feldern. CAN und CAN-FD besitzen eigene, nativ validierte Startkonfigurationen. Die gemeinsame Auflösung versorgt Parameterformular, Preflight-Review und Geräteeditor. Bestätigte Istwerte behalten Vorrang. Szenarioänderungen bleiben beim Speichern und erneuten Laden erhalten; ersetzte unbestätigte globale Duplikate werden entfernt.

Unbekannte Geräte- und Messwerte werden gesondert als `NIS_SIMULATION_ASSUMPTION`, `ASSUMED`, `hardware_evidence=false` gespeichert und angezeigt. Echte UNKNOWN-Definitionen, Hardwarebestätigung und strenge physische/Timing-/Preflight-Prüfungen bleiben erhalten. Schema-Beispiele sind bearbeitbare Ausgangswerte und kein Nachweis eines ausführbaren physikalischen Modells für jede Technologie.

Die generierte Technologie-Projektion wurde über ihren vorhandenen Generator aktualisiert; lediglich ihr Herkunfts-Hash änderte sich. Die Strukturzuordnung enthält den neuen Regressionstest und bewahrt sämtliche 3.968 bisherigen Zuordnungen. Schema-Audits prüfen die zwei zusätzlichen Simulationsmetadaten getrennt; alle ursprünglichen Profildefinitionen, Grenzen und UNKNOWN-Regeln bleiben exakt geprüft.

## Prüfnachweise

- Vollständige Typprüfung und Release-/Speichertests: PASS.
- Frontend: 570 bestanden.
- Backend in Wegwerf-Postgres: 21.570 bestanden, 56 Untertests bestanden, 2 übersprungen, 1 bestehende Warnung zum Feldnamen `validate`.
- Browser gegen das unveränderliche Release-Image: 88 bestanden. Darin alle 125 realen Parameterformulare, sämtliche zehn Technologie-Regressionen, Speicher-/Reload-Verhalten, bestätigte Gerätewerte, große Ganzzahlen und die kleinen/großen Wizard-Abläufe.
- Kleine HTTP-Prüfung: 6 erwartete und ausgewertete Routen, 0 fehlgeschlagen.
- Große HTTP-Prüfung: 766 erwartete und ausgewertete Routen, 0 fehlgeschlagen, keine fehlenden beobachteten Signale, Conformance PASS. Die dokumentierten Kapazitäts-/Preflight-/Assessment-Warnungen bleiben sichtbar.
- Produktionsprüfung: identische getestete/laufende Image-ID, Localhost und VPN/LAN ready, unveränderte gespeicherte Projektparameter. Im realen Produktbrowser 73 Parameterfelder, 0 leer, 33 als Simulationsannahme gekennzeichnet.

## Ausgelieferte Version

Image: `sha256:1cf9cd671c32c6f807c867b1173b2571397eb293a1c632d6642d4dbc0c8ec545`

Quelle: `a05752f8724b39454ad1cc21138478991ae3c49defd13ad47b394087c760bb5f`

Git-Basis: `f0c9ffde83a1e2edec525de4edfaa8d907abe2ed`

Vollständiger PASS-Nachweis: `backend/test-output/release-gates/delivery-3112c6e77690/e169e94e6a7a/receipt.json`

[Lokales Projekt](http://localhost:13500/studio?mode=parameters&project=20261005103106027-d3a78a2c#parameter-values) · [VPN/LAN-Projekt](http://192.168.178.10:13500/studio?mode=parameters&project=20261005103106027-d3a78a2c#parameter-values)

Die Produktdatenbank wurde nicht als Testziel verwendet. Die Abschlussprüfung des realen Projekts war lesend. Historische Images und fremde Arbeitsänderungen wurden bewahrt. Die taskbezogenen Vorher-/Nachher-Snapshots und `changes.patch` dokumentieren alle 17 betroffenen Dateien. Frühere fehlgeschlagene bzw. abgebrochene Läufe bleiben als solche erhalten; der historische Tool-Checker-Campaign wird hiermit nicht als PASS erklärt.

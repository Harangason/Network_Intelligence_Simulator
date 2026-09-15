# Geräteumfang: Sollzahl und erkannte Geräte

Die Inventarübersicht im Engineering-Fragebogen verwendete `equipmentCounts`
(verbindliche Sollwerte) als unbeschriftete Anzahl über einer Liste aus
`plannedEquipment.chains` (konkret erkannte Geräte). Dadurch konnte eine leere
Sensorliste mit „Sensoren · 3“ überschrieben sein. Der Bereitschaftstext ließ
zusätzlich `equipmentIdentityReady` aus, obwohl die Übergabeprüfung diese
Bedingung bereits berücksichtigt.

Die Übersicht zeigt jetzt erkannte und vorgegebene Anzahl getrennt. Der
Vollständigkeitsbefund nennt die betroffene Kategorie und beide Zahlen.
Der Bereitschaftstext berücksichtigt die Identitätsprüfung.

Eine bloße Anzahl ohne Messaufgabe erzeugt weiterhin keine erfundenen
Sensortypen. Der gezielte Browserfall reproduziert „Raspberry Pi, drei Sensoren
und drei Ventile“, prüft 0 erkannt / 3 vorgegeben und den unvollständigen Status,
präzisiert die Eingabe auf drei Temperatursensoren und prüft danach alle drei
Sensoren im Controller-Zweig. Die exakte ungespeicherte Eingabe des gemeldeten
Screenshots war nicht mehr verfügbar; der Versuch ist eine gezielte Reproduktion.

Validierung: drei bestehende Parser-/Clustertests bestanden; gezielter realer
Playwright-Test gegen einen separat gebauten Produktionskandidaten mit
wegwerfbarer Datenbank bestanden. Test-Ressourcen anschließend entfernt.
Beleg: `backend/test-output/inventory-release-gates/bf3ae54da6f4/targeted-browser-r6.json`.

Stand: Im vollstaendigen Release 40972398d891 enthalten, E2E bestanden und am 15.09.2026 bereitgestellt.

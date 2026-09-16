# Korrekturen zum Industry60-Recheck vom 16.09.2026

Bezug: `.tool-checker/reports/industry60-recheck-20260916.md`. Der historische Bericht bleibt unverändert; die dort offenen 58 Fälle werden durch diese Korrektur nicht zu vollständigen Szenario-PASS.

## R01 – Zusammenfassung des tatsächlichen Entwurfs

Die feste Temperatur-/Ventil-Steuerkette wurde entfernt. `project_intake_text` beschreibt die tatsächlich gespeicherten Geräte, gruppiert nach Geräteart. `prepare_project_request` übergibt dafür die persistierte Geräteliste; auch Ergänzungen zeigen den gesamten aktuellen Entwurf. Keine erfundene Schreibfehlerkorrektur oder automatische Behauptung einer Steuerkette.

## R02 – Explizite Technologiezuordnung

Der Inventarparser verarbeitet im Kommunikationsabschnitt zusätzlich „Technologie für/fuer/for Gerätefamilie“. „Drives“ bindet die explizit genannten „Motor Drives“. Angaben mit Doppelpunkt bleiben unterstützt. Qualifikatoren werden erhalten: schnelle Positionssensoren oder einfache Sensoren dürfen nicht pauschal auf unbestimmte Sensorplätze übertragen werden. Alternative oder widersprüchliche Technologien bleiben als Anschlusskandidaten offen. Negierte Angaben erzeugen keine bestätigte Verbindung.

## Prüfung

- 12 neue Regressionen mit Originalaufträgen S01-A/S12-A, Negativfällen, konkurrierenden Anschlüssen und SQL-Persistenz.
- Gezielter isolierter Lauf: 46 bestanden, eine bestehende Pydantic-Warnung.
- Backend-Gesamtlauf: 1808 bestanden, 2 übersprungen; Frontend: 390 bestanden; Typprüfung und Produktionsbuild erfolgreich.
- Vollständiger Release-Lauf: `backend/test-output/release-gates/403051a80f8e/receipt.json`; **PASS**, alle vorgeschriebenen Prüfungen erfolgreich.
- Browser-E2E: 68 bestanden, einschließlich neun Stufen für I2C/Modbus-RTU-Raspberry-Pi-Projekte und Großprojekt mit echtem Simulationsneustart.
- Kleine und große HTTP-Abnahme bestanden; Großprojekt: Conformance PASS, 1404 beobachtete Signale, 0 fehlgeschlagene Routen.
- HTTP-Wiederholung beider Originalaufträge bestanden, einschließlich erneut geladenem Entwurf und vollständigem persistiertem CHAT-Output. Der Kurztext ist eine gekürzte Vorschau; die Vollantwort wurde im strukturierten Output geprüft.
- Browser: alle acht Geräte des gemischten Auftrags sichtbar; bei allen zehn MotorDrives steht EtherCAT. Nachweise: `.tool-checker/evidence/industry60-intake-fixes` (JSON und Browser-AX).
- HTTP-Test nutzt den deterministischen Intake im isolierten Release-Kandidaten ohne lokale KI. Kein neuer Nachweis zur Qualität zusätzlicher Modell-Planungstexte.

Die Prüflücken S26/S29/S38 sowie die übrigen offenen Pflichtpfade aus dem Bericht sind kein durch diese Änderungen erbrachter E2E-Nachweis. Architekturentscheidungen werden nicht automatisch beantwortet. Eine Fehlerquote unter 1 Prozent für alle 60 Szenarien ist damit nicht nachgewiesen.

## Bereitstellung

Build `6b788ad14684` über `start-networkis.ps1 -ReleaseReceipt` bereitgestellt. Laufendes Image stimmt exakt mit dem PASS-Receipt überein: `sha256:9f7d6fbf3b5f20c13bea0a0525675dceafbc498f79aeaaa8a386e34f4166915e`. Container healthy; `/api/ready`: Datenbank und Speicher verfügbar. Bestehende Entwürfe wurden nicht automatisch umgeschrieben.

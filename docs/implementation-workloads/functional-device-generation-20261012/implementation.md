# Fachliche Sensor-/Aktor-Erstellung

Der gemeinsame Wizard-Generator erhält einen branchenunabhängigen funktionalen Gerätevertrag (`sensor-actuator-v1`). Die aktuelle Wizard-Oberfläche gibt diese Version ausdrücklich mit dem bestätigten Auftrag weiter. Ältere bestätigte Importaufträge behalten ihre bestehende Codierung.

Sensoren benötigen eine fachliche Messgröße und einen Verarbeiter/Empfänger. Eigene Messgrößen und Anschlüsse haben Vorrang vor Entwurfsvorschlägen. Unbekannte Rollen bleiben offen. Komplexe Messdaten bleiben neben Status, Health, Qualität, Zähler und Mode erhalten; die bisherige Begrenzung auf fünf Signale durfte den Nutzdatenausgang abschneiden.

Wahrnehmungsfunktionen erhalten einen getrennten FUNCTION_OUTPUT-Entwurf für Objektdaten. Der begrenzte Entwurf enthält Objekt-ID, Klassifikation, Konfidenz, Position, Geschwindigkeit sowie Frame-/Zeit-/Koordinatenreferenzen. Größen, Objektvokabular, Koordinaten- und Zeitbezug sind prüfpflichtige Annahmen. Es werden keine erkannten oder gemessenen Objekte erfunden und keine Bildverarbeitungsalgorithmen implementiert.

Funktionale Abhängigkeiten zu Assistenz, Navigation oder Sensorfusion sind sichtbare TX/RX-Vorschläge im vorhandenen Review. Die bestätigten Empfänger werden über die bestehenden kanonischen Kommunikationsverträge und Routingpfade verarbeitet. Kein Gateway oder Display wird allein aus physischer Erreichbarkeit zum fachlichen Empfänger.

Allgemeine Verarbeiter speichern die zugeordneten Sensor-/Aktor-Referenzen in Function.configuration; Sensor- und Aktorrollen liegen in HardwareNode.identity. Referenzen werden erst nach Anlage aller Hardware aufgelöst, damit Controller/Sensor keine zyklische CREATE-Abhängigkeit erzeugen. Befunde werden bei Vorschlagsprüfung und in der Simulationsvorprüfung ausgewertet. Status und Aktorrückmeldung ersetzen keine Wahrnehmungseingänge; ein Status oder fremder Sender erfüllt keinen Aktorbefehl.

Die Bestandsdaten des geöffneten Projekts wurden nicht automatisch umgeschrieben. Ihr historischer Lauf enthält die neuen Objektdaten noch nicht. Eine fachlich geprüfte Modellergänzung/Neugenerierung ist erforderlich, um die aktuelle Kamera-Assistenz-Lücke in diesen konkreten Daten zu reparieren. Die Codeauslieferung allein erzeugt keine rückwirkende Trace-Evidenz.

Prüfungen: 319 Frontend-Tests, TypeScript-Prüfung, 40 isolierte Generator-/Status-Regressionsprüfungen und 15 zusätzliche isolierte Gerätevertrag-Prüfungen. Zwei davon erstellen, prüfen, genehmigen und übernehmen echte neue Custom-/Robotik-Modelle mit bestätigter Bilddaten- und Objektdatenkommunikation. Vollständiger Release und Produktivnachweise werden im workload.json geführt.

Radar-Abstandssensoren behalten skalare Messgrößen. Radar-Objektlisten sind ausdrücklich als solche benannt; die Verarbeitungsfunktion kann beide passenden Eingänge akzeptieren. Temperatur erfüllt keinen Radar-Eingang.

Die Vollprüfung erkannte fehlende Einträge neuer Dateien im kanonischen Strukturverzeichnis. Neun fehlende Pfade (einschließlich bereits vorhandener UI-Erweiterungen) wurden mit ihren tatsächlichen Eigentümern und Verbrauchern ergänzt. Alle sieben unveränderten Strukturtests bestanden anschließend.

Die bestehende Mehrfenster-Browserprüfung verwendete noch die Namen der früheren gemeinsamen Steuerung und den englischen Wiedergabestatus. Der Bedienungsweg wurde an die freigegebene Trennung von Simulation/Trace und die zugeklappte Steuerung angepasst; alle fachlichen Kopplungs-, Vergleichs-, Cursor-, Kontext- und Sitzungsprüfungen bleiben erhalten. Fünf Fälle bestanden gemeinsam, der verbleibende Cursorfall nach dem Öffnen der verborgenen Steuerung separat.

Die Anzeige-/Traceformat-Prüfung öffnet jetzt die standardmäßig geschlossene Simulationssteuerung vor dem Zugriff auf Start und Traceformate. Alle fünf Fälle bestanden mit unveränderten Anzeige-, Auswahl- und Formatprüfungen. Auch der kleine Neunstufen-Wizard öffnet diese Steuerung bei Wiederherstellung und Neustart ausdrücklich; die Persistenz-, Artefakt- und Neustartprüfungen bleiben vollständig erhalten.

## Produktiver Abschluss am 13.10.2026

Der vollständige Release `delivery-d005d85ff712/904e7c1d3803` ist PASS: 631 Frontend-Tests, 21.804 Backend-Tests und 56 Subtests (2 übersprungen), 116 Browserfälle, Typprüfung, 28 Speicher-/Releaseprüfungen und beide kleinen/großen HTTP-Abnahmen bestanden. Der große Browserlauf mit 50 Controllern, 250 Sensoren und 250 Aktoren bestand in 14,3 Minuten; der kleine Neunstufen-Lauf mit Reload/Neustart sowie alle Rückkehrfälle bestanden. Nichtautomotive I2C/Modbus-Browserfälle prüfen den berechtigten Block inkonsistenter Parameter; sie werden nicht als vollständige Neunstufen-Abnahme ausgegeben.

Parallel genehmigte UI-Änderungen machten den früheren finalen Quellenabgleich ungültig. Die FAIL-Belege bleiben erhalten. Das ungenutzte Fehlversuchsimage `0b2a649c42e1` wurde nach vollständig geprüfter Archivierung und frischen Referenzprüfungen gezielt entfernt. Für die aktuelle Oberfläche wurden ausschließlich Browserbedienungsselektoren angepasst: Bereich/Ansicht/Kopplung, gemeinsamer Cursor in den Einstellungen, neue Start-/Reset-Namen und eindeutige Reset-Bestätigung im Alertdialog. Alle fachlichen Assertions und Zeitlimits blieben erhalten. Der Reset-/Historien-/Neustartfall wurde vor der letzten Vollprüfung gezielt bestanden.

Das unveränderte bereits gebaute Image wurde nach reinen Prüfeingabeänderungen erneut vollständig getestet und durch `scripts/release-and-deploy.py` produktiv übernommen. Image: `sha256:ad1a2361ee5f1ae61b351a16cd6657f58537977766de5412ee7375cdaf6860b4`; Git: `0800dd20216b38ce97db457f05da29a542f4f6e5`; Anwendungsquelle: `a1aeaee791e6aa9f632a0c19ed3a91301648c2e99ee87a9215cf5057680794c0`; Prüfeingaben: `1d53a506831e93a3eebdc8446c4d1a64ec936919dca897a4b0eadf4b886e74d3`. Laufendes Image und Quellidentität stimmen mit dem PASS überein, Datenbank und Speicher sind verfügbar.

`verify_production.py` bestätigte im laufenden Image vier unveränderte Generatorfälle (Custom, Robotics, Aerospace, Building): Sensor-Bilddaten und getrennte, begrenzte FUNCTION_OUTPUT-Objektdaten mit Sensor-Eingangsreferenz. Prüfung ohne SQL-Schreibzugriff oder Änderung des Produktmodells. Die aktorbezogenen Prüfungen sind in den isolierten Backend-/Wizard-Abnahmen enthalten. Bestehendes Projekt `20261009072206008-4bb505f1` und alte Traces wurden nicht rückwirkend erweitert; fachlich geprüfte Modellergänzung oder Neugenerierung und neuer Lauf bleiben dafür erforderlich.

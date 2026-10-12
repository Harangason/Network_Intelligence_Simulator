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

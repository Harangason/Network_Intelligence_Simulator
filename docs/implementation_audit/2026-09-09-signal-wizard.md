# Signal-Wizard: Semantik und physischer Transport

Die übergeordneten Objekte und physischen Anschlüsse im Anlege-Wizard sind deutschsprachig alphabetisch und natürlich numerisch sortiert.

Der Signal-Wizard nutzt jetzt die bestehende kanonische Semantik: NUMERIC für Messgrößen sowie STATE, ENUM, BOOLEAN usw. für logische Werte. Zustandswerte, reservierte Codes, ungültige Werte und Default werden in den vorhandenen Feldern `semantic` und `data` übergeben. Der Bearbeitungsdialog verwendet dieselben verständlichen Signalart-Bezeichnungen. Bestehende Signale werden nicht automatisch umklassifiziert.

Zuordnung und Detailseite zeigen die tatsächlichen physischen Sendebindungen der Nachricht einschließlich zusätzlicher Sendebindungen. Busnamen stammen aus den Workflow-Netzen, Technologien aus den physischen Anschlüssen. Angezeigt werden Nachrichtenlänge, Zyklus und vorhandene Bitraten. Fehlende physische Zuordnung wird ausdrücklich angezeigt. Die Lastberechnung selbst bleibt nachrichtenbasiert; Signalart erzeugt keine zusätzliche Übertragung.

Validierung: Produktionsbuild inklusive TypeScript erfolgreich; sechs Signalarchitektur-Tests bestanden. Browserprüfung über `scripts/verify-signal-wizard.mjs` prüft Sortierung, LIN-Buskontext und das Submit-Payload für STATE mit OFF=0. Der POST wird im Browsertest abgefangen; es werden keine Testsignale im Benutzerprojekt angelegt. Screenshot und Payload-Nachweis liegen unter `verification/2026-09-09-signal-wizard.*`.

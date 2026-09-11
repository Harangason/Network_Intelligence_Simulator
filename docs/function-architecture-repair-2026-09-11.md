# Reparatur aus Funktionskommunikation und aktueller Hardwarearchitektur

Nutzerpräzisierung vom 11.09.2026: Der Agent soll die neue Hardwarearchitektur
anwenden und dabei erhalten, welche Funktionen vorher zusammengearbeitet haben.

Der Reparatur-Agent löst zuerst die Partneridentität auf. Die Quelle ist die
kanonische Kommunikationsschnittstelle bzw. der Nachrichten-Publisher. Der
Empfänger stammt aus der gespeicherten Kommunikation. Bei einem bisherigen
Geräte-Endpunkt ohne Funktionsreferenz ist nur eine eindeutig zugeordnete Funktion
als Ergänzung zulässig. Namen und benachbarte Leitungsanschlüsse sind kein Beleg.

Anschließend folgt der Agent der aktuellen `Function.hardware_node_id`-Zuordnung
und sucht die vollständigen physischen Wege. Ein Funktionsumzug aktualisiert die
Route, die physische Nachrichtenbindung und erforderlichenfalls die abgeleitete
Hardwarezuordnung der logischen Schnittstelle. Funktion und Schnittstelle behalten
ihre Identitäten. Andere Funktionen auf dem alten Anschluss bleiben davon getrennt.

`route.functional_intent` speichert die bisherigen Partner unabhängig von Bus und
Leitung. Neue Routen einschließlich angenommener Vorschläge erhalten diesen Anker.
Physische Änderungen im Netzwerkeditor erhalten ihn. Eine absichtliche Änderung
der Funktionspartner über den Routing-Editor erfasst dagegen die neue Kommunikation.
Die Routing-Validierung erkennt einen abweichenden Empfänger sowie eine nicht mehr
passende Funktions-/Hardwarezuordnung.

Einfache Sensoren und Aktoren benötigen nicht automatisch ein eigenes
Funktionsobjekt. Ihre vorhandene Geräte-I/O wird mit unveränderter Geräteidentität
gesondert dargestellt. Fehlende bzw. mehrdeutige Partner bleiben offen. Werden
beide Funktionen auf dasselbe Gerät verschoben, ist lokale Kommunikation auszulegen;
der Agent erfindet dafür keinen externen Busweg. Automatischer Technologiewechsel
oder eine funktionale Timingfreigabe sind kein Bestandteil dieser Reparatur.

## Prüfung des aktuellen Projekts

Projekt: `network-project-20260910042736034-d11591d0` nach der vom Nutzer übernommenen
neuen physischen Führung. Der Live-Datenbestand wurde für diese Prüfung nur gelesen.

- 262 Geräte, 126 Netze, 63 explizite Funktionen.
- 438 Kommunikationsbeziehungen zugeordnet: 143 Funktionsbeziehungen, 295 mit Geräte-I/O.
- Auf einer Projektkopie: 100 Routen in drei zusammengehörigen Reparaturen ergänzt.
- Danach keine offenen Reparaturgruppen und keine ungeklärten Partner.
- Funktionen, Signale, Payloads, Timing und Routing-Policies unverändert;
  geänderte Routen technisch validiert und erneut freizugeben.

72 Backendprüfungen einschließlich separater SQL-Datenbank bestanden.
Abgedeckt sind unter anderem Funktionsumzug, geteilte alte Anschlüsse,
versehentlich ersetzte physische Endpunkte, mehrdeutige Funktionen, Geräte-I/O,
veraltete Vorschauen und atomare Reparatur. Die Tests ändern das Benutzerprojekt nicht.

Die Zahlen oben beziehen sich auf den ersten geprüften Snapshot. Bei einem später
erneut eingelesenen Projektstand wurden auf dessen Kopie 70 Routen ergänzt; ein
Fall ohne durchgängigen physischen Pfad blieb offen. Alle 438 Funktions-/I/O-Partner
waren weiterhin zugeordnet. Der Agent berechnet jeden Vorschlag aus dem jeweils
aktuellen Modell; bekannte Partner allein beweisen noch keinen verfügbaren Busweg.

Implementierung: `backend/engineering/communication_intent.py` und
`communication_repair.py`, Routing-Persistenz/-Validierung sowie die gemeinsame
Reparatur-Agent-Oberfläche in Engineering und Routing.

Prüfungen: `backend/tests/test_communication_intent.py`,
`scripts/verify_function_architecture_sql.py`,
`frontend/scripts/verify-functional-architecture.mjs`.

# Netzwerk-Editor: Port anlegen

Am 10.09.2026 gemeldet am Kontextmenü von „Fahrerassistenz“. Korrektur im Build `1759676ab08c`.

## Ursache und Änderung

- In großen Topologien waren Portflächen transparent. Freie Ports verschwanden zusätzlich beim Abwählen des Geräts. Freie Anschlüsse sind jetzt dauerhaft als farbige, greifbare Ringe sichtbar. Die Zeichenbegrenzung der Gerätekarte schneidet sie nicht mehr ab; verbundene Busanschlüsse behalten ihre bisherige Darstellung.
- `addPort` änderte nur den lokalen React-Zustand. Es wartet jetzt auf die bestätigte Speicherung des physischen Anschlusses über den bestehenden Topologie-Endpunkt. Währenddessen sind die Menüeinträge gesperrt. Fehler erscheinen direkt im Menü, ohne einen ungespeicherten Schein-Port anzulegen.
- Der Speicherpfad normalisierte auch bereits kanonische Busansichten erneut nach alten Namensheuristiken. Im vollständigen Testprojekt führte das zu einem abgewiesenen Zonenmix. Gespeicherte Szenen werden jetzt mit ihren bestehenden physischen Netzreferenzen übernommen; die Normalisierung bleibt auf Topologien ohne gespeicherte Szene begrenzt.
- Mehrere neue Ports am selben Klickpunkt erhalten unterschiedliche freie Randpositionen. Ist kein freier Platz vorhanden, fordert der Editor zum Vergrößern der Karte oder Verschieben vorhandener Anschlüsse auf.

## Prüfung

Reproduzierbares Browser-Skript: [verify-network-port-menu.mjs](I:/PycharmProjects/My_first_Network_Simulator/frontend/scripts/verify-network-port-menu.mjs). Es verlangt ausdrücklich eine isolierte Projekt-ID; das Anwenderprojekt wird nicht durch Testports verändert.

Vollständige Kopie mit 261 Geräten und 260 Verbindungen: LIN, CAN, CAN FD, CAN-XL, Ethernet und FlexRay jeweils per Kontextmenü anlegen; genau einen zusätzlichen Port, zugehörigen SQL-Hardwareanschluss und richtigen Bustyp prüfen. Alle bestehenden Verbindungen einschließlich Buszuordnungen vollständig vergleichen. Ein absichtlich abgewiesener Speichervorgang muss den bisherigen Zustand erhalten. Nach Neuladen und Abwahl müssen alle sechs Ports sichtbar und ohne Überdeckung erreichbar bleiben.

Zusätzlich: 37 Backendtests bestanden; 14 SQL-abhängige Tests im lokalen Pytest-Lauf mangels Test-DB-Konfiguration übersprungen. Die Browserprüfung verwendet die laufende SQL-Datenbank mit einer getrennten Projektkopie. Sieben Frontendtests zu Topologie und Busdarstellung bestanden. TypeScript und Produktionsbuild erfolgreich.

Maschinenlesbares Ergebnis: [port-menu-browser-result.json](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/port-menu-browser-result.json). Sichtprüfung: [port-menu-verified.png](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/port-menu-verified.png).

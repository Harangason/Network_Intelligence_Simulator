# Benennung physischer Netze

Verbindliche Nutzeranforderung vom 10.09.2026; gilt für den kanonischen Simulator.

Automatisch erzeugte Ethernet-Netze erhalten persistierte Namen im Muster
`ETH_<Systemrahmen>_<NN>`, zum Beispiel `ETH_Kameraverarbeitung_01` oder
`ETH_Fahrerassistenz_02`. Nummern sind mindestens zweistellig; Namen werden
projektweit ohne Beachtung der Groß-/Kleinschreibung kollisionsfrei vergeben.

Der Kontext stammt aus bestätigter Owner-Zuordnung, vorhandenem Systemrahmen
oder gemeinsamem Cluster. Bei alten strukturierten IDs kann deren benannter
Kontext zur Benennung verwendet werden. Fehlt ein belegbarer Kontext, lautet
der neutrale Stamm `ETH_Netz`; keine fachliche oder räumliche Zuordnung erfinden.
Umlaute werden ausgeschrieben, Worttrenner zu Unterstrichen vereinheitlicht.

Der Name wird in `parameters.networks[].name` und allen Netznamensreferenzen
persistiert. Automatisch vom Netz übernommene Hardware-Interface-Namen folgen
ihm auch in kanonischen HardwareNetworkInterface-Datensätzen. Dadurch steht der
lesbare Name in Listen, Dialogen und im exportierten Projektmodell zur Verfügung.
Eine reine Verkürzung im View erfüllt die Anforderung nicht.

`name_source=generated` und `name_context` dokumentieren die automatische
Benennung. Individuelle Busnamen (`name_source=user`) sowie explizit vergebene
Portnamen bleiben erhalten. Wiederholte Generierung oder Abgleich erzeugt keine
neuen Namen für bereits passend benannte Netze. Technische IDs bleiben stabil.

Benennung bestimmt weder Technologie, Systemzugehörigkeit noch räumliche
Identität. Die Trennung aus `SPATIAL_ARCHITECTURE_CONTRACT.md` gilt unverändert.
Die Regel ändert keine Kommunikationsparameter, Freigaben oder Zeitbewertungen.

Gemeinsame Implementierung: `backend/engineering/naming.py`; verwendet vom
Wizard, manueller Port-/Netzerzeugung, Netzwerkzuordnung und Agent-Werkzeug.
Bestehende automatische Namen werden ausdrücklich über den versionierten
Projektabgleich `/workflow/ethernet-names` übernommen, nicht beim bloßen Lesen.


## Verifiziert am 10.09.2026

Aktiver Build `e8475e1422fb`. 43 Prüfungen in separater PostgreSQL-Datenbank
bestanden, darunter Wizard-Erzeugung, vollständiger Workflow, Alias-Anker,
Neuladen, Konflikte, Rollback, Erhalt individueller Namen und wiederholter
Abgleich. Fünf Frontend-Prüfungen sichern die tatsächlichen Netzlabels und
alphabetische Auswahl auch bei abweichenden Portnamen. Produktionsbuild samt
TypeScript erfolgreich.

Im Projekt `network-project-20260910042736034-d11591d0` wurden zehn alte
automatische Ethernet-Namen dauerhaft korrigiert. Vorhandene explizite Namen
bleiben erhalten. Nicht zuordenbare, momentan unverbundene Alt-Netze heißen
`ETH_Netz_01` bis `ETH_Netz_07`; die belegten Kontexte heißen unter anderem
`ETH_Diagnose_01` und `ETH_Infotainment_01`. Netz-IDs, Routing, Geometrie,
Kommunikationsparameter und Workflow-Versionen wurden dabei nicht verändert.
Der erneute Namensplan enthält keine Änderungen.

Abgleichskript: `scripts/normalize_project_ethernet_names.py`.
Sicherung und Ergebnis: `backend/runtime/ethernet-names-normalized.json`.
SQL-Prüfprotokoll: `backend/runtime/ethernet-naming-sql-result.txt`.
Browsertest der vererbten Namen: `network-project-bus-naming-ui-1789074298840`.
Die Routing-Auswahl liest die Namen aus `parameters.networks`; individuelle
Portnamen werden nicht länger als Netzname ausgegeben.


Die Browserkontrolle der bestehenden Route Diagnose → System bestätigt
`ETH_Diagnose_01` in der Interface-Auswahl und in der Busauswahl. Das Öffnen
und Schließen des Wizards lässt Parameter und Topologie unverändert.
Nachweis: `backend/runtime/ethernet-names-routing-verified.json` und
`backend/runtime/ethernet-names-routing-verified.png`;
Prüfskript: `frontend/scripts/verify-ethernet-names-routing.mjs`.

### Routing-Tabelle und Suche

Die Tabellenzelle `Network` hatte weiterhin `source.network_id` direkt ausgegeben.
Details zeigten ebenfalls IDs; die Matrix verkürzte sie bisher durch Textersetzung.
Seit Build `ad1f7e55915c` lösen diese Ansichten sowie die Vorschlagsliste explizite
Netz-IDs gegen den vollständigen gespeicherten Netzkatalog auf. Namen werden
unverändert übernommen, einschließlich Unterstrichen und Nummern. Tabellenfilter
und Matrixsuche verwenden dieselben Namen. Die technische ID bleibt als Tooltip
der Tabellenzelle prüfbar. Eine unbekannte ID wird als unbekanntes Netz angezeigt,
nicht durch ein anderes Interface-Netz oder einen Protokollnamen ersetzt.

`network-automotive_ethernet-7537dce901cb` ist eine intern erzeugte Identität:
`physical_segments.py` verwendet die Technologie und zwölf Hex-Zeichen des
SHA-256 über sortierte zusammenhängende Port-IDs. Der gespeicherte Netzname im
betroffenen Projekt lautet `ETH_Fahrerassistenz_02`.

Verifikation: acht Frontendtests und Produktionsbuild einschließlich TypeScript
bestanden. Der Browsertest bestätigt Tabelle, Namensfilter mit Treffer-/Leerfall,
Routendetails, Matrixsuche und Neuladen am betroffenen bestehenden Netz. Parameter,
Topologie und Routen bleiben unverändert. Prüfskript:
`frontend/scripts/verify-routing-network-labels.mjs`; Ergebnis:
`backend/runtime/routing-network-labels-verified.json`; Screenshots:
`backend/runtime/routing-network-labels-table.png` und
`backend/runtime/routing-network-labels-matrix.png`.

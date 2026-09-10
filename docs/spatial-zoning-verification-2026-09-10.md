# Räumliche Busaufteilung

Projekt: `network-project-20260910042736034-d11591d0`. Stand: 10.09.2026.

## Vorgaben und Ursache

| Kennung | Quelle | Regel |
| --- | --- | --- |
| ZONE-01 | Nutzerkommentar zu RearLeft/RearRight, 10.09.2026 | Lokale Busse räumlich trennen; keine Vermischung verschiedener Fahrzeugecken. Projektregel, keine allgemeine LIN-Protokollgrenze. |
| ZONE-02 | Nutzerantwort, 10.09.2026 | Dieses Fahrzeug ist ein Linkslenker: Fahrer links, Beifahrer rechts. |
| ZONE-03 | Frühere Nutzerfreigabe zu Umzuordnungen | Änderungen betreffen kanonisches Modell, Anschlüsse, Verbindungen und Routen sowie die gespeicherte Ansicht. |
| ZONE-04 | Binding-/Generator-Verträge unter `docs/technology_bindings` | Einbauort und physische Netzwerkkennung sind keine Protokollidentität. Nachrichtengeneratoren bleiben Registry-basiert. |

Die bisherige `_confirmed_local_io_memberships` zählte Teilnehmer je System-Owner und Bustyp. Räumliche Positionen waren kein Gruppierungsschlüssel. Dadurch teilten sich alle acht Federweg-/Dämpferpositionssensoren einen LIN-Zweig. Die Lastrechnung konnte die unpassende Architektur nicht erkennen.

## Umsetzung

- Gemeinsame Wortsegmentierung für deutsche zusammengesetzte Namen, CamelCase und englische Positionen. `Fahrersitz` wird als Sitz auf Fahrerseite erkannt, `Fahrerassistenz` nicht. Explizite Einbauorte in `HardwareNode.identity.installation_zone` haben Vorrang vor Namen; Widersprüche brechen die Planung ab.
- Wizard ordnet vor Nachrichtenbindung nach funktionalem Owner, Technologie und Einbauzone zu; erst danach greifen Teilnehmergrenzen und Lastdimensionierung. Natürliche Namenssortierung hält die Planung unabhängig von Eingabereihenfolge stabil.
- Bestandsmigration trennt lokale LIN-, CAN-, CAN-FD-, CAN-XL- und FlexRay-Zweige. Controller-Backbones dürfen weiterhin Zonen verbinden. Ethernet bleibt in dieser Änderung unverändert.
- Bestehende Busse werden getrennt, nicht automatisch zusammengelegt. Bereits getrennte Zweige derselben Zone können bestehen bleiben; ihre Bezeichner werden bei Bedarf nummeriert. Bestehende Protokolle und Bitraten werden übernommen, nicht aus alten ID-Endungen abgeleitet.
- Jeder neue Zweig erhält einen eigenen modellierten Controllerkanal. Feste Ressourcenobergrenzen werden geprüft. Zusätzliche Kanäle dokumentieren Planungsbedarf, keine Beschaffungs- oder Hardwarebestätigung.
- Transaktionale Übernahme mit versionsgebundener Vorschau: Hardware-Identitäten, physische Anschlüsse, Nachrichtensendebindungen, direkte Multicast-Teilrouten, kanonische Beziehungen, Topologie, Routenfreigaben und neu dimensionierte Sendepläne/Capacity.
- Speichern verhindert erneutes Vermischen lokaler Einbauzonen. Intelligence nennt ungeklärte Einbauorte ausdrücklich. Die Darstellung verwendet kurze Busnamen mit VL/VR/HL/HR und ordnet bekannte Fahrzeugecken links/rechts sowie vorne/hinten an.

Unbekannte Positionen bleiben innerhalb ihres funktionalen Systems offen; sie werden nicht anhand einer beliebigen Nachbarschaft oder pauschal dem Motorraum zugewiesen. Mehrkanal-Multicast über zusätzliche Gateways benötigt explizite Pfade und wird bei Mehrdeutigkeit zurückgewiesen.

## Prüfung

- 89 gezielte Backend-Tests bestanden: Positionen, stabile Erzeugung, physische Ports, Zonierung, Umhängen, Topologie und Dimensionierung.
- 7 Frontend-Tests bestanden: Busbeschriftung, Szene und Auswahl.
- SQL/API-Test mit einer vollständigen Projektkopie in separater Datenbank: veraltete Vorschau zurückgewiesen; erzwungener Fehler nach kanonischen Schreiboperationen vollständig zurückgerollt; erfolgreiche Übernahme; erneutes Laden identisch; zweiter Plan ohne weitere Objekt-/Routenänderungen oder zusätzliche Kanäle.
- Die Projektkopie benötigt 21 zusätzliche lokale Segmente/Controllerkanäle (10 LIN, 11 CAN-FD). 93 betroffene Routen wurden erfolgreich validiert und freigegeben.

Reproduzierbare Prüfungen: `backend/tests/test_spatial_zoning.py` und `scripts/verify_spatial_zoning_sql.py`. Laufzeit-Sicherungen und Nachweise liegen unter `backend/runtime/zoning-*`.

## Produktiver Nachweis

Build `a87b1be40165` ist auf Port 13500/15050 aktiv. Die tatsächliche Übernahme wurde vorab als `zoning-live-backup.json` gesichert und als `zoning-live-receipt.json` dokumentiert. 261 eindeutige Geräte, 311 Nachrichten und 725 Signale bleiben erhalten; Bitlayout, Skalierung und DLC wurden mit der Sicherung verglichen.

| Dämpferzweig | Datenpublisher | Teilnehmer inkl. ECU | Mittlere Last | Ergebnis |
| --- | ---: | ---: | ---: | --- |
| Daempferregelung LIN VL | 2 | 3 | 13,33 % | NORMAL |
| Daempferregelung LIN VR | 2 | 3 | 13,33 % | NORMAL |
| Daempferregelung LIN HL | 2 | 3 | 13,33 % | NORMAL |
| Daempferregelung LIN HR | 2 | 3 | 13,33 % | NORMAL |

Federweg und Dämpferposition derselben Ecke teilen ihren jeweiligen Zweig. Der separate bisherige Aktor-Zweig bleibt bestehen; für seine generischen Aktoren ist kein Einbauort bestätigt. Vorher belegten die acht Sensoren gemeinsam einen Bus mit 53,33 % mittlerer Last.

Der Preflight hat **0 Fehler**, `ready_for_simulation=true`. Der reguläre 0,3-s-Smoke-Job `806220852521441d975336ddd1a4fcf8` ist `completed`, ohne Jobfehler. Capacity, Simulation und Intelligence bleiben aufgrund weiterer vorhandener Hinweise auf `WARNING`; es wird keine pauschale Gesamtfreigabe behauptet.

Intelligence berechnet die Ortsprüfung aus dem aktuellen Modell: **0 Zonenkonflikte, 135 lokale Geräte mit ungeklärtem Einbauort**. Diese offene Anforderung bleibt sichtbar. `zoning-live-recheck.json` bestätigt 0 weitere Objektänderungen, 0 neue Kanäle und 0 Routenänderungen.

Browserprüfung: alle vier kurzen Dämpferzweignamen und 13,33 % Last sichtbar; im Detail von LIN HL ausschließlich die beiden RearLeft-Sensoren. Die gespeicherte SQL-Szene enthält `LIN VL/VR/HL/HR` als Linienbeschriftung und passende Links-/Rechts-Spalten. Zusätzlich 25 Intelligence-Tests bestanden, insgesamt **114 gezielte Backend-Tests** plus die oben genannten 7 Frontend-Tests; TypeScript und Produktionsbuild erfolgreich.

## Branchenübergreifende Ergänzung

Die übergeordnete Nutzerregel zu Fahrzeugen, Drohnen, Robotern und Gebäuden
steht in `docs/SPATIAL_ARCHITECTURE_CONTRACT.md` und ist über `AGENTS.md`
eingebunden. Quelle: Nutzerauftrag vom 10.09.2026; Geltungsbereich: gesamte
Architektur-/KI-Generierung dieses Simulators. Mit den bestehenden Binding-
und Generator-Verträgen vereinbar. Die Fahrzeugvorgabe LHD bleibt bestehen.

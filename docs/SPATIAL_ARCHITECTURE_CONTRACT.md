# Raumcluster als allgemeine Architekturgrundlage

Verbindliche Projektregel, aufgenommen am 10.09.2026 aus der Nutzeranforderung
zur branchenübergreifenden räumlichen Aufteilung und KI-Generierung.
Ergänzt die Binding-/Generator-Verträge unter `docs/technology_bindings`.
Fahrzeuganwendung: `docs/spatial-zoning-verification-2026-09-10.md`.

## Drei unabhängige Zuordnungen

Jedes Gerät besitzt eine fachliche Funktion/Verantwortung, einen physischen
Einbauort in einem Bezugsrahmen und physische Kommunikationsanschlüsse.
Diese Angaben dürfen nicht gegenseitig als Beweis verwendet werden.
Ein gemeinsamer Flugregler macht vier Rotoren nicht räumlich identisch.
Ein Busname bestimmt weder Bustyp noch Einbauort; eine Funktion bestimmt
keinen Einbauort ihrer Sensoren oder Aktoren.

Raumcluster können Fahrzeugzonen, Rotorarme, Roboterbereiche, Maschinenzellen,
Etagen oder Räume beschreiben. Hierarchische Raumkennungen bleiben eindeutig:
„Raum 1“ in verschiedenen Etagen ist nicht derselbe Raum. Ein Raumcluster
legt keine bestimmte Anzahl von Bussen oder Teilnehmern fest.

## Entscheidung und Herkunft

1. Bestätigte Hardware-Identität und explizite Projektzuordnung lesen.
   Gegensätzliche Bestätigungen oder Bezugsrahmen als Konflikt behandeln.
2. Ohne Bestätigung nur eindeutige vollständige Positionswörter ableiten.
   Fahrer/Beifahrer benötigt die Lenkungsseite. „Fahrerassistenz“ und „Fahrwerk“
   bezeichnen keine Fahrerseite.
3. Zahlen, Drehsinn und Funktionsnamen belegen keinen Ort. „Motor 1–4“ einer
   Drohne benötigt eine konkrete Geometrie/Motorzuordnung. Vier Rotoren
   bedeuten insbesondere nicht automatisch eine X-Geometrie.
4. Bei benannten Räumen die explizite Zuordnung verwenden. Keine globalen
   Links-/Rechts-Gruppen über mehrere Räume oder Maschinen hinweg erzeugen.
5. Entscheidung, Quelle, Bezugsrahmen und Status CONFIRMED, DERIVED oder
   UNRESOLVED speichern. Unbekannte Orte sichtbar offen lassen. Frühere
   Projekte liefern Vorschläge, keine Bestätigung für das aktuelle Projekt.

Das KI-Reasoning soll diese Prüfungen anwenden und kurz begründen, bevor es
Zuordnungen vorschlägt. Größere Modellkapazität ersetzt keine Fachprüfung.

## Physische Planung

Lokale Zweige nach funktionalem Owner, Technologie und Raumcluster planen;
erst danach Ressourcen, Teilnehmergrenzen, Kapazität, Zeitverhalten und
Rückmeldungen prüfen. Controller-Backbones bzw. ausdrücklich als `backbone`
deklarierte Netze gesondert behandeln. Raumcluster verlangen weder eine
elektrische Sternschaltung eines CAN/LIN-Busses noch automatisch einen
Technologiewechsel.

Automatisches Trennen ist derzeit für modellierte lokale LIN-, CAN-, CAN-FD-,
CAN-XL- und FlexRay-Zweige integriert. Andere Technologien behalten ihre
eigene Topologie und werden über ihre Technologieverträge bewertet.
Bestätigte harte Hardwaregrenzen bleiben verbindlich. Neue Kanäle sind
Planungsbedarf. Keine automatische Zusammenlegung bereits getrennter Busse.

Eine bestätigte Umzuordnung betrifft Hardware-Identitäten, Anschlüsse,
Nachrichtenbindungen, Routen, SQL-Topologie und abgeleitete Berechnungen.
Sie muss atomar validiert werden; ein bloß verschobenes Bild genügt nicht.

## Gemeinsamer Datenvertrag

`parameters.spatial_architecture`, alternativ im strukturierten Wizard-Prompt
als einzeiliges `- Raumarchitektur: {...}`:

```json
{
  "reference_frame": "Building-A",
  "zones": [
    {"id": "floor1", "label": "Etage 1"},
    {"id": "floor1/room1", "label": "Raum 1", "parent_id": "floor1"},
    {"id": "floor1/room2", "label": "Raum 2", "parent_id": "floor1"}
  ],
  "assignments": {"TemperatureSensor1": "floor1/room1", "TemperatureSensor2": "floor1/room2"}
}
```

Zuordnungsschlüssel sind kanonische Hardware-IDs oder exakte Namen,
ohne Unterscheidung der Groß-/Kleinschreibung. Benutzerdefinierte Zonen
benötigen einen expliziten Bezugsrahmen. Zyklen, fehlende Elternräume,
doppelte Kennungen und widersprüchliche Zuordnungen werden zurückgewiesen.

Ohne benannte Räume gelten relative Positionscodes FL/FR/RL/RR,
F/R/L/RIGHT, UPPER/LOWER/CENTER; UNKNOWN bleibt offen. Kombinationen,
bei denen eine dritte Achse verloren ginge, benötigen eine benannte Zone.
Hardware-Identitäten verwenden `installation_zone`,
`installation_zone_source`, `installation_reference_frame` und
`spatial_decision`. Frei erfundene Zuordnungen dürfen nicht als bestätigt
deklariert werden. Separate Parameterformulare erhalten diese Definition.

## Laufzeit und Grenzen

Gemeinsame Implementierung: `backend/engineering/spatial_architecture.py`.
Wizard und `spatial_zoning.py` verwenden dieselbe Auflösung; Intelligence
berechnet den Befund aus dem aktuellen Modell. Das MCP-Werkzeug
`inspect_spatial_architecture` liefert Quellen und Konflikte und unterstützt
eine gezielte Gerätesuche. Die lokale KI erhält die Grundregeln bei jedem
Aufruf; räumliche Architekturfragen nutzen das konfigurierte Hauptmodell.

Dies ist überprüfbare Architekturkenntnis im Laufzeitkontext, kein Training
der Modellgewichte. Freitext allein liefert noch keine vermessene Geometrie.
Die grafische automatische Platzierung unterstützt weiterhin die bekannten
relativen Positionen; benannte Raumhierarchien sind keine CAD-Darstellung.

Referenzprüfung: PX4 trennt Geometrie (Anzahl und Position der Motoren),
Ausgangszuordnung und Drehrichtung und definiert dafür einen Bezugsrahmen.
Das stützt die Trennung dieser Angaben; es schreibt keine Busaufteilung vor.
[PX4: Actuator Configuration and Testing](https://docs.px4.io/main/en/config/actuators).

## Verifikation am 10.09.2026

Build `6f88ce1d4c86` ist im laufenden NIS aktiv. 200 Backend-Tests bestanden:
178 gezielte Raum-/Topologie-/Intelligence-/Agent-Prüfungen und 22 Prüfungen
für Wizard, physische Snapshots und Laufzeitkommunikation. Produktionsbuild
inklusive TypeScript erfolgreich.

Die Tests umfassen vier Rotorpositionen, explizit zugeordnete Motoren 1–4,
fehlende Geometrie, Roboter-Owner ohne belegte Co-Lokation, verschachtelte
Gebäuderäume, unzulässige Hierarchien, widersprüchliche Bestätigungen,
Erhalt der Raumdefinition bei Parameteränderungen sowie lokale Zweige
gegenüber ausdrücklich gemeinsam genutzten Backbones.

Vollständige SQL-Projektkopie in separater Datenbank: veraltete Vorschau
zurückgewiesen; Fehler nach Schreiboperationen vollständig zurückgerollt;
21 zusätzliche Kanäle und 93 Routen konsistent übernommen/validiert;
wieder geladene Topologie identisch; Folgeplanung ohne weitere Änderungen.
Testprojekt: `pytest-zoning-7194dd4b-6619-4007-8548-f168c43dc953`.

Zusätzlich wurde ein durch den Gesamtlauf aufgedeckter Fehler behoben:
Ein LIN-Sendeplatz darf beim Gateway-Übergang nicht auf den CAN-Abschnitt
vererbt werden. Jeder physische Abschnitt verwendet seinen eigenen Sendeplan.
Gezielter Laufzeittest und kompletter Wizard-/Simulationslauf bestanden.

Das neue MCP-Werkzeug wurde im laufenden Dienst projektbezogen geprüft,
ohne Modellversionen zu verändern. Intelligence wurde neu berechnet:
82 bekannte Orte, 135 offene lokale Geräte, 0 Zonenkonflikte. Die vorhandene
Fahrzeugzuordnung wurde durch diese Generalisierung nicht umgehängt.
Die Regeln sind im KI-Kontext und Werkzeugvertrag nachgewiesen; die Prüfung
der Modellwahl verwendet einen kontrollierten Inferenz-Dummy und behauptet
kein Training oder eine allgemeine Qualitätsgarantie des Sprachmodells.

Nachweise: `backend/runtime/spatial-architecture-sql-result.txt`,
`spatial-wizard-final.txt`, `spatial-architecture-live-audit.json` und
`spatial-architecture-intelligence-live.json` im selben Laufzeitverzeichnis.

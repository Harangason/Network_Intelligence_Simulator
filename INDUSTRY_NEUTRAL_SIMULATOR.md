# Industry Neutral Simulator Directive

## Verbindliche Anweisung

Dieser Simulator muss industrie- und domaenneutral funktionieren.

Automotive ist in diesem Projekt nur ein Test- und Referenzprofil fuer die
Funktion. Automotive darf nicht als Grundannahme fuer Architektur, Datenmodell,
Signalnamen, Hardwaremodell, Routing, Timing, Fehlermodelle oder Exportlogik
verwendet werden.

Wenn ein Projekt aus einem anderen Fachbereich nicht sauber auf bestehende
Automotive-nahe Programmpfade passt, muessen eigene neutrale oder
branchenspezifische Programmpfade ergaenzt werden. Das gilt insbesondere fuer:

- Robotics und ROS/ROS2 Architekturen
- Aerospace und Avionik-/Satelliten-/UAV-Systeme
- Industrial Automation und Maschinen-/Anlagenkommunikation
- Rail, Marine, Energy, Medical und weitere technische Domaenen
- Generische Embedded-, Sensor-, Gateway- und Kommunikationssysteme

## Architekturregel

Der Kern des Simulators muss mit neutralen Begriffen arbeiten:

- `participant`, `node`, `service`, `signal`, `hardware`, `bus`, `port`,
  `route`, `channel`, `interface`

Branchenspezifische Begriffe duerfen nur in Profilen, Import-Adaptern,
Suggestion-Katalogen oder Szenario-Layern vorkommen:

- Automotive: `ecu`, `adas`, `brake`, `powertrain`
- ROS/ROS2: `node`, `topic`, `publisher`, `subscriber`, `service`, `action`
- Aerospace: `flight_controller`, `sensor_bus`, `payload`, `telemetry`,
  `command`, `redundancy`
- Industrial: `plc`, `fieldbus`, `io_module`, `drive`, `safety_controller`

## Pflichtverhalten

- Importierte externe Profile werden erhalten und nicht still auf Automotive
  umgebogen.
- Jede Domain bekommt bei Bedarf eigene Mapping- und Suggestion-Logik.
- Der Simulator darf fehlende Informationen vorschlagen, aber nicht automatisch
  fremde Fachmodelle veraendern.
- Trace-Erzeugung und Hardwareauswertung muessen auch ohne Automotive-Begriffe
  funktionieren.
- Neue Features muessen mindestens gegen ein Automotive- und ein
  Nicht-Automotive-Beispiel gedacht oder getestet werden.

## Domaenenpfade

Die Branchenprofile liegen unter `physic_lib/Industries/`.

Vorgesehene Struktur:

```text
physic_lib/Industries/
  Generic/
  Automotive/
  RoboticsROS/
  Aerospace/
  IndustrialAutomation/
  Rail/
  Marine/
  Energy/
  Medical/
```

Jede Domain kann eigene Profile, Requests, Hardwaretopologien,
Signal-/Service-Mappings und Lernspeicher enthalten. Der Simulator darf daraus
laden, muss aber immer auf ein neutrales internes Request-Modell abbilden.

## ROS/ROS2 Programmpfad

ROS/ROS2 Projekte sollen nicht kuenstlich wie Fahrzeug-ECUs behandelt werden.
Ein ROS/ROS2 Adapter soll folgende Konzepte neutral abbilden:

- ROS Node -> Simulator Participant/Node
- Topic -> provided/consumed Service oder Signalstream
- Publisher -> provided Service
- Subscriber -> consumed Service
- Service/Action -> bidirektionaler Request/Response-Pfad
- QoS, Rate und Deadline -> Timing/Jitter/Dropout-Modell
- DDS Domain, Namespace und Remapping -> Routing-/Channel-Metadaten

## Aerospace Programmpfad

Aerospace Projekte sollen eigene Topologie- und Sicherheitsannahmen bekommen:

- Flight Controller, Payload Controller, Sensor Unit, Actuator Unit als Nodes
- Telemetry, Command, Navigation, Health und Payload Data als Services
- Redundante Busse und Fallback-Pfade als Hardware-/Routing-Metadaten
- Deterministische Timingfenster, Latenzgrenzen und Health-Monitoring
- Fault Containment, Degraded Mode und Safe Mode als Fault-/Health-Modell

## Definition of Done

Die Industrie-Neutralitaet gilt als erreicht, wenn:

- ein Automotive-Profil und mindestens ein Nicht-Automotive-Profil denselben
  Generatorpfad nutzen koennen,
- ROS/ROS2- oder Aerospace-Profile ohne Automotive-Begriffe importierbar sind,
- Hardware- und Signal-Suggestions domaenspezifisch, aber intern neutral sind,
- Manifest und `simulation_interface.json` die Domain ausweisen,
- neue branchenspezifische Pfade keine Automotive-Abhaengigkeit erzwingen.

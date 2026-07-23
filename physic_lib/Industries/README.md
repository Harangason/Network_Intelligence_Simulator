# Branchenspezifische Generatoren

Der Simulationskern bleibt technologie- und branchenneutral. Dieser Ordner
enthält ausschließlich fachlich gruppierte Technologieprofile. Hardware,
Ports, Netzwerk-Schnittstellen, Netzwerke, Routen und Trace-Events verwenden
in allen Branchen dasselbe Standalone-Kernmodell.

## Klassenmodell

`generator_base.py` definiert:

- `TechnologyProfile`: unveränderliches, serialisierbares Datenmodell
- `BaseTechnologyGenerator`: abstrakte Basis jeder Fachdomäne

`registry.py` definiert `TechnologyRegistry`. Die Registry instanziiert alle
Fachgeneratoren, erkennt doppelte Technologie-IDs und kombiniert eingebaute
mit benutzerdefinierten Profilen.

Jede Domäne besitzt den gleichen Einstieg:

```text
<Domain>/
├─ __init__.py
└─ generators/
   ├─ __init__.py
   └─ technology_generator.py
```

## Domänen und Zuständigkeiten

| Domäne | Generator-Klasse | Technologien |
|---|---|---|
| Automotive | `AutomotiveTechnologyGenerator` | CAN, CAN FD/XL, LIN, FlexRay, MOST, Automotive Ethernet, CANopen, J1939, SOME/IP, DoIP |
| IndustrialAutomation | `IndustrialTechnologyGenerator` | PROFIBUS, PROFINET, EtherCAT, EtherNet/IP, Modbus, DeviceNet, Sercos, IO-Link, OPC UA |
| EmbeddedSystems | `EmbeddedTechnologyGenerator` | I²C, SPI, UART, RS-232/422/485, 1-Wire, USB, PCIe |
| Aerospace | `AerospaceTechnologyGenerator` | ARINC 429/664/825, MIL-STD-1553, SpaceWire |
| Rail | `RailTechnologyGenerator` | MVB, WTB, ETB, TRDP |
| Marine | `MarineTechnologyGenerator` | NMEA 0183/2000, IEC 61162 |
| BuildingAutomation | `BuildingTechnologyGenerator` | KNX, BACnet MS/TP und BACnet/IP |
| Energy | `EnergyTechnologyGenerator` | IEC 61850, DNP3 |
| RoboticsROS | `RoboticsTechnologyGenerator` | DDS/RTPS, ROS 2 |
| Generic | `GenericNetworkTechnologyGenerator` | Ethernet, IPv4/IPv6, UDP, TCP |

## Neue Technologie ergänzen

1. Technologie im fachlich passenden `technology_generator.py` ergänzen.
2. Bei einer neuen Branche von `BaseTechnologyGenerator` erben.
3. Die neue Generator-Klasse in `TechnologyRegistry.DEFAULT_GENERATORS`
   registrieren.
4. Registry- und Simulationstests ausführen.

Projektspezifische oder proprietäre Busse müssen nicht in den Quellcode
aufgenommen werden. Sie können weiterhin über `technology_profiles` in der
Standalone-Konfiguration registriert werden.

## Industriespezifisches Lernen

Jeder Simulationslauf wird genau einer Branche zugeordnet. `IndustryContext`
normalisiert Namen und Aliase, beispielsweise `industrial` zu
`IndustrialAutomation` und `ros2` zu `RoboticsROS`.

Die Speicher werden bei Bedarf automatisch angelegt:

```text
<Domain>/
├─ Learning/
│  └─ simulation_memory.db
└─ Knowledge/
   └─ knowledge_graph.db
```

`simulation_memory.db` enthält Laufparameter, Kennzahlen, Befunde und
Verweise auf Trace-Artefakte. `knowledge_graph.db` enthält keine vollständigen
Trace-Events, sondern fachliche Knoten und Kanten wie:

- `Industry HAS_RUN SimulationRun`
- `SimulationRun INVOLVES Hardware`
- `Hardware HAS_PORT Port`
- `Port EXPOSES_INTERFACE NetworkInterface`
- `NetworkInterface CONNECTED_TO Network`
- `Network USES_TECHNOLOGY Technology`
- `SimulationRun PRODUCED_FINDING Finding`

Alte Datenbanken unter einem kleingeschriebenen `learning/` werden beim ersten
Zugriff sicher übernommen; die Quelldatei bleibt dabei erhalten.

# Communication Simulator

Der Communication Simulator ist eine eigenständige, technologieoffene
Kommunikationssimulation. Er modelliert Hardware, physische Ports, logische
Netzwerk-Schnittstellen, Netzwerke, Nachrichten, Timing und Fehler unabhängig
von einer bestimmten Branche oder einem bestimmten Engineering-Werkzeug.

Der universelle Simulationskern unterstützt jede integrierte oder
benutzerdefinierte Bus-Technologie. Für CAN und Ethernet stehen zusätzlich
native Writer zur Verfügung.

## Architektur

Das Kernmodell trennt vier Ebenen:

```text
Hardware
  └─ physischer Port
       └─ logische Netzwerk-Schnittstelle
            └─ Bus oder Netzwerk
```

Beispiel: Eine ECU kann zwei CAN-FD-Ports, einen LIN-Port und einen
Ethernet-Port besitzen. Auf dem Ethernet-Port können mehrere logische
Schnittstellen mit eigenen VLANs, IP-Adressen und Protokollen liegen.

Die Implementierung ist ebenfalls geschichtet:

```text
CommunicationSimulator
├─ HardwareProfileService
│  ├─ HardwareProfileNormalizer
│  └─ HardwareProfileValidator
├─ TechnologyRegistry
│  └─ branchenspezifische BaseTechnologyGenerator-Klassen
└─ UniversalTraceGenerator
   ├─ JsonLinesTraceWriter
   └─ CsvTraceWriter
```

Der optionale KI-Assistent verwendet zusätzlich eine industriespezifische
Speicherschicht:

```text
IndustryContext
└─ IndustryKnowledgeService
   ├─ IndustryMemoryStore → Industries/<Domain>/Learning/simulation_memory.db
   └─ KnowledgeGraphStore → Industries/<Domain>/Knowledge/knowledge_graph.db
```

Der Knowledge Graph speichert Topologie-, Profil-, Technologie- und
Fehlerbeziehungen. Vollständige Trace-Events verbleiben ausschließlich unter
`traces/`.

Die Technologieprofile liegen nicht im Simulationsskript, sondern in
`physic_lib/Industries/<Branche>/generators/technology_generator.py`.
`bus_technologies.py`, `hardware_profile.py` und `universal_trace.py` behalten
ihre bisherigen Funktions-APIs als schlanke Kompatibilitätsfassaden.

Aktuelle Generatorbereiche:

- `Automotive`
- `IndustrialAutomation`
- `EmbeddedSystems`
- `Aerospace`
- `Rail`
- `Marine`
- `BuildingAutomation`
- `Energy`
- `RoboticsROS`
- `Generic`

Ein neuer Fachgenerator erbt von `BaseTechnologyGenerator`, implementiert
`generate()` und wird in `TechnologyRegistry.DEFAULT_GENERATORS` registriert.

## Unterstützte Technologien

Die eingebaute Registry enthält mehr als 50 Bus- und Protokollprofile:

- Automotive: Classic CAN, CAN FD, CAN XL, LIN, FlexRay, MOST, Automotive
  Ethernet, CANopen, J1939, SOME/IP und DoIP
- Industrial: PROFIBUS, PROFINET, EtherCAT, EtherNet/IP, Modbus RTU/TCP,
  DeviceNet, Sercos, IO-Link und OPC UA
- Embedded: I²C, SPI, UART, RS-232, RS-422, RS-485, 1-Wire, USB und PCIe
- Aerospace/Defense: ARINC 429, ARINC 664/AFDX, ARINC 825,
  MIL-STD-1553 und SpaceWire
- Rail: MVB, WTB, ETB und TRDP
- Marine: NMEA 0183, NMEA 2000 und IEC 61162
- Building/Energy: KNX, BACnet MS/TP/IP, IEC 61850 und DNP3
- Robotics: DDS/RTPS und ROS 2
- Allgemein: Ethernet, IPv4, IPv6, UDP und TCP

Proprietäre Technologien werden über `technology_profiles` beschrieben und
dann wie integrierte Technologien simuliert. Der Kern besitzt deshalb keine
geschlossene Liste erlaubter Busse.

Alle Technologien unterstützen den neutralen JSONL-/CSV-Trace. Native
Dateiformate sind technologieabhängig:

| Bereich | Native Formate |
|---|---|
| CAN/CAN FD | BLF, DBC, ASC, TRC, CSV, JSON, XML, YAML, ARXML, FIBEX |
| CAN XL | universeller Trace; BLF bei Bedarf CAN-FD-kompatibel |
| Ethernet/IP-basierte Technologien | PCAP und PCAPNG |
| Messdaten | optional MDF und MF4 |
| alle anderen Technologien | universeller JSONL-/CSV-Trace |

## Installation

Voraussetzungen:

- Python 3.14 oder neuer
- `uv` empfohlen

```powershell
uv sync
```

Alternativ:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install python-can openai
```

MDF/MF4 benötigen zusätzlich:

```powershell
python -m pip install asammdf
```

## Schnellstart

Der umfassendste Einstieg ist die technologieoffene CLI:

```powershell
python generate_realistic_communication_tool.py
```

Ohne Parameter führt sie interaktiv durch:

1. technologieoffene Standalone-Simulation oder native CAN/Ethernet-Ausgabe
2. Branche und eine der 54 registrierten Technologien
3. Bitrate und Anzahl der Hardware-Knoten
4. Dauer, Zyklus und Payload-Größe
5. Seed und maximales Eventlimit
6. Dropout- und Korruptionswahrscheinlichkeit
7. Ausgabeformate und Zielordner

Alle Technologien anzeigen:

```powershell
python generate_realistic_communication_tool.py --list-technologies
```

Nicht-interaktives Aerospace-Beispiel:

```powershell
python generate_realistic_communication_tool.py `
  --technology arinc429 `
  --industry Aerospace `
  --bitrate 100000 `
  --nodes 3 `
  --duration 5 `
  --cycle-ms 20 `
  --payload-bytes 4 `
  --max-events 10000 `
  --dropout-probability 0.01 `
  --corruption-probability 0.001 `
  --formats universal-jsonl,universal-csv `
  --out-dir aerospace_demo
```

Industrial-Automation-Beispiel:

```powershell
python generate_realistic_communication_tool.py `
  --technology modbus_tcp `
  --nodes 4 `
  --cycle-ms 50 `
  --payload-bytes 64 `
  --duration 10 `
  --out-dir modbus_demo
```

Der bisherige native CAN/Ethernet-Pfad bleibt erreichbar:

```powershell
python generate_realistic_communication_tool.py `
  --native-cli `
  --bus fd `
  --formats blf,dbc,asc `
  --out-dir native_can_demo
```

Konfigurationsvorlage erstellen:

```powershell
uv run python communication_simulator.py `
  --write-config-template simulation_config.json
```

Simulation starten:

```powershell
uv run python communication_simulator.py --config simulation_config.json
```

Technologiekatalog anzeigen:

```powershell
uv run python communication_simulator.py --list-technologies
```

Nur Topologie und Hardware validieren:

```powershell
uv run python communication_simulator.py `
  --config simulation_config.json `
  --validate-only
```

Relative Ausgabeordner werden unter `traces/` abgelegt. Absolute Zielpfade
werden respektiert.

## Standalone-Konfiguration

```json
{
  "schema": "communication-simulator.simulation-config.v1",
  "name": "multi_bus_system",
  "output_dir": "multi_bus_system",
  "duration_s": 2.0,
  "seed": 42,
  "formats": [
    "universal-jsonl",
    "universal-csv",
    "blf",
    "dbc",
    "pcapng"
  ],
  "networks": [
    {
      "id": "control_can",
      "technology": "can_fd",
      "nominal_bitrate": 500000,
      "data_bitrate": 2000000
    },
    {
      "id": "sensor_bus",
      "technology": "i2c",
      "bitrate": 400000
    }
  ],
  "hardware": [
    {
      "id": "controller",
      "type": "ecu",
      "health": "nominal",
      "ports": [
        {
          "id": "controller_can1",
          "physical_type": "can",
          "network_interfaces": [
            {
              "id": "controller_can_if",
              "technology": "can_fd",
              "network": "control_can",
              "channel": 0
            }
          ]
        },
        {
          "id": "controller_i2c0",
          "physical_type": "i2c",
          "network_interfaces": [
            {
              "id": "controller_i2c_if",
              "technology": "i2c",
              "network": "sensor_bus",
              "address": "controller"
            }
          ]
        }
      ]
    }
  ],
  "communications": [
    {
      "id": "temperature",
      "sender_interface": "sensor_i2c_if",
      "receivers": ["controller_i2c_if"],
      "cycle_ms": 100,
      "payload_bytes": 4
    }
  ]
}
```

Wenn `communications` fehlt, erzeugt der Simulator für Netzwerke mit mindestens
zwei Schnittstellen reproduzierbare Standardrouten.

## Eigene Bus-Technologie

```json
{
  "technology_profiles": [
    {
      "id": "vendor_bus_x",
      "kind": "bus",
      "family": "custom",
      "medium": "fiber",
      "topology": "ring",
      "access": "time_triggered",
      "addressing": "node_id",
      "default_bitrate": 25000000,
      "max_payload_bytes": 128,
      "native_formats": []
    }
  ],
  "networks": [
    {
      "id": "vendor_network",
      "technology": "vendor_bus_x"
    }
  ]
}
```

Ein unbekannter Technologiename wird nicht abgewiesen. Ohne Profil verwendet
der Simulator generische Annahmen und meldet eine Warnung. Mit einem eigenen
Profil werden Payload-Grenzen und Technologiemetadaten berücksichtigt.

## Python-API

```python
from communication_simulator import CommunicationSimulator

simulator = CommunicationSimulator()
result = simulator.run(
    {
        "schema": "communication-simulator.simulation-config.v1",
        "output_dir": "api_demo",
        "duration_s": 1,
        "formats": ["universal-jsonl", "universal-csv"],
        "networks": [{"id": "serial", "technology": "rs485"}],
        "hardware": [
            {
                "id": "controller",
                "ports": [
                    {
                        "id": "rs485_a",
                        "network_interfaces": [
                            {
                                "id": "controller_if",
                                "technology": "rs485",
                                "network": "serial",
                            }
                        ],
                    }
                ],
            }
        ],
    }
)

print(result["status"])
print(result["artifacts"])
```

Die bisherige Funktion `run_simulation(config)` bleibt weiterhin verfügbar.

## Ausgabe

```text
traces/<lauf>/
  traces/
    universal_trace.jsonl
    universal_trace.csv
  native/
    traces/
    datenbasen/
    generation_manifest.json
    simulation_interface.json
  generation_manifest.json
  simulation_result.json
```

`generation_manifest.json` enthält:

- Hardware-, Port-, Schnittstellen- und Netzwerkanzahl
- verwendete Technologien
- Validierungsbefunde
- Routen- und Eventanzahl
- erzeugte Artefakte
- Status der nativen Writer

## Hardwarevalidierung

Die Validierung verändert importierte Definitionen nicht. Sie meldet:

- doppelte Hardware-, Port-, Schnittstellen- oder Netzwerk-IDs
- Schnittstellen ohne Netzwerk
- Verweise auf unbekannte Netzwerke
- Ports ohne logische Schnittstelle
- Hardware ohne Ports
- ungenutzte Netzwerke
- Technologien ohne integriertes oder benutzerdefiniertes Profil

## Native CAN-/Ethernet-Werkzeuge

`generate_realistic_communication_tool.py` bleibt als spezialisierter nativer
Writer erhalten. Sein öffentlicher Konfigurationseinstieg ist neutral:

```powershell
uv run python generate_realistic_communication_tool.py `
  --write-config-template native_config.json

uv run python generate_realistic_communication_tool.py `
  --config native_config.json
```

Für neue Projekte ist `communication_simulator.py` der primäre Einstieg.

## Projektstruktur

```text
communication_simulator.py                 Standalone-CLI und Python-API
bus_technologies.py                        offene Technologie-Registry
hardware_profile.py                        Hardware-/Port-/Netzwerkmodell
universal_trace.py                         neutraler Event- und Trace-Kern
generate_realistic_communication_tool.py   native CAN-/Ethernet-Writer
format_generators/                         formatspezifische Writer
trace_realism.py                           synthetische Signalmodelle
signal_suggestions.py                      Signalvalidierung
nemotron.py                                optionaler Szenarioassistent
tests/                                     Standalone-Regressionstests
traces/                                    ausschließlich Laufzeitausgaben
```

Weiterführend:

- [Standalone-Schnittstelle](SIMULATION_INTERFACE.md)
- [Hardware- und Netzwerkmodell](HARDWARE_INTERFACE_ROADMAP.md)
- [Industrieneutrale Architektur](INDUSTRY_NEUTRAL_SIMULATOR.md)
- [Format-Writer](format_generators/README.md)
- [Aktueller Stand](CURRENT_STATUS.md)

## Grenzen

- Ein universeller Trace kann jede registrierte Technologie darstellen. Ein
  binäres natives Herstellerformat benötigt trotzdem einen eigenen Writer.
- CAN XL wird vom vorhandenen BLF-Writer noch nicht als natives
  CAN-XL-Frameobjekt unterstützt.
- Das Zeit- und Fehlermodell ist synthetisch und reproduzierbar, aber kein
  zertifiziertes Anlagen- oder Physikmodell.

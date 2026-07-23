# Current Status

Stand: 2026-07-23

## Umgesetzt

- eigenständige Standalone-CLI und Python-API
- neutrales Schema `communication-simulator.simulation-config.v1`
- Hardware → Port → Netzwerk-Schnittstelle → Netzwerk
- offene Registry mit mehr als 50 integrierten Technologien
- frei definierbare proprietäre Technologieprofile
- universeller JSONL-/CSV-Trace für alle Technologien
- native CAN-/CAN-FD-, Ethernet- und IP-Writer als Adapter
- Hardware- und Topologievalidierung ohne automatische Quelländerung
- neutrale Manifest- und Ergebnisdateien
- vorhandene Signalrealismus-, Filter- und Fault-Funktionen im nativen Adapter

## Native Grenzen

- CAN XL wird im vorhandenen BLF-Writer CAN-FD-kompatibel gespeichert.
- Native Herstellerformate benötigen jeweils einen eigenen Writer.
- MDF/MF4 benötigen `asammdf`.
- Das universelle Timingmodell ist synthetisch und nicht zertifiziert.

## Nächste sinnvolle Ausbaustufen

1. technologiespezifische Arbitration und Buslastberechnung
2. weitere native Writer für LIN, FlexRay, ARINC und industrielle Busse
3. Gateway-Latenz und Clock-Domain-Simulation
4. elektrische Fehler- und Terminierungsmodelle
5. Importer für verbreitete Netzwerkbeschreibungen

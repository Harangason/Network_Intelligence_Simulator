# Standalone Simulation Interface

Der primäre Einstieg ist `communication_simulator.py`. Er akzeptiert eine
neutrale JSON-Konfiguration und benötigt keine externe Plattform.

## Schemas

- Konfiguration: `communication-simulator.simulation-config.v1`
- Hardware: `communication-simulator.hardware.v1`
- Ergebnis: `communication-simulator.simulation-result.v1`
- Manifest: `communication-simulator.generation-manifest.v1`

## CLI

```powershell
uv run python communication_simulator.py --write-config-template simulation_config.json
uv run python communication_simulator.py --config simulation_config.json
uv run python communication_simulator.py --config simulation_config.json --validate-only
uv run python communication_simulator.py --list-technologies
```

## Python

```python
from communication_simulator import run_simulation

result = run_simulation(config)
```

## Konfigurationsbereiche

- `hardware`: Geräte, Steuerungen, Sensoren, Aktoren und Gateways
- `ports`: physische Anschlüsse eines Hardwareelements
- `network_interfaces`: logische Schnittstellen auf einem Port
- `networks`: Busse, Cluster und paketbasierte Netze
- `technology_profiles`: proprietäre oder angepasste Technologien
- `communications`: Sender, Empfänger, Zyklus und Payload
- `formats`: universelle und native Ausgabeformate

## Ergebnis

`simulation_result.json` enthält Status, Artefaktpfade, Hardwarevalidierung und
Trace-Zusammenfassung. `generation_manifest.json` ergänzt den vollständigen
Technologiekatalog, Warnungen und Reproduzierbarkeitsmetadaten.

Der universelle Trace verwendet ein gemeinsames Ereignismodell für alle
Technologien. Jedes Ereignis enthält Zeit, Route, Technologie, Netzwerk,
Hardware, Port, Schnittstelle, Empfänger und Payload.

# MBSE Simulation Interface

`generate_realistic_communication_tool.py` now supports two simulation modes:

- `existing`: uses the existing routing table/default communication generator.
- `restbus`: derives CAN routes from modeled participants and their provided/consumed services.

## CLI

Create a request template:

```powershell
py generate_realistic_communication_tool.py --write-mbse-template mbse_simulation_request.json
```

Run a restbus simulation directly:

```powershell
py generate_realistic_communication_tool.py --simulation-mode restbus --formats blf,dbc,json,csv --out-dir generated_restbus
```

Run from an MBSE request:

```powershell
py generate_realistic_communication_tool.py --mbse-request mbse_simulation_request.json
```

The result interface is written as `simulation_interface.json` in the output folder unless `--interface-out` is provided.

## Request Shape

```json
{
  "schema": "can-simulator.mbse-simulation-request.v1",
  "simulation_mode": "restbus",
  "output_dir": "generated_restbus_simulation",
  "formats": "blf,dbc,json,csv",
  "duration_s": 10.0,
  "bus_type": "fd",
  "channels": 4,
  "messages": null,
  "nominal_bitrate": 500000,
  "data_bitrate": 2000000,
  "seed": 42,
  "participants": [
    {
      "name": "ADAS_DOMAIN",
      "role": "domain_controller",
      "channel": 0,
      "cycle_ms": 20,
      "provided_services": ["TRAJECTORY_PLAN"],
      "consumed_services": ["OBJECT_LIST", "BRAKE_STATUS"],
      "gateway_to_channel": 1,
      "health": "nominal"
    }
  ]
}
```

`health` may be `nominal`, `degraded`, `faulty`, `offline`, `disabled`, or `not_available`.
Offline/disabled participants are not routed. Degraded/faulty participants keep participating, but their route cycle is stretched.

## Python API

```python
from generate_realistic_communication_tool import run_mbse_simulation_request

result = run_mbse_simulation_request({
    "simulation_mode": "restbus",
    "output_dir": "generated_restbus_simulation",
    "formats": "blf,dbc,json,csv",
    "duration_s": 5,
    "channels": 4,
})
```

The returned dict matches the written `simulation_interface.json` and includes artifact paths, routing rows, participant metadata, warnings, and bus settings.

## External Profile Import

`nemotron.py` can create the MBSE request from an external project/topology file. This is the handoff point for embedding the simulator in another toolchain.

Create an import template:

```powershell
py nemotron.py --write-import-template imported_profile.json
```

Convert the imported topology into a simulation request:

```powershell
py nemotron.py --import-profile imported_profile.json --out generated_request.json --emit-handoff handoff.json
```

Optionally install the imported topology as a reusable project profile:

```powershell
py nemotron.py --import-profile imported_profile.json --install-imported-profile --import-industry Industrial
```

Accepted import schema:

```json
{
  "schema": "can-simulator.profile-import.v1",
  "industry": "Automotive",
  "project_key": "external_vehicle_platform",
  "description": "Imported topology from another project",
  "package_mode": "mixed",
  "channels": 5,
  "participants": [
    {
      "name": "LIDAR_FRONT",
      "role": "lidar_sensor",
      "channel": 1,
      "cycle_ms": 20,
      "provided_services": ["OBJECT_LIST"],
      "consumed_services": ["SYNC_TIME"]
    }
  ]
}
```

Aliases are supported for non-automotive imports:

- `nodes` or `devices` instead of `participants`
- `publishes`, `signals`, or `outputs` instead of `provided_services`
- `subscribes`, `inputs`, or `commands` instead of `consumed_services`
- `period_ms` or `cycle` instead of `cycle_ms`

The generated handoff file uses schema `can-simulator.integration-handoff.v1` and contains the resolved request path, CLI command, Python API entry point, package mode, formats, industry, and participant count.

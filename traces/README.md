# traces

Emulated communication traces are written here.

## Structure

- `Automotive/<YYYY_MM_DD_HH_MM>_<scenario>/`
  One generated trace package per simulation run.

Each package can contain:

- `traces/`
  BLF, ASC, TRC, CSV, JSON, LOG, TXT, XML, YAML, PCAP, PCAPNG and mixed trace files.
- `datenbasen/`
  DBC, ARXML, FIBEX and related network database files.
- `generation_manifest.json`
  Metadata for the generated package.
- `simulation_interface.json`
  Restbus participants, routing and simulation summary.

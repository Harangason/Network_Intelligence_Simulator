# traces

This directory is reserved for generated simulator output.

Trace packages can become large quickly, especially BLF, PCAP, PCAPNG, MDF,
MF4, CSV, and mixed JSON exports. Generated scenario folders under this
directory are intentionally ignored by Git. Keep reusable configuration,
profiles, and documentation in `physic_lib/` instead.

Typical generated packages use this shape:

- `Automotive/<timestamp>_<scenario>/traces/`
  BLF, ASC, TRC, CSV, JSON, LOG, TXT, XML, YAML, PCAP, PCAPNG, and mixed trace files.
- `Automotive/<timestamp>_<scenario>/datenbasen/`
  DBC, ARXML, FIBEX, and related network database files.
- `Automotive/<timestamp>_<scenario>/generation_manifest.json`
  Metadata for the generated package.
- `Automotive/<timestamp>_<scenario>/simulation_interface.json`
  Restbus participants, routing, warnings, artifact paths, and simulation summary.

# traces

Dieses Verzeichnis ist ausschließlich für lokale Laufzeitausgaben vorgesehen.
Generierte Unterordner und Trace-Dateien werden von Git ignoriert.

Ein typischer Lauf enthält:

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

Wiederverwendbare Hardware-, Netzwerk- und Technologieprofile gehören nicht in
diesen Ordner.

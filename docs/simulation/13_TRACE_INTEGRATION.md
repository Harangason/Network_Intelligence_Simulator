# Trace Integration

Der universelle Trace bleibt die zentrale Zeitbasis.

Signal-Samples enthalten zusaetzlich:

- `semantic_type`
- `quality`
- `actual_value`
- `golden_value`
- `state`
- `source_dependencies`
- `fault_state`

Diese Felder werden in `model_trace.json` bis in die Signalserien weitergegeben.

Bei grossen Laeufen wird die interaktive Model-Trace-Darstellung decimiert. Die Sampling-Punkte je Signal werden ueber die komplette konfigurierte Dauer verteilt; der letzte gespeicherte Punkt bleibt am Ende der Simulation statt bei einer fruehen Event-Grenze stehenzubleiben.

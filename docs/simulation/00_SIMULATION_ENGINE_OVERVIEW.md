# Simulation Engine Overview

Die zentrale Runtime bleibt die vorhandene Python-Kette:

`Frontend -> backend/engineering/simulation.py -> backend/simulator/communication_simulator.py -> backend/simulator/universal_trace.py -> backend/simulator/model_based_simulation.py -> Trace / Signals / Busload / Events`

Das Frontend konfiguriert Szenario, Dauer, Umfang und Ansicht. Die Emulation von Signalwerten, Golden Values, Faults, Encoding und Trace-Ausgabe liegt in Python.

## Aktueller Ausbau

- `ModelBasedSimulationEngine` bleibt der Einstieg fuer Signalwerte.
- `backend/simulator/signals/core` kapselt plausible Signal-Emulation.
- `SignalBehaviorRegistry` ersetzt neue monolithische Behavior-Erweiterungen durch registrierte Handler.
- `PlausibleSignalEmulationService` fuehrt Constraints, Rate-Limits, Noise, Quantisierung, Raw-Wert und Quality zusammen.


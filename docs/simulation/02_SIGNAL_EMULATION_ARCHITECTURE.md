# Signal Emulation Architecture

Die modulare Erweiterung liegt unter `backend/simulator/signals` und wird ausschliesslich aus der bestehenden `ModelBasedSimulationEngine` heraus genutzt.

| Modul | Aufgabe |
| --- | --- |
| `context.py` | `SimulationContext` mit Zeit, Seed, Signalwerten, Environment und Routing-Kontext. |
| `runtime_state.py` | Vorwerte, Historie und Delay-Zugriff fuer reproduzierbare Verlaeufe. |
| `registry.py` | `SignalBehaviorRegistry` mit registrierten Behavior-Handlern. |
| `random_service.py` | `SimulationRandomService` fuer zentrale, benannte Seed-Streams. |
| `emulator.py` | `PlausibleSignalEmulationService` als Pipeline-Orchestrierung. |
| `sample.py` | `SignalSample` als gemeinsamer Sample-Contract. |
| `constraints/engine.py` | `SignalConstraintEngine` fuer Grenzen und Rate-Limits. |
| `noise/engine.py` | `SignalNoiseEngine` fuer reproduzierbares, begrenztes Sensorrauschen. |
| `quality/engine.py` | `SignalQualityEngine` fuer `VALID`, `INVALID`, `STALE`, `NOT_AVAILABLE`, `ESTIMATED`. |
| `encoding/service.py` | `SignalEncodingService` fuer Quantisierung und Raw-Wert vor Message Packing. |
| `derived/engine.py` | `DerivedSignalEngine` fuer Dependency-Reihenfolge vor der Auswertung. |
| `discrete/state_machine.py` | `SignalStateMachineEngine` fuer Operating-State-Verlaeufe. |

`SignalBehaviorEngine` delegiert an diesen Layer und bleibt kompatibel fuer bestehende Aufrufer.

Pipeline: Behavior -> Constraints -> Noise -> Quantization -> Quality -> Fault Injection -> Message Encoding.

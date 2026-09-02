# Existing Engine Inventory

| Komponente | Bewertung | Entscheidung |
| --- | --- | --- |
| `communication_simulator.py` Runtime Entry | funktionierend | KEEP |
| `universal_trace.py` Zeitachse, Routen, Events | funktionierend | KEEP |
| `ModelBasedSimulationEngine` | zentrale Signal-/Payload-Engine | REUSE / ADAPT |
| `SignalBehaviorEngine` | kompatibler Adapter auf den modularen Signal-Emulator | SPLIT / ADAPT |
| `FunctionBehaviorEngine` | wertet abhaengige Signale aus | REUSE |
| `DerivedSignalEngine` | sortiert abhaengige Signale vor Formula/State-dependent Sampling | ADD |
| `SignalStateMachineEngine` | Operating-State-Verlauf fuer Status/Boolean/Physical Models | ADD |
| `SignalConstraintEngine` | physikalische Grenzen und Rate-Limits | ADD |
| `SignalNoiseEngine` | kontrolliertes Noise mit zentralem Seed | ADD |
| `SignalQualityEngine` | Quality-State pro Sample | ADD |
| `SignalEncodingService` | Quantisierung/Raw Value vor Message Packing | ADD |
| `FaultInjectionEngine` | Golden-zu-Actual-Faults | KEEP |
| `MessageCodec` | Encoding/Decoding | KEEP |
| `trace_realism.py` | plausible semantische Baselines fuer Generatoren | REUSE als Referenz |
| `nemotron.py` | KI-Assistent fuer Vorschlaege | KEEP als Proposal-/Recovery-Hilfe |

Keine zweite Runtime wurde gebaut. Die neue Signalstruktur haengt intern unter der bestehenden Model-Based Engine und der Universal Trace bleibt die einzige Zeitbasis.

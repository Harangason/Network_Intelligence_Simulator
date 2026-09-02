# Simulation Engine Summary

## Zweck

Die Simulationsfunktion bildet das freigegebene Engineering-Modell als ausführbare Kommunikations-Emulation ab. Sie erzeugt zeitbasierte Frames, Signalwerte, Fehlerereignisse, Buslasten und Trace-Artefakte aus Hardware, Interfaces, Routing und Simulationsparametern.

## Rollen der Module

| Modul | Aufgabe |
| --- | --- |
| `backend/engineering/simulation.py` | Engineering-Adapter: lädt Modell, Routing, Workflow-Topologie und Simulationsumfang. |
| `backend/simulator/communication_simulator.py` | Primärer Runtime-Einstieg: validiert Konfiguration, startet Event-Generierung und schreibt Artefakte. |
| `backend/simulator/universal_trace.py` | Erzeugt den universellen Ereignisstrom über Dauer, Zykluszeiten, Routen, Netze und Faults. |
| `backend/simulator/model_based_simulation.py` | Model-Based Engine: berechnet Signalwerte, Golden Values, Fault-Effekte, Payload-Encoding und Model Trace. |
| `backend/simulator/nemotron.py` | KI-gestützter CAN-Simulationsassistent für Profil-/Konfigurationsvorschläge, nicht die zentrale Laufzeit-Engine. |

## Eingaben

- Engineering-Modell mit Hardware, Funktionen, Interfaces, Messages und Signals.
- Freigegebene Routing-Pfade mit Sendern, Empfängern, Messages und Signalzuordnungen.
- Netzwerk- und Protokollparameter wie Bitrate, Payload-Größe, Zykluszeit, Gateway-Latenzen und Queues.
- Szenarioeinstellungen wie Dauer, Seed, Geschwindigkeit, Trace-Formate und Faults.
- Simulationsumfang: default `ALL`, optional gefiltert auf ausgewählte Messages oder Signals.

## Ablauf

1. Das Frontend sammelt Szenario, Dauer, Trace-Formate und Simulationsumfang.
2. `engineering/simulation.py` reichert die Konfiguration mit kanonischen Engineering-Daten an.
3. Der Simulationsumfang filtert bei Bedarf Messages, Signals und Communications.
4. `communication_simulator.py` startet die neutrale Simulation.
5. `universal_trace.py` erzeugt alle Ereignisse entlang der Kommunikationspfade.
6. `ModelBasedSimulationEngine` berechnet pro Ereignis die zugeordneten Signale und deren Werte.
7. Artefakte wie `universal_trace.jsonl`, `universal_trace.csv`, `model_trace.json` und native Formate werden geschrieben.
8. Das Frontend visualisiert Network/ECU, Signale, Buslast und Events synchron auf einer Zeitachse.

## Ergebnisdaten

- `frames`: zeitlich sortierte Kommunikationsereignisse.
- `signals`: Signalserien mit Golden Value, Istwert, Einheit, Grenzen und Fault-Markern.
- `bus_load`: berechnete Netzlast pro Zeitfenster.
- `events`: synchronisierte Warnungen und Fehlerereignisse.
- `signal_summary`: Anzahl der Signale, Samples und betroffenen Signale.
- `timing_summary`: Frame-Anzahl, gespeicherte Frames und Dauer.
- `network_load_summary`: Lastverteilung je Netzwerk.

## Grenzen und Zuständigkeiten

- Die Simulation ist Python-first; das Frontend soll nur konfigurieren und visualisieren.
- Nemotron ist ein optionaler KI-Assistent für Vorschläge und Recovery, nicht die deterministische Emulationsquelle.
- Die Laufzeit ist reproduzierbar über Seed, Szenario und Engineering-Snapshot.
- KI-generierte Faults oder Modelländerungen müssen vor Aktivierung geprüft und angenommen werden.

## Aktueller UI-Bezug

Im Schritt `Simulation` kann der Nutzer auswählen, ob alle Messages/Signals simuliert werden oder nur eine gezielte Teilmenge. Default ist `ALL`, damit ein normaler Lauf das komplette freigegebene Modell abdeckt.

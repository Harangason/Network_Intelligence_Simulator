# Arbeitsauftrag für Codex
## Random Forest & Gradient Boosting für den Network Intelligence Simulator

## 1. Ziel

Erweitere den **Network Intelligence Simulator** um eine modulare Machine-Learning-Schicht auf Basis von:

```text
Random Forest
Gradient Boosting
```

Ziel ist nicht, deterministische Engineering-Logik zu ersetzen, sondern strukturierte Klassifikations-, Ranking- und Anomalieaufgaben effizienter zu lösen.

Grundregel:

```text
Python Core
→ deterministic calculation

ML
→ classification / ranking / prediction

Qwen / LLM
→ interpretation / explanation / proposal
```

---

## 2. Kernanwendungen

Mindestens folgende Use Cases vorbereiten:

```text
1. Signal Semantic Classification
2. Status Model Classification
3. Physical Model Selection
4. Trace Fault Classification
5. Routing Candidate Ranking
6. Message Packing Quality
7. Architecture Gap / Quality Classification
```

Optional später:

```text
Hardware Mapping Recommendation
Network Technology Recommendation
Requirement Classification
Function Classification
Data Quality Classification
```

---

## 3. Random Forest als Baseline

Für jeden strukturierten ML-Use-Case zuerst:

```text
Random Forest
```

als Baseline trainieren.

Ziel:

```text
robust
leicht erklärbar
wenig Hyperparameter
schnell vergleichbar
```

---

## 4. Gradient Boosting als Candidate

Danach denselben Datensatz mit:

```text
Gradient Boosting
```

trainieren.

Bewertung gegen dieselben:

```text
Train
Validation
Test
Golden Evaluation
```

Splits.

---

## 5. Modellwahl

Keine subjektive Modellwahl.

Beispiel:

```text
Signal Semantic Classification

Random Forest:
F1 = 0.91

Gradient Boosting:
F1 = 0.95
```

Dann:

```text
Gradient Boosting
→ preferred candidate
```

---

## 6. Signal Semantic Classification

Input Features beispielsweise:

```text
name tokens
name embedding
description embedding
unit
datatype
minimum
maximum
resolution
bit_length
enum_count
producer_type
consumer_type
cycle_time
network_type
domain_tags
```

Output:

```text
TEMPERATURE
ROTATIONAL_SPEED
PRESSURE
CURRENT
VOLTAGE
POSITION
OPERATING_STATE
HEALTH_STATE
QUALITY_STATE
BOOLEAN
COUNTER
...
```

---

## 7. Status Model Classification

Beispiel:

```text
Signal:
GatewayStatus

Features:
unit = none
enum_values = true
producer = Gateway
name contains Status
```

ML Output:

```text
semantic_type = STATE

status_dimension = OPERATING_STATE
```

Danach:

```text
StatusModelRegistry
→ gateway.py
```

Die Zustände selbst kommen aus der freigegebenen Statusmodelllogik.

ML wählt:

```text
welches Modell passt
```

nicht:

```text
welche Wahrheit gilt
```

---

## 8. Physical Model Selection

Beispiel:

```text
MotorTemperature
→ TEMPERATURE
→ physical/temperature.py
```

```text
MotorRPM
→ ROTATIONAL_SPEED
→ physical/rotational_speed.py
```

ML kann hierfür:

```text
model_class
confidence
alternative_models
```

liefern.

---

## 9. Trace Fault Classification

Nutze Simulations- und Trace-Daten.

Mögliche Klassen:

```text
NORMAL
BLOCKED_MOTOR
OVERHEATING
SIGNAL_DRIFT
STUCK_SIGNAL
MESSAGE_LOSS
TIMING_FAULT
JITTER_FAULT
NETWORK_OVERLOAD
GATEWAY_DELAY
SENSOR_FAULT
```

---

## 10. Trace Feature Extraction

Features beispielsweise:

```text
mean
std
min
max
slope
variance
rate_of_change
zero_crossings
out_of_range_count
dropout_count
latency_mean
latency_p95
jitter_mean
jitter_max
message_loss_count
timeout_count
busload_mean
busload_peak
state_transition_count
```

---

## 11. Cross-Signal Features

Beispiel:

```text
RPM
Current
Torque
Temperature
```

kombiniert.

Beispiel Finding:

```text
RPM = 0
Current = high
TorqueCommand = high
Temperature rising
```

ML:

```text
BLOCKED_MOTOR
confidence = 0.94
```

---

## 12. Qwen-Anbindung

ML liefert strukturierte Findings.

Qwen bekommt:

```text
fault_class
confidence
important_features
affected_signals
trace_window
engineering_context
```

und erzeugt daraus:

```text
Root Cause Explanation
Recommendation
Repair Proposal
```

Qwen entscheidet nicht die ML-Klasse neu, außer als explizite Gegenhypothese.

---

## 13. Routing Candidate Ranking

Nur gültige Routen ranken.

Pipeline:

```text
Python Routing Validation
→ valid routes
→ ML Ranking
→ Qwen Explanation
→ User Review
```

Features:

```text
hop_count
gateway_count
network_load
latency
jitter
redundancy
priority
criticality
receiver_count
```

Output:

```text
route_score
ranking
confidence
```

---

## 14. Message Packing Quality

Deterministischer Core berechnet:

```text
payload_used
payload_capacity
cycle_time
receiver_set
busload
```

ML bewertet:

```text
PACKING_GOOD
REPACK_RECOMMENDED
SPLIT_RECOMMENDED
MERGE_RECOMMENDED
```

oder Score:

```text
packing_quality = 0.91
```

---

## 15. Keine ML-Packing-Wahrheit

ML darf nicht direkt Bits verschieben.

Nicht:

```text
ML
→ new message payload
```

sondern:

```text
ML
→ optimization proposal

Python MessagePackingService
→ deterministic repacking
```

---

## 16. Interface-/Bus-Ranking

ML kann gültige Kandidaten ranken:

```text
CAN_FD_A
CAN_FD_B
Ethernet_A
```

Aber Python prüft zuerst:

```text
technology compatibility
capacity
routing
hardware capability
```

---

## 17. Architecture Quality Classification

Features:

```text
orphan_signals
unmapped_functions
missing_receivers
missing_status_models
routing_gaps
timing_violations
busload_margin
unknown_semantics
SPOF_count
traceability_gaps
```

Output eher:

```text
LOW_RISK
MEDIUM_RISK
HIGH_RISK
```

oder mehrere Einzelklassifikationen.

Keinen undurchsichtigen „AI Quality Score“ als Wahrheit darstellen.

---

## 18. Trainingsdatenquelle Simulation

Simulation ist zentrale Quelle für gelabelte ML-Daten.

Szenarien:

```text
GOLDEN
OVERHEATING
BLOCKED_MOTOR
SIGNAL_DRIFT
STUCK_SIGNAL
MESSAGE_LOSS
JITTER
NETWORK_OVERLOAD
GATEWAY_DELAY
```

---

## 19. Synthetic Training Example

Mindestens:

```text
scenario_id
signal_features
network_features
fault_type
fault_target
root_cause
label
quality
seed
```

---

## 20. Nur kontrollierte Labels

Simulation kann automatisch gelabelte Beispiele erzeugen, wenn:

```text
fault scenario known
fault target known
expected effect known
```

Unklare reale Trace-Findings erst nach Review als Trainingsdaten verwenden.

---

## 21. Training Dataset Builder

Implementiere:

```text
MLDatasetBuilder
```

mit:

```text
collect()
sanitize()
deduplicate()
feature_extract()
balance()
split()
version()
export()
```

---

## 22. Dataset Versioning

Mindestens:

```text
dataset_id
version
created_at
source_snapshot
train_count
validation_count
test_count
class_distribution
feature_schema_version
```

---

## 23. Feature Schema Versioning

Sehr wichtig:

```text
feature_schema_version
```

speichern.

Modell darf nicht mit inkompatibler Feature-Struktur geladen werden.

---

## 24. Model Registry

Implementiere / erweitere:

```text
ModelRegistry
```

Eintrag:

```text
model_id
model_type
task
version
dataset_version
feature_schema_version
metrics
status
artifact_location
created_at
```

Model Types:

```text
RANDOM_FOREST
GRADIENT_BOOSTING
```

---

## 25. Status

```text
TRAINING
EVALUATION
CANDIDATE
APPROVED
PRODUCTION
DEPRECATED
REJECTED
```

---

## 26. Model Router

Erweitere:

```text
AIModelRouter
```

Beispiel:

```text
simple rule
→ heuristic

semantic similarity
→ embedding

structured classification
→ Random Forest / Gradient Boosting

time-series anomaly
→ ML / DL

complex engineering request
→ Qwen

exact calculation
→ Python Service
```

---

## 27. ML Inference API

Fachlich beispielsweise:

```text
POST /ml/classify/signal
POST /ml/classify/status
POST /ml/classify/fault
POST /ml/rank/routes
POST /ml/score/packing
POST /ml/score/architecture
```

An bestehende API-Struktur anpassen.

---

## 28. Model Explainability

Für Random Forest / Gradient Boosting mindestens:

```text
feature importance
top contributing features
confidence
alternative class
```

speichern bzw. anzeigen.

Optional später:

```text
SHAP
```

---

## 29. Confidence Policy

Beispiel:

```text
>= 0.90
HIGH_CONFIDENCE

0.70–0.89
MEDIUM_CONFIDENCE

< 0.70
REVIEW_REQUIRED
```

Konfigurierbar.

---

## 30. Active Learning

Besonders wertvolle Review-Fälle:

```text
low confidence
model disagreement
rare class
unknown semantic type
high impact finding
failed validation
```

---

## 31. Random Forest vs Gradient Boosting Vergleich

Für jede Aufgabe automatische Evaluation:

```text
accuracy
precision
recall
F1
confusion matrix
inference latency
model size
```

---

## 32. Deployment Gate

Kein Modell automatisch produktiv setzen.

```text
Train
→ Evaluate
→ Compare
→ Review
→ Approve
→ Production
```

---

## 33. Python-Struktur

Empfohlen:

```text
backend/intelligence/ml/
├── core/
│   ├── model.py
│   ├── prediction.py
│   ├── feature_schema.py
│   └── registry.py
├── features/
│   ├── signal_features.py
│   ├── trace_features.py
│   ├── routing_features.py
│   ├── packing_features.py
│   └── architecture_features.py
├── random_forest/
│   ├── trainer.py
│   ├── classifier.py
│   └── config.py
├── gradient_boosting/
│   ├── trainer.py
│   ├── classifier.py
│   └── config.py
├── training/
├── evaluation/
├── inference/
└── api/
```

---

## 34. Keine monolithische ML-Datei

Nicht:

```text
ml_models.py
```

mit allen Tasks.

Nach:

```text
task
model type
feature extraction
training
inference
```

trennen.

---

## 35. Tests

Mindestens:

```text
signal classification
status classification
physical model selection
fault classification
route ranking
packing scoring
architecture classification
model loading
feature schema mismatch
low-confidence handling
```

---

## 36. Golden Evaluation

Erzeuge festes:

```text
SimulatorMLGoldenSet
```

Nicht im Training verwenden.

---

## 37. Simulation-to-ML E2E

Test:

```text
Simulation Scenario
→ Trace
→ Feature Extraction
→ ML Classification
→ Finding
→ Qwen Explanation
```

---

## 38. Definition of Done

Die ML-Erweiterung gilt erst als abgeschlossen, wenn:

1. Random Forest als Baseline verfügbar ist.
2. Gradient Boosting als Candidate verfügbar ist.
3. beide mit identischen Datensplits verglichen werden.
4. Signal Semantic Classification funktioniert.
5. Status Model Classification funktioniert.
6. Physical Model Selection funktioniert.
7. Trace Fault Classification funktioniert.
8. Routing Ranking nur validierte Routen bewertet.
9. Message Packing Quality nur Proposal liefert.
10. Architecture Classification keine deterministische Wahrheit ersetzt.
11. Simulation gelabelte Trainingsdaten liefern kann.
12. Dataset Versioning vorhanden ist.
13. Feature Schema versioniert ist.
14. Model Registry vorhanden ist.
15. Model Router ML korrekt einbindet.
16. Confidence und Explainability vorhanden sind.
17. Qwen ML-Findings erklären kann.
18. keine deterministische Engineering-Logik ins ML verlagert wurde.
19. Unit-, Integration- und E2E-Tests erfolgreich sind.
20. Dokumentation dem As-Built-Stand entspricht.

---

# Leitregel

```text
Simulation creates labeled evidence.

ML learns structured patterns.

Python validates engineering facts.

Qwen explains and proposes.

Humans approve engineering truth.
```

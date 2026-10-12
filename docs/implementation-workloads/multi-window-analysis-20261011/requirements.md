# Arbeitsauftrag für Codex: NIS Multi-Window- und Multi-Monitor-Workspace für Simulation und Trace-Analyse

## 1. Ziel

Erweitere den **NIS** um eine gezielte Multi-Window- und Multi-Monitor-Fähigkeit für die Bereiche:

```text
Simulation
Trace Analyse
Signalanalyse
Sequenzanalyse
Bus Load
Events
Findings / Gaps
Root Cause
Diagramme
```

Der Schwerpunkt liegt ausdrücklich auf der **parallelen Analyse**.

Der Nutzer soll nicht ständig zwischen Tabs hin- und herspringen müssen, sondern mehrere fachlich gekoppelte Sichten gleichzeitig verwenden können.

Beispiele:

```text
Monitor 1
→ Simulation Run / Scenario

Monitor 2
→ Trace Analyse
```

```text
Monitor 1
→ Sequence

Monitor 2
→ Signals
```

```text
Monitor 1
→ Bus Load

Monitor 2
→ Events / Findings / Root Cause
```

```text
Monitor 1
→ Golden Trace

Monitor 2
→ Fault Trace / Compare
```

Zusätzlich gilt:

> **Mehrere Fenster bedeuten mehrere Sichten – nicht mehrere Wahrheiten.**

> **Simulation, Trace und Analyse müssen denselben technischen Kernkontext teilen.**

---

## 2. Aktuelle NIS-Idee als Ausgangspunkt

Die aktuelle NIS-Trace-Ansicht zeigt bereits eine gute fachliche Richtung, zum Beispiel mit:

```text
NETWORK / ECU
SEQUENCE
SIGNALS
BUS LOAD
EVENTS
```

sowie einem schrittweisen Workflow wie:

```text
LOAD
→ FILTER
→ INSPECT MESSAGES
→ FOLLOW SEQUENCE
→ INSPECT SIGNALS
→ SYNCHRONIZE TRACE
→ DETECT FINDINGS
→ EXPLORE CHARTS
```

und Analyseblöcken wie:

```text
1 Session / Daten laden
2 Botschaften
3 Sequenz
4 Signale
5 Trace
6 Findings / Gaps
7 Root Cause
8 Diagramme
```

Genau diese Logik soll für Multi-Window weiterentwickelt werden.

---

## 3. Grundbegriffe

Der NIS muss künftig zwischen folgenden Ebenen unterscheiden:

```text
Board
= fachlicher Hauptbereich

View
= konkrete Darstellung innerhalb eines Boards

Window
= Darstellungscontainer

Monitor
= physische Anzeige
```

Zusätzlich für NIS:

```text
Analysis Context
= Session, Run, Trace, Zeitbereich, Auswahl, Filter
```

Also:

```text
Board != View != Window != Monitor
```

---

## 4. Keine zweite technische Wahrheit

Mehrere Fenster dürfen keine voneinander getrennten Trace- oder Simulationswahrheiten erzeugen.

Nicht:

```text
Window A
→ eigene Trace-Kopie

Window B
→ eigene Simulation-Kopie
```

Sondern:

```text
               NIS Core / Simulation Core / Trace Store
                                 │
                           NIS Services
                                 │
                 ┌───────────────┴───────────────┐
                 │                               │
             Window A                        Window B
```

Fenster halten nur:

```text
active_tab
selected_message
selected_signal
selected_ecu
selected_time_range
selected_cursor
filter
compare_mode
zoom
chart_state
layout
```

Nicht:

```text
eigene technische Schattenmodelle
unabhängige Simulationsresultate
abweichende Trace-Interpretationen ohne Kennzeichnung
```

---

## 5. Hauptziel für NIS

Multi-Window ist im NIS nicht nur Komfortfunktion, sondern ein Analysewerkzeug.

Zielbilder:

### 5.1 Simulation + Trace

```text
Monitor 1
Simulation Run

Monitor 2
Trace Analyse
```

### 5.2 Sequence + Signals

```text
Monitor 1
Message Sequence

Monitor 2
Signal Values / Charts
```

### 5.3 Bus Load + Events

```text
Monitor 1
Bus Load / Performance

Monitor 2
Events / Findings / Gaps
```

### 5.4 Root Cause + Diagram

```text
Monitor 1
Root Cause

Monitor 2
Sequence / Diagram / Timeline
```

### 5.5 Golden Run + Fault Run

```text
Monitor 1
Golden Trace

Monitor 2
Fault Trace
```

---

## 6. Multi-Window-Aktionen

Jede geeignete View erhält eine oder mehrere Aktionen:

```text
↗ In neuem Fenster öffnen
🔗 Mit Primäransicht koppeln
⇄ Vergleich öffnen
🧭 Analysefenster öffnen
```

Optional in einem Menü:

```text
Ansicht öffnen

○ Im aktuellen Bereich
○ Neues Fenster
○ Analysefenster
○ Sekundäransicht
○ Vergleichsansicht
```

---

## 7. NIS Analysis Context

Für Simulation und Trace ist ein gemeinsamer Analysekontext erforderlich.

Mindestens:

```text
project_id
session_id
simulation_run_id
trace_id
trace_segment_id
network_id
ecu_id
message_id
signal_id
time_cursor
time_range
filter_set
compare_left
compare_right
view_mode
analysis_stage
selected_finding_id
selected_root_cause_id
```

Dieser Kontext muss fensterübergreifend teilbar sein.

---

## 8. Analysis Stages

Die in der UI sichtbare Workflow-Idee soll formalisiert werden.

Beispiel:

```text
LOAD
FILTER
INSPECT_MESSAGES
FOLLOW_SEQUENCE
INSPECT_SIGNALS
SYNCHRONIZE_TRACE
DETECT_FINDINGS
EXPLORE_CHARTS
EXPLAIN_ROOT_CAUSE
```

Dieser Stage-Kontext darf zwischen Fenstern transportiert werden.

Beispiel:

```text
Window 1
→ Stage: FOLLOW_SEQUENCE

Window 2
→ Stage: INSPECT_SIGNALS
```

oder gekoppelt:

```text
Window 1
→ Stage-Wechsel auf DETECT_FINDINGS

Window 2
→ reagiert mit passenden Analysis Views
```

---

## 9. Link Modes

Mindestens drei Modi unterstützen:

```text
FOLLOW_PRIMARY
INDEPENDENT
COMPARE
```

### FOLLOW_PRIMARY

Sekundärfenster folgt Auswahl und Analysekontext des Primärfensters.

Beispiel:

```text
Window 1
Message ausgewählt

Window 2
zeigt automatisch zugehörige Signals / Events / Charts
```

### INDEPENDENT

Sekundärfenster bleibt stabil und analysiert einen anderen Kontext.

### COMPARE

Zwei gezielt verschiedene Kontexte werden parallel gehalten:

```text
Golden vs Fault
Run A vs Run B
ECU A vs ECU B
Signal A vs Signal B
Baseline vs Current
```

---

## 10. Synchronisierter Zeitkontext

Gerade für NIS ist Zeitkopplung zentral.

Shared Time Context:

```text
time_cursor
time_range
sample_index
frame_index
message_index
sequence_step
```

Dieser Zeitkontext muss nutzbar sein für:

```text
Simulation Results
Trace
Sequence
Signals
Bus Load
Events
Charts
```

Beispiel:

```text
Cursor = 12.520 s
```

Dann sollen relevante Fenster denselben Zeitpunkt fokussieren.

---

## 11. Beispiel – Sequence + Signals

### Monitor 1

```text
SEQUENCE
```

Nutzer markiert:

```text
Nachricht MSG_EngineStatus
bei t = 12.520 s
```

### Monitor 2

```text
SIGNALS
```

zeigt automatisch:

```text
relevante Signalwerte
Trend
letzte Änderung
qualifizierte Plausibilität
```

Optional zusätzlich:

```text
Chart
Bit-/Byte-Darstellung
physikalischer Wert
Rohwert
Einheit
```

---

## 12. Beispiel – Bus Load + Events

### Monitor 1

```text
BUS LOAD
```

zeigt:

```text
Spitzenlast
Durchschnittslast
Zeitfenster
betroffene ECU / Bussegmente
```

### Monitor 2

```text
EVENTS
```

zeigt:

```text
Korrelation zwischen Lastspitze und Event
```

Zum Beispiel:

```text
Buslast steigt
→ Timeout Event
→ Retransmission
→ Finding
```

---

## 13. Beispiel – Findings / Gaps + Root Cause

### Monitor 1

```text
Findings / Gaps
```

### Monitor 2

```text
Root Cause
```

Wenn ein Finding gewählt wird, soll Fenster 2 automatisch den relevanten Kontext aufbauen:

```text
Traceausschnitt
betroffene Botschaften
betroffene Signale
betroffene ECU
wahrscheinliche Ursache
```

---

## 14. Beispiel – Diagramme

Diagramme sollen als sekundäre Analysefenster besonders gut nutzbar sein.

Beispiele:

```text
Sequence Diagram
Signal Chart
Timing Chart
Network Load Chart
State Progression
Fault Propagation
ECU Interaction
```

Ein Diagramm ist eine View auf denselben Analysekontext.

Kein eigener Fachzustand.

---

## 15. Compare Mode – NIS-spezifisch

Compare Mode ist für NIS besonders wertvoll.

Pflichtfälle:

```text
Golden Trace vs Fault Trace
Golden Simulation vs Current Simulation
ECU A vs ECU B
Signal Before vs After Event
Expected Sequence vs Observed Sequence
```

### Compare Context

```text
CompareContext
├── left
│   ├── trace_id
│   ├── run_id
│   ├── object_id
│   ├── time_range
│   └── view
│
└── right
    ├── trace_id
    ├── run_id
    ├── object_id
    ├── time_range
    └── view
```

Keine automatische Überschreibung beider Seiten.

---

## 16. Window Descriptor

Beispiel:

```text
NisWindowDescriptor
├── window_id
├── project_id
├── board_id
├── view_id
├── session_id
├── simulation_run_id
├── trace_id
├── selected_object_id
├── selected_object_type
├── time_context
├── link_mode
├── compare_context
├── width
├── height
├── last_position
├── created_at
└── last_active_at
```

---

## 17. Broadcast / Synchronisation

Für die Browser-Version bevorzugt:

```text
BroadcastChannel
```

ergänzend:

```text
WebSocket
SharedWorker
serverseitiger session context
```

Mindestens Events:

```text
NIS_CONTEXT_SESSION_SELECTED
NIS_CONTEXT_RUN_SELECTED
NIS_CONTEXT_TRACE_SELECTED
NIS_CONTEXT_MESSAGE_SELECTED
NIS_CONTEXT_SIGNAL_SELECTED
NIS_CONTEXT_ECU_SELECTED
NIS_CONTEXT_TIME_CHANGED
NIS_CONTEXT_FILTER_CHANGED
NIS_CONTEXT_STAGE_CHANGED
NIS_CONTEXT_FINDING_SELECTED
NIS_CONTEXT_ROOT_CAUSE_SELECTED
NIS_WINDOW_REGISTERED
NIS_WINDOW_CLOSED
NIS_SESSION_LOGOUT
```

---

## 18. Trace Workflow Pane und Windowing

Die aktuelle Workflow-Darstellung darf in Multi-Window integriert werden.

Beispiel:

### Primärfenster

```text
TRACE WORKFLOW
```

### Sekundärfenster

fachlich fokussiert auf den aktuell gewählten Schritt:

```text
Schritt 3 Sequenz
→ Sequence View

Schritt 4 Signale
→ Signal View

Schritt 6 Findings / Gaps
→ Findings View

Schritt 7 Root Cause
→ Root Cause View
```

So kann der Nutzer den Workflow oben sehen und darunter bzw. auf Monitor 2 tief arbeiten.

---

## 19. Analysis Projection Only

Wenn eine View ausdrücklich nur Analyseprojektion ist, muss das klar bleiben.

Beispielhinweis:

```text
Analysis projection only
```

Bedeutung:

```text
View zeigt abgeleitete Analyse
aber ist nicht selbst der persistente technische Primärdatensatz.
```

Dieser Unterschied muss auch in Multi-Window sichtbar bleiben.

---

## 20. NIS-spezifische Workspace-Profile

### Trace Investigation

```text
Primary:
Sequence

Secondary:
Signals

Context:
Events
```

### Bus Diagnosis

```text
Primary:
Bus Load

Secondary:
Events

Context:
Root Cause
```

### Golden Comparison

```text
Primary:
Golden Trace

Secondary:
Fault Trace

Context:
Compare
```

### Simulation Evaluation

```text
Primary:
Simulation Run

Secondary:
Trace Analyse

Context:
Charts / Findings
```

### ECU Deep Analysis

```text
Primary:
Network / ECU

Secondary:
Messages / Signals

Context:
Root Cause
```

---

## 21. WorkspaceProfile-Modell

```text
WorkspaceProfile
├── profile_id
├── name
├── user_id
├── project_scope
├── primary_view
├── secondary_views[]
├── link_modes[]
├── preferred_window_sizes
├── preferred_monitor_roles
├── restore_on_start
└── version
```

---

## 22. Rechte und Session

Mehrere Fenster teilen dieselbe authentifizierte Session.

Ein sekundäres Fenster darf keine Rechte umgehen.

Serverseitig prüfen:

```text
user
role
scope
project access
trace access
simulation access
analysis access
```

Logout in einem Fenster:

```text
NIS_SESSION_LOGOUT
```

→ alle Fenster reagieren.

---

## 23. Editierbarkeit

Die meisten Trace-/Analyseviews sind lesend.

Falls es editierbare Simulationsparameter oder Annotationen gibt, dann gelten:

```text
edit lock
oder
optimistic revision check
```

Bei Konflikt:

```text
REVISION_CONFLICT
```

Nicht still überschreiben.

---

## 24. Cross-Window Invalidierung

Wenn Fenster A den Simulationskontext ändert:

```text
neuer Run
neuer Trace
neuer Filter
```

müssen andere Fenster reagieren:

```text
STALE
→ refresh
```

Wenn Derived Views betroffen sind:

```text
recompute
```

Das passt zum NIS-Ziel:

```text
SYNCHRONIZE TRACE
DETECT FINDINGS
EXPLORE CHARTS
```

---

## 25. Deep Links

Separat geöffnete Analyseviews benötigen stabile Deep Links.

Beispiel:

```text
/nis/projects/<project>/simulation?run=<run_id>&window=primary
/nis/projects/<project>/trace?trace=<trace_id>&view=signals&window=secondary
/nis/projects/<project>/analysis?finding=<finding_id>&window=context
```

Bestehendes Routing wiederverwenden.

---

## 26. Keine Tab-Duplikationslogik als Ersatz

Es reicht nicht, einfach denselben Tab zweimal zu rendern.

Gefordert ist:

```text
geteilte Kontexte
Synchronisation
Compare Mode
Workspace Profiles
Zeitkopplung
Analyseworkflow
```

---

## 27. Browser-Limitierungen

In einer normalen Web-App:

```text
window.open(...)
```

ist erlaubt.

Aber exakte Platzierung auf Monitor 2 ist nicht immer zuverlässig steuerbar.

Phase 1:

```text
Fenster öffnen
→ Nutzer zieht auf Monitor 2
→ Zustand speichern
```

Optionale spätere Erweiterung:

```text
Window Placement API
```

Nur als Zusatz, nicht als Voraussetzung.

---

## 28. Desktop Runtime – spätere Erweiterung

Falls NIS später als:

```text
Electron
Tauri
Desktop App
```

läuft, soll dieselbe Architektur erweitert werden um:

```text
Monitor Enumeration
Auto Placement
Auto Restore
Fullscreen Compare
```

Wichtig:

kein zweites Fachmodell für Desktop bauen.

---

## 29. Performance

Multi-Window darf nicht dazu führen, dass jedes Fenster den kompletten Trace vollständig neu lädt.

Stattdessen:

```text
Shared Context
Selective Query
Range Loading
Shared Cache
Event-driven Refresh
```

Für große Traces besonders beachten:

```text
virtuelle Listen
segmentierte Zeitfenster
lazy loading
chart decimation
```

---

## 30. Engineering-Logik für NIS

Die Multi-Window-Funktion ist nicht nur UI, sondern unterstützt Engineering-Fragen wie:

```text
Warum trat ein Timeout auf?
Welche Signaländerung ging dem Fehler voraus?
Welche Buslastspitze fällt mit dem Event zusammen?
Welche ECU war zuerst betroffen?
Wie unterscheidet sich Fault Run von Golden Trace?
```

Der Nutzer soll solche Fragen mit zwei Monitoren deutlich effizienter bearbeiten können.

---

## 31. Analyse-Assistant als Sekundärfenster

Für NIS wäre ein Analyse-Assistent auf Monitor 2 sehr hilfreich.

### Monitor 1

```text
aktive Simulation / Trace View
```

### Monitor 2

```text
NIS Analyse-Assistent
```

Der Assistant erhält automatisch:

```text
current project
current run
current trace
selected ECU
selected message
selected signal
selected finding
current time cursor
current workflow stage
```

Beispielantwort:

```text
Die Buslastspitze bei 12.520 s korreliert mit drei Retransmissions
auf ECU_GW_01 und einem Timeout im Folgepfad.
```

---

## 32. Pflicht-E2E-Szenarien

### E2E-01 – Sequence + Signals

```text
Window 1:
Sequence

Window 2:
Signals

Nachricht auswählen
→ Signale aktualisieren sich passend
```

### E2E-02 – Bus Load + Events

```text
Window 1:
Bus Load

Window 2:
Events

Zeitbereich auswählen
→ Events im gleichen Zeitfenster
```

### E2E-03 – Findings + Root Cause

```text
Window 1:
Findings

Window 2:
Root Cause

Finding auswählen
→ Root Cause Kontext aktualisiert
```

### E2E-04 – Golden Compare

```text
Window 1:
Golden Trace

Window 2:
Fault Trace

Compare aktiv
→ Unterschiede sichtbar
```

### E2E-05 – Simulation + Trace

```text
Window 1:
Simulation Result

Window 2:
Trace Analyse

Zeitcursor koppeln
→ beide Views synchron
```

### E2E-06 – Assistant

```text
Window 1:
Trace Analyse

Window 2:
Analyse-Assistent

Signal auswählen
→ Assistant kennt Kontext
```

---

## 33. Mandatory Assertions

```text
core_truth_shared = true
window_has_no_shadow_model = true
trace_context_shared = true
simulation_context_shared = true

follow_primary_sync_works = true
independent_mode_works = true
compare_mode_works = true

time_sync_works = true
finding_to_root_cause_sync_works = true
busload_to_event_sync_works = true
sequence_to_signal_sync_works = true

secondary_window_permissions_validated = true
session_sync_works = true
logout_sync_works = true

workspace_profiles_work = true
cross_window_refresh_works = true
analysis_projection_flag_preserved = true

assistant_receives_trace_context = true
assistant_receives_simulation_context = true
```

---

## 34. Nicht erlaubt

Nicht erlaubt:

- eigene technische Wahrheit pro Fenster
- vollständige Trace-Kopie pro Monitor ohne Not
- Rechteprüfung nur im Frontend
- Compare Mode mit stiller gegenseitiger Überschreibung
- unsichtbare Kontextabweichung
- Root-Cause-View ohne nachvollziehbaren Bezug zum Finding
- Bus-Load-View ohne synchronisierbaren Zeitbezug
- Signalview ohne Bezug zur ausgewählten Nachricht / ECU / Zeit
- Workspace-Restore mit offenen unsicheren Edit-Operationen

---

## 35. Entwicklungsphasen

### Phase 0 – Bestandsaufnahme

Prüfe:

```text
aktuelles Routing
Simulation Views
Trace Views
Tabs / mode Parameter
Analysis Workflow
Session Provider
State Provider
Chart/Trace Components
```

### Phase 1 – Detach View

```text
In neuem Fenster öffnen
WindowDescriptor
Window Registry
```

### Phase 2 – Shared Analysis Context

```text
BroadcastChannel
session/run/trace/message/signal/time sync
```

### Phase 3 – Link Modes

```text
FOLLOW_PRIMARY
INDEPENDENT
COMPARE
```

### Phase 4 – Time Sync

```text
Simulation
Trace
Sequence
Signals
Bus Load
Events
```

### Phase 5 – Workspace Profiles

```text
save
load
restore
```

### Phase 6 – Analyse-Assistent

```text
active trace context
active simulation context
selected findings/root cause
```

### Phase 7 – Desktop Adapter

Nur falls Desktop Runtime vorhanden ist:

```text
monitor enumeration
auto placement
compare restore
```

---

## 36. Definition of Done

Die NIS Multi-Window-Funktion gilt als umgesetzt, wenn:

1. Simulation- und Trace-Views in separaten Fenstern geöffnet werden können.
2. mehrere Fenster denselben NIS-Core-Kontext teilen.
3. Fenster nur View-State separat halten.
4. `FOLLOW_PRIMARY` funktioniert.
5. `INDEPENDENT` funktioniert.
6. `COMPARE` funktioniert.
7. Zeitkontext fensterübergreifend synchronisiert werden kann.
8. Sequence-, Signal-, Event-, Finding- und Root-Cause-Kontext verknüpft werden können.
9. Workspace Profiles gespeichert und geladen werden können.
10. Rechte und Sessions fensterübergreifend konsistent sind.
11. Compare von Golden/Fault Runs möglich ist.
12. große Traces performant behandelbar bleiben.
13. ein Analyse-Assistent den aktiven Kontext erhalten kann.
14. die Funktion im Browser nutzbar ist, auch wenn die physische Monitorplatzierung manuell bleibt.
15. spätere Desktop-Monitorplatzierung ohne neue Facharchitektur möglich bleibt.

---

## 37. Zielbild

```text
                     NIS Core / Trace Store / Simulation Core
                                      │
                                 NIS Services
                                      │
                                Shared Context
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
          ▼                           ▼                           ▼
   Primary Window              Secondary Window             Compare Window
      Sequence                     Signals                    Fault Trace
          │                           │                           │
          └────────────── Shared Session / Time / Context ───────┘
```

Physisch zum Beispiel:

```text
Monitor 1
→ Simulation / Sequence / Network

Monitor 2
→ Signals / Bus Load / Events / Root Cause / Assistant
```

oder:

```text
Monitor 1
→ Golden Run

Monitor 2
→ Fault Run
```

---

## 38. Leitregel

> **NIS Multi-Window soll Analysegeschwindigkeit und Ursachenverständnis erhöhen.**

> **Der Nutzer soll Simulation, Sequenz, Signale, Events, Findings und Root Cause parallel sehen können.**

> **Tabs sollen zu fachlich gekoppelten Analysefenstern weiterentwickelt werden – nicht nur optisch, sondern mit gemeinsamem technischen Kontext.**

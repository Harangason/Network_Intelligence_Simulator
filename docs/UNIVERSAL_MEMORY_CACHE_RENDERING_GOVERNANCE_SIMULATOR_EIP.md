# Arbeitsauftrag für Codex
## Universelle Memory-, Cache- und Rendering-Governance für Network Intelligence Simulator und EIP

## 1. Ziel

Analysiere und verbessere die Speicher-, Cache- und Rendering-Architektur des **Network Intelligence Simulator** und der **Engineering Intelligence Platform (EIP)** nach einem gemeinsamen universellen Grundmodell.

Ziel ist:

```text
stabile Laufzeit
+
begrenzter Speicherverbrauch
+
schnelles Rendering
+
vorhersagbare Cache-Größen
+
keine unkontrolliert wachsenden Collections
+
keine Memory Leaks
+
keine Vollprojektdarstellung im Frontend
```

Die Architektur soll für beide Systeme verwendbar sein.

Projekt- oder modul-spezifische Unterschiede dürfen über Adapter / Konfigurationen umgesetzt werden.

---

# 2. Zentrale Architekturregel

Verbindlich:

```text
Large Data
→ Backend / Persistent Store

Visible Projection
→ Frontend

Hot Result
→ Bounded Cache

Historical Data
→ Persistent Store
```

Weitere Pflichtregeln:

```text
NO UNBOUNDED CACHE
NO UNBOUNDED FRONTEND COLLECTION
NO FULL PROJECT RENDERING
NO CACHE AS DATABASE
NO DUPLICATE LARGE STATE
```

---

# 3. Nicht einfach „mehr cachen“

Ziel ist ausdrücklich nicht:

```text
mehr RAM benutzen
→ dadurch schneller
```

sondern:

```text
richtig cachen
+
begrenzen
+
invalidieren
+
freigeben
+
persistieren
```

Ein Cache ohne Limits ist ein Speicherleck mit Absicht.

---

# 4. Pflichtanalyse vor Umbau

Codex muss zuerst untersuchen:

```text
Welche Daten liegen im Browser?
Welche Daten liegen in React State?
Welche Daten liegen in globalen Stores?
Welche Query-Caches existieren?
Welche Backend-Caches existieren?
Welche Python Dicts / Maps wachsen unbegrenzt?
Welche Redis-/Memory Stores existieren?
Welche Graphen werden vollständig geladen?
Welche Tabellen rendern alle Zeilen?
Welche Trace-/Simulation-Daten werden dauerhaft im Browser gehalten?
Welche WebSockets bleiben aktiv?
Welche Event Listener werden nicht entfernt?
Welche Timer laufen weiter?
Welche Canvas-/Graph-Instanzen werden nicht disposed?
Welche Worker werden nicht terminiert?
Welche Blobs / Object URLs bleiben bestehen?
Welche API Responses sind unnötig groß?
Welche Daten werden mehrfach gespiegelt?
```

---

# 5. Memory Inventory

Erzeuge eine Tabelle:

| Layer | Component | Data Type | Typical Size | Growth Behavior | Limit | Risk | Action |
|---|---|---|---|---|---|---|---|

Layer mindestens:

```text
Browser
React State
Frontend Query Cache
Global Frontend Store
WebSocket Buffer
Canvas / Graph Renderer
Backend Process RAM
Python Cache
Redis
Database
Artifact Store
```

---

# 6. Komponenten klassifizieren

Für jede relevante Speicher-/Cache-Komponente:

```text
KEEP
LIMIT
REFACTOR
MOVE_TO_REDIS
MOVE_TO_DB
MOVE_TO_ARTIFACT_STORE
VIRTUALIZE
STREAM
WINDOW
DISPOSE
REMOVE
REPLACE
```

---

# 7. Universelles Speicherstufenmodell

Verwende vier primäre Stufen.

## Tier 1 – UI Memory

Nur sichtbare / aktive Daten:

```text
selected object
current viewport
current page
active filters
visible rows
visible graph nodes
current playhead window
```

Lebensdauer:

```text
seconds / minutes
```

## Tier 2 – Frontend Query Cache

Nur zuletzt verwendete API-Daten.

Eigenschaften:

```text
bounded
TTL / GC
query-key based
invalidatable
not persistent truth
```

Lebensdauer:

```text
minutes
```

## Tier 3 – Backend Hot Cache

Für teure, wiederverwendbare Ergebnisse:

```text
analysis result
graph projection
capacity calculation
timing calculation
routing analysis
short-lived simulation summary
```

Bevorzugt:

```text
Redis
```

oder ein explizit begrenzter In-Process-LRU.

## Tier 4 – Persistent Store

Für vollständige / historische Daten:

```text
Engineering Objects
Relationships
Trace Data
Simulation Data
Audit
Large Reports
Artifacts
Historical Analysis
```

Ziel:

```text
PostgreSQL
+
Artifact Store
```

je nach Datentyp.

---

# 8. Frontend darf nicht zur Datenbank werden

Verboten:

```text
vollständiges Projekt
→ React State
```

Verboten:

```text
gesamter Trace
→ Browser Memory
```

Verboten:

```text
alle Simulation Samples
→ global frontend store
```

Frontend speichert nur:

```text
UI state
selection state
view state
filter state
viewport state
small working sets
```

---

# 9. Lazy Loading und Projection APIs

Daten nur laden, wenn benötigt.

Beispiel:

```text
Project
↓
Hardware Board opened
↓
load Hardware Projection
↓
Signal opened
↓
load Signal Details
```

Nicht:

```text
Project opened
→ load everything
```

Große Modelle über Projektionen bereitstellen:

```text
HardwareProjection
SignalProjection
RoutingProjection
TraceWindowProjection
GraphViewportProjection
SimulationWindowProjection
```

---

# 10. Tabellen virtualisieren

Für große Tabellen wie:

```text
Signals
Messages
Requirements
Trace Events
Findings
Audit Events
Simulation Samples
```

keine vollständige DOM-Erzeugung.

Verwende:

```text
virtualized rows
windowed rendering
overscan
```

Bei z. B. 20.000 Zeilen sollen nur sichtbare Zeilen plus kleiner Overscan tatsächlich gerendert werden.

---

# 11. Graph Rendering

Große Engineering-Graphen nicht vollständig rendern.

Nicht:

```text
5000 nodes
+
15000 edges
→ browser at once
```

sondern:

```text
Selected Object
+
N Hops
+
Filtered Relations
+
Viewport
```

Implementiere / konsolidiere backendseitig:

```text
GraphProjectionService
```

mit fachlich etwa:

```text
get_subgraph()
get_neighbors()
get_n_hop_projection()
get_viewport_projection()
get_filtered_projection()
get_summary()
```

Optional LOD:

```text
zoomed out → clusters
medium zoom → systems / groups
zoomed in → individual objects / signals
```

---

# 12. Trace- und Simulation-Windowing

Trace-Daten nur fensterweise laden.

Beispiel:

```text
playhead = 120 s
frontend window = 115 s ... 125 s
```

Backend besitzt vollständigen Trace.

Gleiches Prinzip für Simulation:

```text
full simulation
→ backend / artifact store

visible time range
→ frontend
```

---

# 13. Ring Buffer für Live-Daten

Für:

```text
Trace Events
Simulation Events
Bus Load Samples
Signal Samples
Logs
```

begrenzte Ring Buffer verwenden.

Verboten:

```text
array.push() forever
```

oder:

```text
setState([...old, ...new]) forever
```

Älteste Einträge müssen entfernt, persistiert oder aggregiert werden.

---

# 14. Backend Cache Policy

Jeder Backend Cache benötigt:

```text
max_entries
max_memory
ttl
eviction_policy
```

Mindestens ein hartes Größenlimit und eine Verdrängungsstrategie sind Pflicht.

Python-In-Process-Caches nur klein und explizit begrenzt halten.

Nicht:

```python
cache = {}
```

ohne Begrenzung.

Bevorzugt:

```text
LRU
TTL
max entries
```

---

# 15. Mehrere Worker berücksichtigen

Beachte:

```text
4 workers
×
500 MB local cache
=
2 GB RAM
```

Große Shared Caches daher nicht pro Prozess replizieren.

---

# 16. Redis für Shared Hot Data

Redis bevorzugt für:

```text
shared cache
short-lived analysis
runtime summaries
job state
small hot projections
```

Mit:

```text
TTL
maxmemory
LRU / LFU eviction
```

Redis ist kein Artifact Store.

Nicht dort ablegen:

```text
hundreds of MB traces
complete simulation history
large binary files
large model artifacts
```

Stattdessen persistenter Artifact Store.

Redis enthält nur:

```text
artifact reference
status
summary
current metrics
```

---

# 17. Cache-Key-Governance

Keine groben Keys wie:

```text
project
```

Besser:

```text
project:{id}:hardware:{revision}
project:{id}:signals:{revision}
project:{id}:routing:{revision}
project:{id}:analysis:capacity:{revision}
```

Revision / Version in Cache Keys integrieren.

---

# 18. Selektive Invalidierung

Nicht ständig:

```text
CLEAR ALL
```

sondern gezielt.

Beispiel:

```text
Routing changed
→ invalidate:
capacity
timing
simulation-preflight

Do not invalidate:
unrelated documentation
```

Wenn Digital Thread / Dependency Graph vorhanden:

```text
Changed Object
↓
Dependent Calculations
↓
OUTDATED
↓
Cache invalidated
```

Optional Status:

```text
VALID
STALE
OUTDATED
EXPIRED
INVALID
```

---

# 19. Frontend Query Cache

Frontend Query Cache bewusst konfigurieren.

Prinzip:

```text
staleTime
+
gcTime
```

Keine endlosen Query-Objekte in einer Session.

Query Keys mindestens nach:

```text
project
board
object
revision
filters
```

strukturieren.

---

# 20. Resource Lifecycle und Cleanup

Alle Frontend-Komponenten mit externen Ressourcen müssen Cleanup implementieren.

Mindestens prüfen:

```text
setInterval
setTimeout
requestAnimationFrame
WebSocket
EventSource
EventListener
Worker
Canvas Renderer
Graph Renderer
Chart Instance
Blob URL
```

Pflicht:

```text
setInterval → clearInterval
addEventListener → removeEventListener
requestAnimationFrame → cancelAnimationFrame
WebSocket → unsubscribe + close
Worker → terminate
createObjectURL → revokeObjectURL
Renderer → destroy / dispose
```

---

# 21. Sichtbarkeitssteuerung

Teure Visualisierungen bei Inaktivität stoppen.

Nutze wenn passend:

```text
IntersectionObserver
document.hidden
active tab
```

Nicht sichtbare Views sollen möglichst nicht weiter rendern.

---

# 22. Render-Frequenz von Daten-Frequenz trennen

Beispiel:

```text
Simulation:
1000 updates/s

UI:
10–30 updates/s
```

Frontend muss nicht jedes Backend-Event rendern.

Für hochfrequente Daten:

```text
raw samples
→ backend aggregation
→ frontend summary
```

Mögliche Werte:

```text
min
max
avg
p95
peak
latest
```

---

# 23. Downsampling

Große Zeitreihen:

```text
raw data
→ downsample
→ visible resolution
```

Die Anzahl gerenderter Punkte darf nicht proportional zur gesamten Trace-Länge wachsen.

---

# 24. API Payload Limits

APIs müssen bei großen Datenmengen unterstützen:

```text
pagination
cursor
limit
time window
field selection
filters
summary mode
```

Große Listen niemals vollständig übertragen.

Bei sehr großen Tabellen / Events möglichst cursor-based pagination verwenden.

---

# 25. Streaming und Backpressure

Für laufende Simulation / Trace optional:

```text
WebSocket
SSE
chunked stream
```

Streaming benötigt immer:

```text
buffer limit
backpressure
cleanup
```

Wenn Backend schneller liefert als Frontend verarbeitet:

```text
drop
aggregate
pause
sample
```

kontrolliert anwenden.

Nie unbegrenzt puffern.

---

# 26. Large Object Policy

Definiere eine messbare Schwelle für Large Objects.

Large Objects dürfen nicht:

```text
duplicated
deep copied repeatedly
stored in many frontend stores
```

werden.

Prüfe in React / TypeScript besonders:

```text
[...oldLargeArray]
{...hugeObject}
```

in Hot Paths.

---

# 27. Derived State begrenzen

Keine großen Daten mehrfach speichern.

Nicht:

```text
rawSignals
filteredSignals
sortedSignals
visibleSignals
```

alle vollständig als eigene States.

Besser:

```text
source query
+
small derived projection
```

---

# 28. Backend-Verarbeitung großer Daten

Python-seitig bei großen Datenmengen bevorzugen:

```text
iterators
generators
stream processing
batch processing
```

statt unnötig vollständige Listen im RAM aufzubauen.

Beispiel:

```text
1,000,000 trace events
→ batches
```

---

# 29. Artifact Store

Persistiere große Artefakte außerhalb des normalen RAM-/Redis-Caches:

```text
Trace files
Simulation files
Reports
Exports
ML datasets
Model artifacts
```

Verbindliche Unterscheidung:

```text
Cache = disposable
Database = persistent structured data
Artifact Store = persistent large objects
```

Jeder Cache muss rekonstruierbar sein.

Wenn nicht:

```text
it is not a cache
```

---

# 30. Memory-Leak-Analyse

Codex muss Memory Leaks aktiv untersuchen.

Frontend:

```text
Heap Snapshot
Allocation Timeline
Detached DOM Nodes
Event Listener Count
WebSocket Count
```

Backend:

```text
process RSS
Python tracemalloc
object growth
worker memory
```

---

# 31. Leak-Reproduction-Test

Mindestens:

```text
open board
close board
repeat 20 times
```

Prüfen:

```text
memory returns close to baseline
```

---

# 32. Long-Running-Test

Simulation / Trace als Langzeittest ausführen.

Beispiel:

```text
30–60 minutes
```

prüfen:

```text
RAM growth
CPU growth
render FPS
event buffer size
cache size
```

---

# 33. Cache- und Performance-Metriken

Cache:

```text
cache_hit_rate
cache_miss_rate
entries
memory_bytes
evictions
expired_entries
average_object_size
```

Frontend:

```text
JS heap
DOM node count
render duration
long tasks
FPS
active sockets
active timers
visible nodes
visible rows
```

Backend:

```text
RSS memory
worker memory
Redis memory
cache size
request latency
analysis latency
artifact writes
GC pressure
```

---

# 34. Memory Budgets

Für relevante Komponenten Budgets definieren.

Beispiel:

```text
Frontend working set
Query Cache
Redis maxmemory
Python Worker RSS target
Graph View max rendered nodes
Trace View max visible samples
```

Konkrete Werte aus Messungen ableiten.

---

# 35. Hard Limits und Soft Limits

Caches / Buffers benötigen Hard Limits.

Bei Erreichen:

```text
evict
drop oldest
persist
downsample
reject oversized request
```

Optional:

```text
80% → warning
100% → protection / eviction
```

---

# 36. Fail-Safe und Performance Mode

Bei Ressourcenproblemen graceful degradation:

```text
lower graph detail
reduce trace window
reduce live update rate
disable expensive overlays
```

Optional einen Performance Mode bereitstellen, der reduziert:

```text
animations
overscan
graph labels
update rate
history window
```

---

# 37. Simulator-spezifische Anwendung

Im Network Intelligence Simulator besonders prüfen:

```text
Network Graph
Bus Load View
Signals View
Live Simulation
Trace Analyse
Fault Injection
Time Series
Message Animation
```

---

# 38. EIP-spezifische Anwendung

Im EIP zusätzlich:

```text
Requirements Board
Structure Graph
Function Manager
Hardware Manager
Communication Manager
Digital Thread
Traceability
Safety
Security
Measurement
Test
Production
Knowledge Graph
```

---

# 39. Universal Core

Gemeinsame technische Komponenten nach Möglichkeit als Shared Core / Library entwickeln:

```text
CachePolicy
MemoryBudget
ProjectionService
Pagination
Windowing
RingBuffer
CacheKeyBuilder
InvalidationService
PerformanceMetrics
```

Simulator / EIP konfigurieren nur:

```text
limits
projection types
cache namespaces
module dependencies
view-specific policies
```

Nicht die gesamte Cache-Logik duplizieren.

---

# 40. Python-First-Prinzip

Backend-Analyse, Projektion, Downsampling, Aggregation und Cache-Policy möglichst in Python zentralisieren.

Frontend übernimmt:

```text
request
display
small local cache
virtualized rendering
```

Cache Layer darf keine Engineering-Wahrheit verändern.

Nur:

```text
store
retrieve
invalidate
evict
```

---

# 41. Teststruktur

Mindestens:

```text
tests/performance/
tests/cache/
tests/memory/
tests/projection/
tests/pagination/
tests/windowing/
tests/streaming/
```

Acceptance Tests mindestens:

```text
large signal list
large trace
long simulation
large graph
multiple board switches
multiple project switches
repeated open/close
multiple active users
```

---

# 42. Regression und Cache Correctness

Nach Umbau prüfen:

```text
correct data
correct visualization
correct filters
correct trace sync
correct graph relations
correct simulation results
no stale cache issues
```

Beispiel:

```text
change object
→ invalidate dependency
→ next read returns new version
```

Performance darf niemals zu falschen oder veralteten Engineering-Daten führen.

---

# 43. Dokumentation

Erzeuge gemeinsame Doku:

```text
docs/performance/

00_MEMORY_CACHE_RENDERING_OVERVIEW.md
01_CURRENT_STATE_INVENTORY.md
02_MEMORY_BUDGETS.md
03_FRONTEND_CACHE_POLICY.md
04_BACKEND_CACHE_POLICY.md
05_REDIS_POLICY.md
06_CACHE_KEYS_AND_INVALIDATION.md
07_GRAPH_PROJECTION.md
08_TRACE_AND_SIMULATION_WINDOWING.md
09_VIRTUALIZATION.md
10_STREAMING_AND_BACKPRESSURE.md
11_MEMORY_LEAK_PREVENTION.md
12_PERFORMANCE_METRICS.md
13_LOAD_AND_LONG_RUNNING_TESTS.md
14_SIMULATOR_ADAPTER.md
15_EIP_ADAPTER.md
16_ARCHITECTURE_COMPLIANCE.md
```

---

# 44. Current State Report

Vor Umbau dokumentieren:

```text
largest memory consumers
unbounded caches
large frontend states
large API responses
full graph renders
large trace buffers
known leaks
missing cleanup
missing limits
```

---

# 45. Umsetzungsschleife

Jeder Umbau in kleinen Schritten:

```text
ANALYZE
→ MEASURE BASELINE
→ DEFINE LIMIT
→ IMPLEMENT
→ TEST
→ LOAD TEST
→ MEMORY TEST
→ REGRESSION
→ FIX
→ RETEST
→ DOCUMENT
→ NEXT STEP
```

---

# 46. Kein Performance-Fix ohne Messung

Vorher:

```text
baseline
```

Nachher:

```text
comparison
```

mindestens:

```text
memory
latency
render time
FPS
cache hit rate
```

---

# 47. Keine vorzeitige Fertigmeldung

Nicht:

```text
cache added
→ complete
```

Nicht:

```text
render feels faster
→ complete
```

Nicht:

```text
one board fixed
→ complete
```

---

# 48. Definition of Done

Der Auftrag ist erst abgeschlossen, wenn:

1. alle relevanten Speicherpfade inventarisiert sind,
2. kein unbounded Cache mehr existiert,
3. kein unbounded Live-Array mehr existiert,
4. große Tabellen virtualisiert sind,
5. große Graphen nur als Projection gerendert werden,
6. Trace und Simulation windowed / streamed sind,
7. Ring Buffer für Live-Daten begrenzt sind,
8. Backend Caches TTL + Limit + Eviction besitzen,
9. Redis maxmemory / eviction konfiguriert ist,
10. große Artefakte nicht in Redis liegen,
11. Cache Keys versioniert sind,
12. selektive Invalidierung funktioniert,
13. Frontend Ressourcen beim Unmount sauber disposed werden,
14. WebSockets / Listener / Timer sauber geschlossen werden,
15. Render-Frequenz und Daten-Frequenz getrennt sind,
16. Downsampling / Aggregation bei großen Zeitreihen funktioniert,
17. API Pagination / Windowing vorhanden ist,
18. Memory Budgets definiert sind,
19. Long-Running Tests stabil sind,
20. wiederholtes Öffnen / Schließen keine kontinuierliche Memory-Zunahme erzeugt,
21. Regression fachlich erfolgreich ist,
22. Simulator und EIP dieselbe Core-Governance verwenden,
23. projektbezogene Unterschiede nur über Adapter / Konfigurationen gelöst werden,
24. Dokumentation vollständig aktualisiert ist.

---

# 49. Zentrale Leitregel

```text
RAM is a working area, not a database.

Cache is temporary, bounded and disposable.

Frontend renders projections, not complete systems.

Historical data belongs in persistent storage.

Large data is streamed, windowed or virtualized.

Every external resource must have a lifecycle.

Every cache must have a limit.

Every performance change must be measured.
```

Kurz:

```text
MEASURE
→ LIMIT
→ PROJECT
→ CACHE
→ INVALIDATE
→ EVICT
→ STREAM
→ VIRTUALIZE
→ DISPOSE
→ VERIFY
```

Diese Architektur soll universell für den Network Intelligence Simulator und das EIP verwendet werden.

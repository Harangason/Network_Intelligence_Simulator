# Wizard-Stillstand und CUDA

Projekt: network-project-20260909132301897-134da9ff. Fix-Build: a677ef03da23.

CUDA ist im laufenden Container verfügbar: CuPy erkennt die RTX 3070 Ti, NUMERIC_ACCELERATOR=cuda, kein Fallback. Ein ausgeführter Trace-Statistik-Test mit 600 Werten meldete cupy-cuda und accelerated=true. Die regelbasierte Engineering-/Routenerzeugung verwendet hingegen Python/CPU und Postgres. Zum Prüfzeitpunkt war in Ollama kein Modell geladen.

Der Agentenlauf war beim Routing BLOCKED: Die Heartbeat-Verlängerung nahm über execute dieselbe Projekt-Modellsperre wie die lange Routengenerierung. Das Backend protokollierte ConcurrentUpdateError und brach den Lauf nach gescheiterter Lease-Verlängerung ab. Gleichzeitig hielt eine rechenaktive Transaktion die Sperre minutenlang.

Die Pfadsuche zählte bis zu sieben Hops lange einfache Wege auf. In dichten Busgraphen mit unerreichbarem Ziel wächst dieser Suchraum kombinatorisch. Jetzt ist die Zahl eingereihter Ankünfte pro Knoten begrenzt; der Netzgraph wird innerhalb einer unveränderlichen Generierungstransaktion einmal aufgebaut. Heartbeats verlängern ausschließlich die projekt- und laufgebundene Gesprächslease ohne die Modellsperre.

Prüfung: 48 Routing-/Agent-Audit-Tests einschließlich dichter unerreichbarer Graphen und echter Lease-Verlängerung während gehaltener Modellsperre; drei gezielte Wizard-Tests; Produktionsbuild erfolgreich. Der bestätigte Projektauftrag wurde in einer zurückgerollten Transaktion nachgespielt: 317 Routenvorschläge in 6,573 Sekunden, inklusive Validierung 9,254 Sekunden. Nach dem ersten Suchlimit-Fix, noch ohne Graph-Wiederverwendung, dauerte die Generierung 105,228 Sekunden.

Die Wiedergabe hat keine Modelländerungen oder Vorschläge gespeichert. 309/317 Kandidaten validieren erfolgreich. Acht Kandidaten haben weiterhin UNMAPPED_ROUTE und DESTINATION_PHYSICAL_PORT_MISSING. Diese fachlichen Zuordnungsfehler sind kein CUDA- oder Laufzeitproblem und wurden nicht als valide freigegeben. Nachweise: verification/2026-09-09-wizard-routing-performance*.json.

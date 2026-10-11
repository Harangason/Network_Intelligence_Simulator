# Runtime-Ergebnisse: drei Browsermarkierungen
Projekt 20261009072206008-4bb505f1, /studio/results.
1. Sieben Runtime-Kennzahlen in festem Sechs-Spalten-Raster erzwingen eine zweite Reihe.
2. Latency & Jitter: sieben Spalten, bisher ohne Spaltenfilter.
3. Load & Queueing: sechs Spalten, bisher ohne Spaltenfilter.
Quelle der Beobachtung: vom Nutzer bereitgestellte Browserbilder; keine Laufzeitprüfung.
Datenfluss: getWorkflowSimulationSnapshot/getSimulation -> mergeSimulationResult -> runtime_metrics -> RuntimeAnalysis in results-workbench.tsx.
Soll: kompakte, nach Platz umbrechende Kennzahlen; kombinierbare unabhängige Filter je sichtbarer Tabellenspalte, zurücksetzbar, mit Trefferzahl und Leerzustand. Zahlenfilter unterstützen Komma und Punkt. Route umfasst auch die sichtbare ID; Violations umfasst Status, Anzahlen und Grenzwerte.
Wiederverwendung: bestehendes Filterzeilenmuster aus engineering-workbench.tsx und trace-analysis-workbench.tsx; lokale React-Zustände, keine zweite Datenquelle oder Registry.
Abdeckung: vorhandene Runtime-Anzeige/Statussemantik im Quellcode; keine neue Testdefinition oder Testausführung beauftragt. Tests ausdrücklich pausiert. Die bekannten Release- und Image-Budget-Blocker bleiben offen.

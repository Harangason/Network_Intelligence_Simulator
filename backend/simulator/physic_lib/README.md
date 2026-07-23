# physic_lib

Diese Bibliothek enthält wiederverwendbare Konfigurationen, Branchenprofile
und Referenzdaten. Jede Branche besitzt zusätzlich einen isolierten Bereich
für ihr lokales Lerngedächtnis und ihren Knowledge Graph. Laufzeit-Traces und
generierte Pakete gehören weiterhin nicht hierher; sie werden unter `traces/`
oder an einen ausdrücklich gewählten absoluten Zielpfad geschrieben.

## Struktur

- `Config/`
  wiederverwendbare Konfigurationsdaten für native Writer und den optionalen
  Szenarioassistenten
- `Industries/`
  neutrale und branchenspezifische Profile sowie je Branche:
  - `Learning/simulation_memory.db` für kompakte Laufhistorie
  - `Knowledge/knowledge_graph.db` für Knoten und Beziehungen
- `PhysicalAI/`
  optionale Workflow- und Integrationsreferenzen
- `Automotiv/`
  historische Automotive-Profile; kein Kernpfad der Standalone-Architektur
- `Samples/LegacyRootDbs/`
  historische Profildatenbank, keine Trace-Ausgabe

## Regeln

- Laufzeitwissen darf ausschließlich unter der passenden Branche in
  `Industries/<Branche>/Learning` oder `Industries/<Branche>/Knowledge` liegen.
- Die Laufzeitdatenbanken werden nicht versioniert.
- Keine generierten Tracepakete in der Bibliothek.
- Hardware-, Port-, Schnittstellen- und Netzwerkdefinitionen bleiben in
  Konfigurationsdateien unverändert erhalten.
- Branchenprofile dürfen Fachbegriffe verwenden; der Simulationskern bleibt
  technologie- und domänenneutral.

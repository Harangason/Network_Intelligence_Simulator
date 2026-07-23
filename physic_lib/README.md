# physic_lib

Diese Bibliothek enthält ausschließlich wiederverwendbare Konfigurationen,
Branchenprofile und Referenzdaten. Laufzeit-Traces und generierte Pakete gehören
nicht hierher; sie werden unter `traces/` oder an einen ausdrücklich gewählten
absoluten Zielpfad geschrieben.

## Struktur

- `Config/`
  wiederverwendbare Konfigurationsdaten für native Writer und den optionalen
  Szenarioassistenten
- `Industries/`
  neutrale und branchenspezifische Profile
- `PhysicalAI/`
  optionale Workflow- und Integrationsreferenzen
- `Automotiv/`
  historische Automotive-Profile; kein Kernpfad der Standalone-Architektur
- `Samples/LegacyRootDbs/`
  historische Profildatenbank, keine Trace-Ausgabe

## Regeln

- Keine Kunden- oder Laufzeitdaten in `physic_lib/`.
- Keine generierten Tracepakete in der Bibliothek.
- Hardware-, Port-, Schnittstellen- und Netzwerkdefinitionen bleiben in
  Konfigurationsdateien unverändert erhalten.
- Branchenprofile dürfen Fachbegriffe verwenden; der Simulationskern bleibt
  technologie- und domänenneutral.

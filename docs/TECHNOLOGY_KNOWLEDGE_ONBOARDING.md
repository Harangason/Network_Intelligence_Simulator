# Automatisches Onboarding von Netzwerktechnologien

Verbindlicher Laufzeitpfad für unbekannte Bus-, Netzwerk-, Kommunikations- und
Protokolltechnologien. Die Implementierung liegt in
`backend/communication/technologies/onboarding.py` und erweitert die bestehende
industrie-neutrale `TechnologyRegistry`.

## Ablauf und Zustände

1. `resolve` unterscheidet `KNOWN`, `PARTIALLY_KNOWN`, `UNKNOWN` und
   `OUTDATED_REVISION`; ähnliche Namen werden nur als Kandidaten gemeldet.
2. Der triggerbezogene Research-Plan beschreibt die fehlenden Kategorien und
   priorisiert Standards, offizielle Organisationen und Herstellerdatenblätter.
3. Research-Provider liefern ausschließlich strukturierte Quellen und Claims.
   Externe Inhalte werden nie ausgeführt. Code-/Prompt-Injection-Muster sperren
   sämtliche Claims der betroffenen Quelle.
4. Werte werden mit Einheit, Scope, Revision, Quelle und Confidence normalisiert.
   Nicht belastbare Werte bleiben `DATA_GAP`. Ein `SIMULATION_DEFAULT` bleibt
   unbestätigt und erfüllt keine Readiness-Anforderung.
5. Abweichende belastbare Quellen erzeugen `CONFLICT`; unterschiedliche
   Revisionen werden nicht intuitiv zusammengeführt.
6. Das Technology Pack erhält `DISCOVERED`, `PROVISIONAL`, `VALIDATED`,
   `SIMULATION_READY` oder `CONFLICTED`. Readiness wird getrennt für Topologie,
   Nachrichtenerzeugung, Timing, Buslast, Fehlermodell und Diagnostik berichtet.

## Persistenz und Registrierung

Packs liegen standardmäßig unter `technologies/generated/<technology-id>/`.
Die dortigen JSON-Dateien bilden den aktiven Stand; jede inhaltliche Version
wird zusätzlich unveränderlich unter `versions/<pack-sha256>/` abgelegt. Die
Umgebungsvariable `NIS_TECHNOLOGY_PACK_ROOT` darf für Tests oder Deployment einen
anderen Root setzen.

Core-Registrierung ist eine eigene, ausdrücklich bestätigte Operation. Sie ist
nur für konfliktfreie `VALIDATED`, `SIMULATION_READY` oder `VERIFIED` Packs
zulässig. Ein generiertes Pack darf keine eingebaute Technologie überschreiben.
Ausführbare generische Binding-/Generator-/Timing-/Load-Komponenten werden nur
registriert, wenn Message-Generation und Busload `READY` sind. Die Registrierung
ändert kein Projekt und startet keine Simulation; ein Projekt übernimmt die
Technologie erst über den normalen Proposal-/Review-Pfad.

## HTTP-Vertrag

- `POST /api/technologies/resolve`: Registry-/Alias-/Ähnlichkeitsauflösung.
- `POST /api/technologies/research`: Research-Plan plus Ergebnisse registrierter
  Research-Provider. Ohne Provider bleiben Quellen leer statt erfunden zu werden.
- `POST /api/technology-packs`: strukturierten Quellenstand validieren und Pack
  versioniert persistieren.
- `GET /api/technology-packs/<id>`: aktives Pack mit Digestprüfung lesen.
- `POST /api/technology-packs/<id>/register`: Core-Aufnahme; benötigt
  `X-NIS-Technology-Registration: confirmed`.

Der Engineering-Agent stellt dieselben Grenzen über
`resolve_network_technology`, `research_network_technology`,
`validate_technology_pack`, `persist_technology_pack`,
`inspect_technology_simulation_readiness`, `resolve_technology_parameter` und
`register_technology_pack` bereit. Persistenz und Registrierung benötigen die
`ADMIN`-Berechtigung; lesende Auflösung darf keine Projektwahrheit verändern.

Industrie und Technologie bleiben unabhängig. Der Erzeugungsregel-Manager leitet
einen unbekannten bestätigten Bustyp nach `technology_discovery`, nie still auf
Automotive oder ein generisches Protokoll.

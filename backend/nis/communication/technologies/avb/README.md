# AVB (`avb`)

## Verantwortung und Vertrag

`profile.json` ist die maßgebliche Definition für Identität, Varianten, Parameter,
Ratenmodell und Fähigkeiten; `definition.py` lädt sie. Die zentrale Registry
registriert dieses Profil genau einmal. `implementation_status`: **PLANNED**.
Kapazitätsnachweis laut Profil: **MODEL_MISSING**.
Ein Profil, Export oder ein Bitratenvorschlag ist kein funktionaler Timingnachweis.
Fehlende Modelle bleiben ausdrücklich unverifiziert; fremde Technologien werden
nicht als Ersatz verwendet.

## Öffentliche Schnittstellen

```python
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
profile = DEFAULT_TECHNOLOGY_REGISTRY.profile("avb")
review = DEFAULT_TECHNOLOGY_REGISTRY.parameter_defaults_review("avb")
```

Direkte Implementierungen: keine zusätzlichen ausführbaren Technologiealgorithmen.
Native Formatadapter: keine Adapter in diesem Paket.
`identity.json`, `review.json` und `physical.json` sind optionale, technologieeigene
Ergänzungen. Generische Timing-, PHY- und Simulationseinstiege delegieren an diese
Eigentümer; die Frontendprojektion entsteht durch `scripts/build/project-vocabulary.py`.

## Tests und Grenzen

Relevante Tests unter `backend/tests`: `test_technology_registry_metadata.py`, `test_technology_standard_defaults.py`;
zusätzlich `test_structure_architecture.py` und `test_structure_completion.py`.
SQL-Prüfungen laufen ausschließlich über `scripts/run-isolated-tests.py`.
Die Tests belegen ihren beschriebenen Umfang; sie zertifizieren keine Hardware,
keine Safetyfunktion und keine nicht implementierte Technologievariante.

## Erweiterungen

Neue technische Regeln und Adapter gehören in dieses Paket. Profiländerungen
erfordern Registry-, Parameter-, Projektlade- und Projektionstests. Branchenvorlagen
referenzieren die Technologie und erhalten keine eigene Implementierung.
Siehe [gemeinsamer Einstieg](../README.md).

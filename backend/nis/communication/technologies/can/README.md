# CAN 2.0A/B (`can`)

## Verantwortung und Vertrag

`profile.json` ist die maßgebliche Definition für Identität, Varianten, Parameter,
Ratenmodell und Fähigkeiten; `definition.py` lädt sie. Die zentrale Registry
registriert dieses Profil genau einmal. `implementation_status`: **IMPLEMENTED**.
Kapazitätsnachweis laut Profil: **MODEL_AVAILABLE**.
Ein Profil, Export oder ein Bitratenvorschlag ist kein funktionaler Timingnachweis.
Fehlende Modelle bleiben ausdrücklich unverifiziert; fremde Technologien werden
nicht als Ersatz verwendet.

## Öffentliche Schnittstellen

```python
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
profile = DEFAULT_TECHNOLOGY_REGISTRY.profile("can")
review = DEFAULT_TECHNOLOGY_REGISTRY.parameter_defaults_review("can")
```

Direkte Implementierungen: `arbitration.py`, `ownership.py`, `physical.py`, `scheduling.py`, `timing.py`.
Native Formatadapter: `can_arxml`, `can_asc`, `can_blf`, `can_csv`, `can_dbc`, `can_fibex`, `can_json`, `can_log`, `can_mdf`, `can_mf4`, `can_trc`, `can_txt`, `can_xml`, `can_yaml`, `can_yml`.
`identity.json`, `review.json` und `physical.json` sind optionale, technologieeigene
Ergänzungen. Generische Timing-, PHY- und Simulationseinstiege delegieren an diese
Eigentümer; die Frontendprojektion entsteht durch `scripts/build/project-vocabulary.py`.

## Tests und Grenzen

Relevante Tests unter `backend/tests`: `test_can_dispatcher.py`, `test_capacity_can_schedule.py`;
zusätzlich `test_structure_architecture.py` und `test_structure_completion.py`.
SQL-Prüfungen laufen ausschließlich über `scripts/run-isolated-tests.py`.
Die Tests belegen ihren beschriebenen Umfang; sie zertifizieren keine Hardware,
keine Safetyfunktion und keine nicht implementierte Technologievariante.

## Erweiterungen

Neue technische Regeln und Adapter gehören in dieses Paket. Profiländerungen
erfordern Registry-, Parameter-, Projektlade- und Projektionstests. Branchenvorlagen
referenzieren die Technologie und erhalten keine eigene Implementierung.
Siehe [gemeinsamer Einstieg](../README.md).


Zusätzlich konsolidierte vorhandene Implementierungen (2026-10-04):
- `encoding.py`
- `formats/trace_model.py`
- `formats/native_example.py`
- `formats/restbus_example.py`
- `formats/routing.py`
- `formats/native_configuration.py`
- `formats/mdf_writer.py`
- `formats/archived_example.py`

Regressionen: `backend/tests/test_structure_consolidation.py`;
ursprüngliche Unterstützungszustände und gespeicherte IDs bleiben maßgeblich.

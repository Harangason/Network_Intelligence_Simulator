"""Capture the existing registry and all consumer fields before the approved audit."""
import hashlib
import json
from pathlib import Path

from backend.app.simulation_service import SimulationService
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry

root = Path(__file__).resolve().parents[1]
dest = root / 'docs/implementation-workloads/technology-full-parameter-audit-20261001'
dest.mkdir(parents=True, exist_ok=True)
previous = json.loads((root / 'docs/implementation-workloads/technology-standard-defaults-20261001/workload.json').read_text(encoding='utf-8'))
paths = previous['files_inspected']
inventory = []
for p in registry.profiles():
    inventory.append({'technology': p['id'], 'profile': p,
                      'form_parameters': SimulationService._parameter_schema(p['id'], p),
                      'audit_status': 'PENDING', 'parameter_verification': [], 'sources': []})
(dest / 'inventory-before.json').write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding='utf-8')
diagnosis = '''# Vollständige Einzelprüfung aller Technologieparameter

Freigabe: Nutzer am 01.10.2026, alle Bustypen einzeln, ohne Technikschwerpunkt.

Erste fehlerhafte Schicht: SimulationService._parameter_schema erzeugt denselben
großen Parametersatz für nahezu alle Profile. TechnologyProfile.parameter_schema
deklariert dagegen fast nur Raten. Die API überschreibt diese zentrale Definition.
Alle allgemeinen Felder werden dort required=True, obwohl viele Anforderungen,
Hardwareeigenschaften oder NIS-Szenariowerte sind und keine Busstandard-Defaults.
Historische Katalograten haben vielfach keine unabhängig geprüfte Normquelle.
Das betrifft auch lokale Geräte-/Transaktionsfelder und ihre Zuordnung zu Netz,
Controller, Zielgerät und tatsächlicher Transaktion.

Die vorherige Struktur-/Ratenprüfung ersetzt diese vollständige fachliche Prüfung
nicht. Ein bestätigter Takt ersetzt keinen Geräte- oder Kapazitätsnachweis.

Vorgehen: Alphabetische vollständige Einzelakten, jedes Feld mit Bedeutung,
Einheit, Gültigkeitsbedingungen, Quelle/Version, Default und Evidenzstatus.
Für jede Technologie zusätzlich Schichten, PHY, Zugriff, Integrität, Adressierung,
Discovery/Diagnose/Überwachung, Geräte- und Transaktionsanforderungen prüfen.
Keine Universalwerte erfinden. Fehlende tatsächliche Geräteangaben offen halten.
Normquellen und NIS-Szenariopolitik getrennt ausweisen. Erst bei vollständiger
belegter Einzelakte und bestandener Regression eine Technologie abschließen.

Alle bestehenden Korrekturen bewahren. Vollständiges Release-Gate und exakt
geprüftes Image produktiv ausliefern, dort Identität und Funktion kontrollieren.
'''
(dest / 'diagnosis.md').write_text(diagnosis, encoding='utf-8')
reference = {'path': str(dest / 'diagnosis.md'), 'sha256': hashlib.sha256((dest / 'diagnosis.md').read_bytes()).hexdigest()}
workload = {
    'goal_id': dest.name, 'goal_type': 'repair', 'kind': 'repair', 'repository': str(root),
    'project_scope': 'Every registered technology individually; every parameter and every affected consumer',
    'requested_change': 'Source-backed complete per-technology parameter verification, stabilization and production delivery',
    'modify_code': True, 'allow_repair': True,
    'constraints': ['TechnologyProfile sole source', 'Sequential individual technology acceptance',
                    'Literature defaults with source and revision', 'No invented device evidence',
                    'No foreign technology defaults', 'Preserve confirmed data and previous corrections',
                    'SQL isolated only', 'Full release gate and exact tested image delivery'],
    'forbidden_changes': ['image pruning', 'product database test writes', 'weaken assertions or evidence',
                          'claim catalog enumeration or rate audit as full parameter verification'],
    'required_outcomes': ['all_technology_parameter_verification', 'canonical_applicable_parameter_profiles',
                          'device_transaction_network_evidence', 'all_consumer_consistency', 'production_delivery'],
    'validation_requirements': ['per_technology_regression', 'mixed_technology_isolation',
                                'frontend_and_storage', 'complete_release_gate', 'running_functionality'],
    'revision_before': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
    'unresolved_decisions': [], 'files_inspected': paths,
    'implementation_plan': ['Inventory all fields', 'Verify sources per technology alphabetically',
                            'Extend existing profiles and consumers', 'Verify every technology independently',
                            'Run full gate and deploy exact tested image'],
    'repair': {'owner': 'PROJECT_PRODUCT', 'first_failing_layer': 'TechnologyProfile / API schema construction',
               'root_cause': 'Shared required schema overrides profile ownership; unverified historical defaults and incomplete applicability',
               'reproduction': 'Compare registry profile parameter_schema with catalog form_parameters in inventory-before.json',
               'evidence': [reference], 'affected_files': paths,
               'acceptance_criteria': ['Every technology individually verified', 'Each field has source and applicability',
                                       'No false standard/device confirmation', 'Exact tested production delivery'],
               'targeted_tests': ['Each technology valid/default/invalid/applicability/source regression'],
               'weaken_assertions_to_pass': False},
    'files_changed': [], 'tests': [], 'validation': [], 'preflight': [],
    'remaining_findings': ['Full individual literature verification and implementation pending'],
    'completion_status': 'ANALYZING',
    'delivery': {'decision': 'YES', 'authorization': 'Explicit user approval and standing AGENTS.md production authorization',
                 'target': 'canonical NIS production on port 13500'},
}
(dest / 'workload.json').write_text(json.dumps(workload, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'technologies': len(inventory), 'form_fields': sum(len(p['form_parameters']) for p in inventory),
                  'workload': str(dest / 'workload.json')}))

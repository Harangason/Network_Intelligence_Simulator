"""Persist the individually reviewed ADC definitions, not a capacity certificate."""
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
folder = root / 'docs/implementation-workloads/technology-full-parameter-audit-20261001'
original = next(item for item in json.loads((folder / 'inventory-before.json').read_text(encoding='utf-8')) if item['technology'] == 'adc')
current = {item['key']: item for item in registry.parameter_fields('adc')}
meanings = {
    'cycle_ms': 'Anwendungsperiode des Signals, keine universelle ADC-Abtastperiode.',
    'minimum_cycle_time_ms': 'Minimale Projektperiode, nicht die geräteabhängige Sample-Rate.',
    'deadline_ms': 'Frist der Anwendung, separat von Acquisition und Wandlung.',
    'timeout_ms': 'Anwendungsüberwachung, kein ADC-Protokolltimer.',
    'maximum_latency_ms': 'Funktionale Maximalzeit, keine zugesicherte Wandlerzeit.',
    'jitter_ms': 'Projektbudget für Zeitabweichung, nicht eine gemessene Aperturunsicherheit.',
    'freshness_ms': 'Projektbudget für Datenalter; ADC-Datenblatt liefert keinen pauschalen Projektwert.',
    'source_processing_delay_ms': 'NIS-Szenarioannahme der Quellenverarbeitung, keine gemessene Acquisition-Zeit.',
    'target_processing_delay_ms': 'NIS-Szenarioannahme der Zielverarbeitung, keine gemessene Wandlungszeit.',
    'propagation_delay_ms': 'NIS-Leitungslaufzeitannahme, vom konkreten Leiter abhängig.',
    'required_reliability': 'Projektanforderung 0–1, kein ADC-Genauigkeits- oder ENOB-Nachweis.',
    'traffic_class': 'NIS-Anwendungskategorie, keine ADC-Arbitration.',
    'clock_offset_ms': 'Uhrenannahme des E2E-Szenarios, kein ADC-Registerdefault.',
    'clock_drift_ppm': 'Uhrenannahme des E2E-Szenarios, kein Datenblattnachweis.',
    'sync_precision_ms': 'Uhrenbudget des Szenarios, keine physische Sample-Apertur.',
    'sync_interval_ms': 'Uhrenannahme des Szenarios, keine universelle ADC-Synchronisation.',
    'maximum_sync_error_ms': 'E2E-Uhrenbudget, kein ADC-Standardwert.',
    'duration_s': 'NIS-Simulationsdauer in Sekunden.',
    'seed': 'Ganzzahliger NIS-Zufallsstart, kein Geräteparameter.',
    'max_events': 'Ganzzahliges NIS-Rechenbudget, kein Geräteparameter.',
    'dropout_probability': 'NIS-Ausfallinjektion 0–1, kein real gemessener ADC-Ausfall.',
}
assert set(current) == set(meanings)
removal = {
    'physical': 'Keine Busnachricht: Wort-/Samplebreite ist geräteabhängig, vier Byte sind kein ADC-Standardpayload.',
    'capacity': 'Keine Frame-Serialisierung oder Busauslastung bei diesem direkten Analogeingang.',
    'qos': 'Keine Frame-Queue, PCP-Priorität oder reservierte Busbandbreite am direkten Analogeingang.',
    'reliability': 'Keine Pakete, Framefehler, Duplikate oder Buswiederholungen; analoge Genauigkeit und Gerätesicherheit sind eigenständige Nachweise.',
    'synchronization': 'Kein natives NTP/PTP/gPTP-Protokoll eines ADC. Host-Uhrenannahmen werden separat geführt.',
    'gateway': 'Kein Gateway im direkten ADC-Anschluss; Durchsatz, Puffer und Konverter sind konkrete externe Geräte.',
}
records = []
for item in original['form_parameters']:
    key = item['key']
    records.append({'key': key, 'before': item, 'after': current.get(key),
                    'meaning_and_applicability_review': meanings[key] if key in current else removal[item['category']],
                    'decision': 'EXPLICIT_NIS_SCENARIO' if key in current else 'REMOVED_NOT_APPLICABLE',
                    'parameter_source_verified': True, 'runtime_timing_verified': False})
for item in registry.profile('adc')['local_timing_schema']:
    records.append({'key': 'local_timing_evidence.' + item['key'], 'after': item,
                    'meaning_and_applicability_review': 'Erfassungs-/Acquisition-Zeit' if item['key'] == 'sample_bound_ms' else 'Wandlungszeit nach Erfassung, getrennt von Acquisition und Setup.',
                    'decision': 'UNKNOWN_DEVICE_INPUT', 'parameter_source_verified': True, 'runtime_timing_verified': False})
data = {'technology': 'adc', 'status': 'SOURCE_AND_LOCAL_RULES_REVIEWED',
        'scope': 'Each original form field and both actual device timing bounds; type/range/applicability checks and persistent evidence rejection',
        'parameter_reviews': records,
        'sources': ['https://developerhelp.microchip.com/xwiki/bin/view/products/data-converters/adc-specs/acquisition-time/',
                    'https://www.ti.com/document-viewer/lit/html/SBAA531/GUID-C645C394-11B3-4154-8F36-0CBA90FBC5EC',
                    'docs/COMMUNICATION_DESIGN_CONTRACT.md'],
        'source_revisions': ['Microchip 2023-11-09', 'TI SBAA531, November 2021, section 2.2', 'NIS_SCENARIO_POLICY_V1'],
        'standard_defaults': {}, 'reason_no_bus_defaults': 'ADC sample width, resolution, range, acquisition, conversion and sample rate depend on the chosen converter and source circuit.',
        'remaining_runtime_status': 'DIRECT_IO_CAPACITY_NOT_APPLICABLE; device timing acceptance remains separate and unverified',
        'not_certified': ['Actual selected ADC electrical accuracy, noise, settling or sample-rate conformance', 'E2E timing acceptance', 'Production delivery'],
        'validation': {'isolated_parameter_storage_regression': '98 passed in 2.99s; nis_test_852e57b4f1c7',
                       'required_and_unverified_parameter_regression': '537 passed in 7.05s; nis_test_13321f936675; one existing Pydantic field warning',
                       'scope': 'All 21 retained fields type/default/bounds, direct IO isolation, device bounds, source, actual repository roundtrip and failed edit preserving previous state'}}
target = folder / 'individual/adc.json'
target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'technology': 'adc', 'reviewed_records': len(records), 'retained_fields': len(current), 'production_delivered': False}))

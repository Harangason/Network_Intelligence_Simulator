"""Persist the first individual source/rule review; this is not a release receipt."""
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry

folder = root / 'docs/implementation-workloads/technology-full-parameter-audit-20261001'
before = next(item for item in json.loads((folder / 'inventory-before.json').read_text(encoding='utf-8'))
              if item['technology'] == '5g')
fields = {field['key']: field for field in registry.parameter_fields('5g')}
notes = {
    'bitrate': 'Konfigurierte Datenrate; keine universelle 5G-Rate. Positive bit/s sind eine Eingabeprüfung, keine normative Mindestfrequenz.',
    'payload_bytes': 'Nutzdaten des NIS-Szenarios in Byte; weder 1500 Byte noch acht Byte sind eine allgemeine NR-Transportblockgrenze.',
    'cycle_ms': 'Anwendungsperiode in ms; 100 ms ist ein NIS-Szenariovorschlag, kein NR-Rahmen oder Slot.',
    'minimum_cycle_time_ms': 'Angeforderte minimale Nachrichtenperiode, kein 5G-Slotintervall.',
    'deadline_ms': 'Projektfrist der Nachricht; Protokolltakt belegt keine Erfüllung.',
    'timeout_ms': 'Anwendungsüberwachung in ms; kein RRC- oder HARQ-Timer.',
    'maximum_latency_ms': 'Zulässige funktionale Latenz; kein zugesicherter Funkstandardwert.',
    'jitter_ms': 'Projektbudget für Zeitabweichung; separat vom Kapazitätsnachweis.',
    'freshness_ms': 'Projektbudget für Datenalter; keine NR-Normvorgabe.',
    'source_processing_delay_ms': 'NIS-Verarbeitungsannahme an der Quelle, nicht garantierte Gerätezeit.',
    'target_processing_delay_ms': 'NIS-Verarbeitungsannahme am Ziel, nicht garantierte Gerätezeit.',
    'propagation_delay_ms': 'Szenarioannahme für Laufzeit; keine pauschale Funkreichweite oder zugesicherte Laufzeit.',
    'target_bus_load_percent': 'NIS-Auslegungsziel in Prozent; ohne Funkressourcenmodell keine bestätigte NR-Auslastung.',
    'peak_factor': 'Dimensionsloser NIS-Spitzenfaktor, kein 3GPP-QoS-Parameter.',
    'burst_factor': 'Dimensionsloser NIS-Burstfaktor, kein 3GPP-Bearerparameter.',
    'burst_window_ms': 'Beobachtungsfenster für NIS-Bursts, keine Radio-Frame-Dauer.',
    'warning_threshold': 'NIS-Warnschwelle in Prozent; keine normativ zugesicherte Last.',
    'critical_threshold': 'NIS-Kritischschwelle in Prozent; muss in der Anwendung zu den anderen Schwellen passen.',
    'overload_threshold': 'NIS-Überlastschwelle in Prozent, keine 5G-Kapazität.',
    'queue_size': 'Anzahl Einträge einer abstrakten NIS-Queue; keine UE-RLC/PDCP-Pufferkapazität.',
    'queue_policy': 'NIS-Queueverfahren; liefert keinen gNB-Schedulingnachweis und keine TSN-/CBS-Konformität.',
    'qos_priority': 'Entfernt: ein pauschales PCP-artiges 0–7-Feld ist keine NR-Logical-Channel-Priority.',
    'traffic_class': 'NIS-Verkehrskategorie, kein 5QI/QFI und keine normgerechte NR-Bearerkonfiguration.',
    'reserved_bandwidth_percent': 'Entfernt: Prozentsatz ohne Funkressourcen-/Bearerzuordnung ist kein belegter NR-Reservierungsparameter.',
    'packet_loss_probability': 'Injizierte NIS-Paketverlustwahrscheinlichkeit 0–1; kein zugesicherter Funkverlust.',
    'frame_loss_probability': 'NIS-Fehlerinjektion 0–1, keine zugesicherte NR-BLER.',
    'bit_error_rate': 'NIS-Bitfehlerrate 0–1 als Szenarioeingabe, keine gemessene PHY-Eigenschaft.',
    'corruption_probability': 'NIS-Fehlerinjektion 0–1.',
    'duplicate_probability': 'NIS-Duplikatinjektion 0–1, keine NR-PDCP-Konfiguration.',
    'reordering_probability': 'NIS-Reihenfolgeinjektion 0–1, kein RLC/PDCP-Reordering-Timer.',
    'retransmission_enabled': 'Entfernt: generischer Schalter mit false würde native HARQ-Unterstützung falsch beschreiben.',
    'retransmission_rate': 'Entfernt: native HARQ/ARQ sind von UE, gNB, Bearer und RLC-Modus abhängig.',
    'retry_limit': 'Entfernt: kein allgemeines NR-Wiederholungslimit null.',
    'retransmission_delay_ms': 'Entfernt: keine allgemeine NR-Wiederholungszeit null.',
    'required_reliability': 'Zuverlässigkeitsanforderung des Szenarios, kein Normnachweis.',
    'clock_offset_ms': 'NIS-Uhrenannahme in ms; keine gemessene UE/gNB-Synchronisation.',
    'clock_drift_ppm': 'NIS-Uhrenannahme; 20 ppm ist keine allgemein verifizierte NR-Oszillatorgrenze.',
    'sync_precision_ms': 'NIS-E2E-Uhrenannahme, keine NR-Zeitsynchronisationsgarantie.',
    'sync_interval_ms': 'NIS-E2E-Uhrenannahme, kein RRC-/SSB-Periodenparameter.',
    'sync_method': 'Entfernt: NTP/PTP/gPTP sind keine austauschbaren nativen NR-Synchronisationsmodi.',
    'maximum_sync_error_ms': 'NIS-E2E-Annahme für Uhrfehler, keine gemessene PHY-Grenze.',
    'gateway_delay_ms': 'NIS-Annahme für eine tatsächliche Gatewayressource; ohne Gerät kein garantierter Wert.',
    'gateway_queue_delay_ms': 'NIS-Gatewayannahme, keine normierte Funkwarteschlange.',
    'protocol_conversion_delay_ms': 'NIS-Annahme an einem tatsächlich verwendeten Konverter, kein NR-Normdefault.',
    'gateway_maximum_throughput': 'Entfernt: 100 Mbit/s belegt keine 5G-Gatewayfähigkeit.',
    'gateway_input_buffer': 'Entfernt: 256 Frames belegen keine 5G-Gatewayfähigkeit.',
    'gateway_output_buffer': 'Entfernt: 256 Frames belegen keine 5G-Gatewayfähigkeit.',
    'gateway_maximum_routes': 'Entfernt: 10000 Routen sind keine normierte 5G-Gerätefähigkeit.',
    'gateway_maximum_messages_s': 'Entfernt: 100000 Nachrichten/s sind keine normierte 5G-Gerätefähigkeit.',
    'duration_s': 'Positive NIS-Simulationsdauer in s, kein Busstandard.',
    'seed': 'NIS-Zufallsinitialisierung, kein Busparameter.',
    'max_events': 'NIS-Laufbudget, kein Busparameter.',
    'dropout_probability': 'NIS-Fehlerinjektion 0–1.',
    'nr_band': 'Gerätekonfiguration/Bandkombination; frei dokumentiert, keine automatische Bandkonformität.',
    'nr_frequency_range': 'Gerätedaten FR1/FR2 gemäß festgelegtem Release; kein pauschaler Default.',
    'nr_direction': 'UL/DL-Richtung des betrachteten Transfers; kein Default und keine Slave-Rollenannahme.',
    'nr_channel_bandwidth_mhz': 'Bandbreite je Träger; SCS-/FR-Kombination geprüft, konkrete Band-/UE-Fähigkeit bleibt erforderlich.',
    'nr_subcarrier_spacing_khz': 'SCS des Nutzdatenträgers; 240 kHz SS/PBCH nicht als Datenträgermodus angeboten.',
    'nr_mimo_layers': 'Layer je Träger, ganzzahlig; UL maximal vier, DL maximal acht im geprüften Release; tatsächliche UE-Fähigkeit erforderlich.',
    'nr_modulation_order': 'Maximal unterstützte Modulationsordnung je Träger; Optionen ersetzen keine UE-Fähigkeit.',
    'nr_carrier_count': 'Positive ganzzahlige Anzahl aggregierter Träger; keine automatische Kapazität aus einem pauschalen Einzelträgerwert.',
    'nr_scaling_factor': 'UE-Skalierungsfaktor aus der dokumentierten Rateformel, kein universeller Default.',
}
assert set(notes) == {field['key'] for field in before['form_parameters']} | set(fields)
records = []
for key, meaning in notes.items():
    original = next((field for field in before['form_parameters'] if field['key'] == key), None)
    current = fields.get(key)
    records.append({'key': key, 'meaning_and_applicability_review': meaning, 'before': original,
                    'after': current, 'decision': 'REMOVED_NOT_NATIVE' if current is None else
                    'UNKNOWN_DEVICE_INPUT' if key.startswith('nr_') or key == 'bitrate' else 'EXPLICIT_NIS_SCENARIO',
                    'parameter_source_verified': True, 'runtime_capacity_verified': False})
data = {'technology': '5g', 'status': 'SOURCE_AND_LOCAL_RULES_REVIEWED',
        'scope': 'NIS parameter definitions, source distinction, existing model limitations, local validation and storage',
        'not_certified': ['Actual UE/gNB/band conformance', 'Heterogeneous carrier aggregation rate calculation',
                          'Radio PHY/resource scheduler, packet timing and capacity', 'Production delivery'],
        'remaining_runtime_status': 'MODEL_MISSING', 'parameter_reviews': records,
        'sources': list(dict.fromkeys([field['source'] for field in fields.values()] +
                    [rule.get('source') for rule in registry.profile('5g')['parameter_constraints'] if rule.get('source')] +
                    ['https://www.etsi.org/deliver/etsi_ts/138300_138399/138300/16.13.00_60/ts_138300v161300p.pdf'])),
        'validation': {'isolated_parameter_and_storage_tests': '61 passed in 2.23s, nis_test_f942aed800e0',
                       'mixed_transport_regression': '485 passed in 6.19s, nis_test_57e1b1745899',
                       'profile_scope_and_new_rules': '43 passed in 5.18s, nis_test_0e15128241db',
                       'frontend_data_helpers': '16 passed; no browser or production claim'}}
target = folder / 'individual' / '5g.json'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'technology':'5g','parameter_records':len(records),'status':data['status']}))

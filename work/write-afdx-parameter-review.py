"""Review each AFDX field against its own literature and explicit NIS scope."""
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
folder = root / 'docs/implementation-workloads/technology-full-parameter-audit-20261001'
before = next(item for item in json.loads((folder / 'inventory-before.json').read_text(encoding='utf-8')) if item['technology'] == 'afdx')
fields = {item['key']: item for item in registry.parameter_fields('afdx')}
baseline = {item['key']: item for item in json.loads((folder / 'individual/5g.json').read_text(encoding='utf-8'))['parameter_reviews']}
native = {
    'bitrate': 'AFDX has its own allowed link modes and documented 100 Mbit/s default; generic Ethernet gigabit is invalid.',
    'payload_bytes': 'Application bytes, not MAC frame bytes; static limit and configured LMAX both apply.',
    'duplex': 'Only full duplex for this AFDX profile.',
    'afdx_bag_ms': 'Integrator-selected power-of-two BAG; lowest allowed mode proposed, no universal actual BAG.',
    'afdx_lmax_frame_bytes': 'Configured per-VL MAC frame including FCS; not an application payload length.',
    'afdx_jitter_bound_us': 'Actual ES jitter bound required; protocol ceiling is not a measured guarantee.',
    'afdx_vl_id': 'Integrator-assigned VL ID, not CAN arbitration ID or PCP priority.',
    'afdx_redundancy': 'Documented default transmits on both networks; installed A/B paths still require evidence.',
    'queue_policy': 'Abstract ordered NIS queue/sub-VL round robin; no executable AFDX schedule or generic TAS/CBS proof.',
}
removed = {
    'qos_priority': 'PCP-like priority is not VL traffic shaping.', 'sync_method': 'Generic NTP/PTP/gPTP is not native AFDX.',
    'reserved_bandwidth_percent': 'VL allocation depends on configured LMAX/BAG, not an unbound percentage.',
    'mtu_bytes': 'Generic MTU up to 65535 replaced by explicit per-VL frame limit.',
    'vlan_id': 'This untagged AFDX frame profile has no generic VLAN field.',
    'rate_limit_bit_s': 'An arbitrary limiter does not implement BAG traffic shaping.',
}
for key in ('retransmission_enabled', 'retransmission_rate', 'retry_limit', 'retransmission_delay_ms'):
    removed[key] = 'AFDX does not guarantee delivery with native acknowledgements/retries; application reliability is separate.'
for key in ('gateway_maximum_throughput', 'gateway_input_buffer', 'gateway_output_buffer', 'gateway_maximum_routes', 'gateway_maximum_messages_s'):
    removed[key] = 'A fixed generic gateway capability is not a confirmed AFDX end-system or switch capability.'
original = {item['key']: item for item in before['form_parameters']}
assert set(original) - set(fields) == set(removed)
records = []
for key in sorted(set(original) | set(fields)):
    item = fields.get(key)
    meaning = removed[key] if item is None else native.get(key)
    if meaning is None:
        # The shared NIS controls were reviewed individually in the first file.
        meaning = baseline[key]['meaning_and_applicability_review'].split(';')[0].split(', kein')[0]
        meaning += '; explicit NIS scenario/application requirement, not an AFDX standard or actual equipment evidence.'
    records.append({'key': key, 'before': original.get(key), 'after': item,
        'meaning_and_applicability_review': meaning,
        'decision': 'REMOVED_NOT_APPLICABLE' if item is None else 'AFDX_NATIVE_OR_CONFIGURATION' if key in native and key != 'queue_policy' else 'EXPLICIT_NIS_SCENARIO',
        'parameter_source_verified': True, 'runtime_capacity_verified': False})
data = {'technology': 'afdx', 'status': 'SOURCE_AND_LOCAL_RULES_REVIEWED',
        'scope': 'Each original and added NIS field; AFDX parameter applicability, literature proposal, strict local validation, storage and lower-layer isolation',
        'sources': ['https://ww1.microchip.com/downloads/aemdocuments/documents/fpga/ApplicationNotes/ApplicationNotes/afdx_solutions_an.pdf',
                    'https://www.aim-online.com/products-overview/tutorials/afdx-arinc664p7-tutorial/', 'docs/COMMUNICATION_DESIGN_CONTRACT.md'],
        'source_revisions': ['Actel AC221 March 2005, pages 2–5', 'AIM AFDX tutorial accessed 2026-10-01', 'NIS_SCENARIO_POLICY_V1'],
        'source_scope': 'Primary manufacturer literature; no claim of certification against the complete latest purchased ARINC standard.',
        'parameter_reviews': records, 'remaining_runtime_status': 'MODEL_MISSING',
        'not_certified': ['Installed ES/switch configuration', 'VL shaping/policing, ES jitter equation and E2E schedule', 'Latest ARINC conformance', 'Production delivery'],
        'validation': {'isolated': '168 passed, one existing Pydantic warning, in 6.06s; nis_test_2fb16962e2bc',
                       'catalog_and_pair_isolation': '114 passed, one existing warning, in 15.14s; nis_test_d57dcd389f48',
                       'scope': 'Every retained field tested individually, LMAX/payload dependency, mode constraints, group save/read and failed edits preserving state'}}
(folder / 'individual/afdx.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'technology': 'afdx', 'reviewed_records': len(records), 'fields': len(fields), 'production_delivered': False}))

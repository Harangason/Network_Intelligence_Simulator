"""Record the AMQP review and machine-readable local test evidence."""
import hashlib
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
folder = root / 'docs/implementation-workloads/technology-full-parameter-audit-20261001'
original = next(item for item in json.loads((folder / 'inventory-before.json').read_text(encoding='utf-8')) if item['technology'] == 'amqp')
before = {item['key']: item for item in original['form_parameters']}
after = {item['key']: item for item in registry.parameter_fields('amqp')}
base = {item['key']: item['meaning_and_applicability_review'] for item in json.loads((folder / 'individual/5g.json').read_text(encoding='utf-8'))['parameter_reviews']}
notes = {
    'bitrate': 'Inherited explicit Ethernet link; no AMQP physical rate.',
    'payload_bytes': 'Body length, not negotiated frame or encoded-message limit.',
    'mtu_bytes': 'IPv4/Ethernet baseline MTU, distinct from AMQP messages.',
    'duplex': 'Actual Ethernet PHY mode remains unknown.',
    'queue_policy': 'Abstract NIS queue; broker priorities and credit are distinct.',
    'amqp_version': 'This review covers 1.0, not 0-9-1.',
    'amqp_max_frame_size_bytes': 'Receive frame limit; negotiation remains required.',
    'amqp_channel_max': 'Highest channel index, not number of active sessions.',
    'amqp_idle_timeout_ms': 'Zero/unset means no declared idle timeout.',
    'amqp_sender_settle_mode': 'Sender settlement policy; mixed is the omitted-field default.',
    'amqp_receiver_settle_mode': 'Receiver settlement policy; first is the default.',
    'amqp_incomplete_unsettled': 'Attach unsettled-map completeness flag.',
    'amqp_link_credit': 'Current link credit is actual peer state.',
    'amqp_message_priority': 'Native message priority; differs from Ethernet PCP.',
    'amqp_durable': 'Message durability requirement; broker capability remains separate.',
    'amqp_ttl_ms': 'Optional message expiry; no invented universal TTL.',
    'amqp_max_message_size_bytes': 'Exact ulong; zero/unset imposes no link limit.',
}
removed = {
    'qos_priority': 'Generic priority replaced by native AMQP message priority.',
    'sync_method': 'NTP/PTP/gPTP are not native AMQP connection controls.',
    'reserved_bandwidth_percent': 'Percentage without transport/broker resources is not AMQP credit.',
    'vlan_id': 'Optional lower-layer VLAN needs its own verified link profile.',
    'rate_limit_bit_s': 'Generic rate limiter does not model AMQP link credit.',
}
for key in ('retransmission_enabled', 'retransmission_rate', 'retry_limit', 'retransmission_delay_ms'):
    removed[key] = 'Generic retry controls replaced by native settlement; TCP ordering and broker delivery remain separate.'
for key in ('gateway_maximum_throughput', 'gateway_input_buffer', 'gateway_output_buffer', 'gateway_maximum_routes', 'gateway_maximum_messages_s'):
    removed[key] = 'Unconfirmed generic gateway capability is not an AMQP broker/peer guarantee.'
assert set(before) - set(after) == set(removed)
records = []
for key in sorted(set(before) | set(after)):
    field = after.get(key)
    note = removed[key] if field is None else notes.get(key)
    if note is None:
        note = base[key].split(';')[0].split(', kein')[0] + '; explicit NIS scenario or project requirement, not an AMQP standard guarantee.'
    records.append({'key': key, 'before': before.get(key), 'after': field,
                    'meaning_and_applicability_review': note,
                    'decision': 'REMOVED_NOT_APPLICABLE' if field is None else 'NATIVE_OR_DECLARED_LOWER_LAYER' if key in notes and key != 'queue_policy' else 'EXPLICIT_NIS_SCENARIO',
                    'parameter_source_verified': True, 'runtime_capacity_verified': False})
xml = folder / 'individual/amqp-tests.xml'
data = {'technology': 'amqp', 'status': 'SOURCE_AND_LOCAL_RULES_REVIEWED',
        'scope': 'All original and added fields; native 1.0 defaults, explicit Ethernet/IPv4/TCP baseline, exact numeric storage and protocol/layer isolation',
        'parameter_reviews': records, 'remaining_runtime_status': 'MODEL_MISSING; no registered standalone AMQP generator',
        'sources': ['https://docs.oasis-open.org/amqp/core/v1.0/os/amqp-core-transport-v1.0-os.html',
                    'https://docs.oasis-open.org/amqp/core/v1.0/os/amqp-core-messaging-v1.0-os.html',
                    'https://www.ieee802.org/3/archive.html', 'https://www.rfc-editor.org/rfc/rfc894',
                    'https://www.rfc-editor.org/rfc/rfc791.html', 'docs/COMMUNICATION_DESIGN_CONTRACT.md'],
        'source_revisions': ['OASIS AMQP 1.0 2012-10-29 Parts 2 and 3', 'IEEE Ethernet archive accessed 2026-10-01', 'RFC 894 1984-04', 'RFC 791 1981-09'],
        'not_certified': ['Actual broker/session/link state and negotiated capabilities', 'Other AMQP versions or undeclared physical/IPv6 transports',
                          'Wire serialization, flow scheduling and broker capacity', 'Production delivery'],
        'validation': {'isolated': '194 passed in 3.84s; nis_test_bc86f2565e3b',
                       'regression': '219 passed with one existing Pydantic warning in 4.44s; nis_test_46e7ba84570f',
                       'evidence': {'path': str(xml), 'sha256': hashlib.sha256(xml.read_bytes()).hexdigest()},
                       'scope': 'Every field type/options/bounds; 64-bit text value save/read, invalid edits preserving state, separate frame/body limits, explicit missing execution model'}}
(folder / 'individual/amqp.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
inventory = json.loads((folder / 'inventory-before.json').read_text(encoding='utf-8'))
progress = []
for profile in inventory:
    file = folder / 'individual' / (profile['technology'] + '.json')
    review = json.loads(file.read_text(encoding='utf-8')) if file.exists() else {}
    progress.append({'technology': profile['technology'], 'status': review.get('status', 'PENDING'),
                     'parameter_records': len(review.get('parameter_reviews', [])),
                     'production_delivered': False})
(folder / 'progress.json').write_text(json.dumps({'total_technologies': len(progress),
    'source_and_local_reviews': sum(item['status'] == 'SOURCE_AND_LOCAL_RULES_REVIEWED' for item in progress),
    'overall_status': 'IN_PROGRESS', 'complete_release_gate': 'NOT_RUN', 'production_delivered': False,
    'technologies': progress}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'technology': 'amqp', 'records': len(records), 'source_and_local_reviews': 4, 'total': len(progress), 'production_delivered': False}))

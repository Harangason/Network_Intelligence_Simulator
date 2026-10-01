"""Record the independently researched upper-layer decisions plus its explicit CAN lower layer."""
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
can = json.loads((folder / 'can-review-decisions.json').read_text(encoding='utf-8'))
native = {**can['native'],
    'bitrate': 'CANaerospace1.7 section1 permits any CAN data rate. No universal default; historical1Mbit/s and section6.1 example12.5ms/80Hz are not mandatory. Explicit HS CAN lower layer retains actual uniform rate/timing and1M ceiling.',
    'payload_bytes': 'Actual CANaerospace standard-header message body0..4 bytes unknown. Four-byte header is excluded from this body; lower CAN DLC=body+4. NODATA0 carries no body, including IDS request. Actual native datatype controls size, no assumed8-byte application payload.',
    'can_dlc': 'Actual lower CAN Data field length4..8 for this registered standard-header baseline; exact body+4. Not the body length or a remote-request length.',
    'can_frame_type': 'Only DATA applies to the registered standard-header CANaerospace message transport; CAN REMOTE request is not a CANaerospace service message.',
    'canas_revision': 'Declared specification1.7 baseline2006-01-12. Later drafts/ARINC825 adaptations are not claimed as verified by this specific profile.',
    'canas_header_type': 'Standard four-byte header identification code0 proposed. Other actual header types require an explicit extension; never pretend their lengths or encoding match standard0.',
    'canas_byte_order': 'Standard body uses BIG_ENDIAN encoding, fixed proposal. Actual host CPU endianness must not change wire encoding. Signed values/raw service octets require explicit encoding.',
    'canas_message_class': 'Actual message class EED/NSH/UDH/NOD/UDL/DSD/NSL unknown. Explicit standard distribution0 activates own base-ID class ranges; class is not automotive device type.',
    'canas_base_identifier': 'Actual base identifier before redundancy offset unknown. Standard distribution class ranges0..127/128..199/200..299/300..1799/1800..1899/1900..1999/2000..2031. No parameter name inferred from an ID alone. Custom schemes beyond registered baseline need extension.',
    'canas_redundancy_level': 'Unredundant baseline0 proposed; nonzero requires extended29-bit CAN identifier and actual identifier=base+65536*level. Level integer0..8191 from29-bit identifier range, not a default redundant architecture or safety guarantee.',
    'canas_node_id': 'Actual encoded header Node-ID octet0..255 unknown. Zero broadcasts to all nodes; EED/NOD header identifies sender whereas NSH/NSL identifies addressed station. NIS node-ID service1..199 range is not indiscriminately imposed on every octet.',
    'canas_data_type': 'Actual datatype code unknown. Standard0..31 map exact body lengths; reserved32..99 rejected. User-defined100..255 requires actual explicit encoding and is not automatically interpreted. DOUBLEH/DOUBLEL each4 bytes, not one8-byte CANaerospace body.',
    'canas_service_code_octet': 'Actual encoded header octet0..255 unknown. Meaning message-class specific; unused NOD service code is zero only when actual unused condition is known. Negative service response codes need signed-to-octet encoding, not generic negative raw byte input.',
    'canas_message_code': 'Actual sequence/service extension octet0..255 unknown. NOD increments modulo256; NSH/NSL uses service extension semantics. No invented initial/current sequence or proof of live monitoring from static validation.',
    'canas_nod_service_code_used': 'Actual NOD use unknown boolean; known false requires service code0. Not a checkbox silently set false and confirmed.',
    'canas_service_role': 'Actual REQUEST/RESPONSE direction unknown, governs paired CAN identifiers. Not generic I2C read/write direction.',
    'canas_service_channel': 'Actual high-priority channel0..35 or low-priority100..115 unknown. For standard services high requestID128+2*channel, response+1; low request1800+2*channel,response+1. Mandatory IDS channel0 support does not automatically configure every service on channel0.',
    'canas_ids_supported': 'Actual mandatory IDS-on-channel0 capability unknown; explicitly false cannot conform to registered baseline. Mandatory protocol requirement never automatically becomes confirmed device support.',
    'canas_response_deadline_ms': 'Standard100-ms response deadline proposal for requests requiring a response. Connectionless/BSS successful no-response services do not acquire a fake response transaction.',
    'canas_response_bound_ms': 'Actual service response time bound unknown, nonnegative<=100ms for requests requiring response. Neither standard deadline nor configured bitrate proves this actual bound.',
    'canas_distribution_id': 'Recommended standard distribution code0 proposed; reserved1..99 rejected, user-defined100..255 explicit and unmodeled. No implicit identification response confirming actual peer scheme or custom encoding.'
}
spec = {'technology':'can_aerospace','native':native,'removed':can['removed'],
    'sources':['https://files.stockflightsystems.com/_5_CANaerospace/canas_17.pdf',*can['sources']],
    'revisions':['CANaerospace1.7 2006-01-12 sections1/2.1/2.2/3.1/4/4.1/4.11/6.1/7.1; actual header and native lengths, not illustrative rates',*can['revisions']],
    'scope':'Each CANaerospace form parameter reviewed independently with explicit registered1.7 standard header and CAN CC HS lower layer. Static native type/length/header/ID/channel/timing checks and persistence; no implemented service state machine or capacity/safety conformance claim.',
    'validation':{'isolated_sql':True,'suite':'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review','passed':0},
    'not_certified':['Actual nodes/clock/PHY/service response/IDS capability or observed sequence',
        'User-defined header/encoding/distribution engine or post1.7 profile',
        'Node service, block download/upload and synchronization execution',
        'Actual bus schedule, fault handling, redundancy or safety certification',
        'Application packet packing and correlated functional E2E acceptance']}
(folder / 'can_aerospace-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

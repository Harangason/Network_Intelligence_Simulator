"""Record an individual custom-binary review without inventing a standard."""
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
native = {
    'payload_bytes': 'Actual application data octets unknown nonnegative integer; no universal 8/65535-byte default/limit for arbitrary binary protocols. Actual peer capacity, framing and lower transport constraints remain separate.',
    'cb_specification_source': 'Required actual authored binary protocol reference; absent specification stays UNVERIFIED. NIS design contract requires preserving explicit encodings but is not a user protocol standard.',
    'cb_specification_revision': 'Required actual specification revision; no fabricated version1 baseline. Field range semantics, compatible endpoints and wire model must refer to that revision.',
    'cb_transport_binding': 'Required actual lower transport/interface reference, unknown; no Ethernet/CAN or automotive inference. Text reference does not itself execute binding or certify PHY/schedule capacity.',
    'cb_layout_source': 'Actual per-signal binary layout/scaling/signedness/alignment/encoding reference unknown; no generic Intel/Motorola encoding default.',
    'cb_framing': 'Required actual FIXED_LENGTH/LENGTH_PREFIX/DELIMITER/TRANSPORT_MESSAGE/CUSTOM classification. No default; stream chunks are not inherently complete application messages.',
    'cb_byte_order': 'Actual LITTLE_ENDIAN/BIG_ENDIAN/FIELD_SPECIFIC unknown. Field-specific layout required for mixed values, independently from transport or bit significance.',
    'cb_bit_order': 'Actual LSB_FIRST/MSB_FIRST/FIELD_SPECIFIC significance/layout unknown. Not inferred from industry, byte order or serial physical transmission direction.',
    'cb_header_bytes': 'Actual encoded application header unknown nonnegative integer; excludes lower transport header. Must include any prefix/checksum physically placed within this header.',
    'cb_trailer_bytes': 'Actual encoded application trailer unknown nonnegative integer; includes delimiter/checksum if protocol puts them there. No fixed2 CRC default.',
    'cb_padding_bytes': 'Actual encoded application padding octets unknown nonnegative integer; alignment/escape expansion needs actual layout, not assumed zero.',
    'cb_message_bytes': 'Actual complete application message unknown; exact sum of known payload/header/trailer/padding, bounded by known actual peer message capacity. Can exceed65535 over segmented/streamed transports.',
    'cb_peer_message_limit_bytes': 'Actual peer accepted full message octets unknown nonnegative integer; not inherited Ethernet MTU or CAN8, not automatically maximum65535.',
    'cb_fixed_length_bytes': 'Actual positive fixed complete message length unknown, applies only FIXED_LENGTH and equals actual complete message size when both known.',
    'cb_length_prefix_bytes': 'Actual positive integer prefix width unknown, applies only LENGTH_PREFIX. No default2-byte length or assumed u16 cap; signedness/order/count scope need actual spec.',
    'cb_length_prefix_scope': 'Actual prefix counts PAYLOAD/COMPLETE_MESSAGE/CUSTOM unknown. Prefix value/overflow/on-wire layout still requires actual spec/encoder; no copied TCP data offset.',
    'cb_delimiter_hex': 'Actual nonempty sequence of full hex octets unknown, applies only DELIMITER. Odd hex rejected; escaping and delimiters occurring in binary data require actual algorithm, no CRLF default.',
    'cb_escaping_source': 'Actual delimiter/byte-stuffing framing algorithm reference unknown. Actual encoded expansion must be included in complete message; escaping is not CAN bit stuffing.',
    'cb_checksum': 'Actual NONE/CRC/HASH_MAC/CUSTOM unknown, no universal CRC16. NONE forbids meaningful checksum algorithm and requires zero supplied checksum octets; CRC/MAC require actual polynomial/key/coverage revision.',
    'cb_checksum_bytes': 'Actual checksum octets unknown nonnegative integer, already included in encoded header/trailer to avoid double counting. Known NONE permits0 only; no automatic actual zero.',
    'cb_checksum_source': 'Actual checksum parameters/init/reflection/coverage/MAC algorithm reference unknown; rejected NONE. Specification reference is not checksum execution or authentication proof.',
    'cb_device_evidence': 'Actual matching peer capability/device timing reference unknown; no automatic source/confirmed true from NIS generic defaults.'
}
removed = {
    'qos_priority': 'No implicit IEEE Ethernet PCP/CAN priority for an unspecified binary application protocol; actual lower transport owns priority.',
    'sync_method': 'No implicit NTP/PTP/gPTP support in a custom binary protocol; actual timing/synchronization requires its own specification.',
    'reserved_bandwidth_percent': 'No universal binary-protocol bandwidth reservation; actual underlying link/schedule evidence required.',
    'retransmission_enabled': 'No universal custom binary acknowledgement/ARQ default. Actual lower transport and application retry rules must be distinguished.',
    'retransmission_rate': 'A generic probability is not a binary acknowledgement/retry state machine.',
    'retry_limit': 'No zero retry-count protocol default without a specified application/lower-transport retry mechanism.',
    'retransmission_delay_ms': 'No universal zero retry delay for unspecified binary framing/session semantics.',
    'gateway_maximum_throughput': 'No verified binary gateway throughput of100Mbit/s; actual device unknown.',
    'gateway_input_buffer': 'Actual gateway input capability unknown, not binary protocol default8.',
    'gateway_output_buffer': 'Actual gateway output capability unknown, not binary protocol default8.',
    'gateway_maximum_routes': 'Actual gateway route capability unknown, not binary protocol default4096.',
    'gateway_maximum_messages_s': 'Actual gateway processing capability unknown, not binary protocol default100000.'
}
spec = {'technology': 'custom_binary', 'native': native, 'removed': removed,
        'sources': ['docs/COMMUNICATION_DESIGN_CONTRACT.md', 'docs/NIS_TECHNOLOGY_PROFILE_COMMUNICATION_MECHANISMS_STABILIZATION.md'],
        'revisions': ['Repository encoding/TechnologyProfile contracts accessed2026-10-01; no universal custom-binary standard exists'],
        'scope': 'Every registered custom-binary parameter, explicit unknown custom specification/framing/encoding/checksum/transport; type, local dependency, large-message and isolated SQL retention checks.',
        'validation': {'isolated_sql': True, 'suite': 'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters', 'passed': 0},
        'not_certified': ['Actual custom specification/revision/peer agreement and detailed field layout unavailable; no invented literature defaults',
                          'Actual resolved lower transport binding and PHY/arbitration/timing/schedule remain unverified',
                          'Executable framing/escaping/length-prefix/checksum/encoder/decoder and capacity model remain MODEL_MISSING',
                          'Actual peer capability/source lifetime and per-message wire correlation']}
(folder/'custom_binary-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

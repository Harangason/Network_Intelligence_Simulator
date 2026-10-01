"""DeviceNet's explicitly specified CAN foundation and independent CIP/wiring review."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root/'docs/implementation-workloads/technology-full-parameter-audit-20261001'
can = json.loads((folder/'individual/can.json').read_text(encoding='utf-8'))
native = {item['key']: item['meaning_and_applicability_review'] + '; applies only because DeviceNet specifies CAN CC as its data link; own adaptation constraints override generic CAN proposals.'
          for item in can['parameter_reviews'] if item['decision'] == 'NATIVE_OR_DECLARED_CONFIGURATION'}
native.update({
    'bitrate': 'DeviceNet modes125/250/500kbit/s only, own minimum/default125k proposal from Rockwell2022 page19; all actual nodes must agree. Not genericCAN100k or Ethernet rate.',
    'payload_bytes': 'Actual CAN data octets0..8 unknown integer; not complete reassembled CIP message limit. Header and application bytes explicitly separate.',
    'can_frame_format': 'DeviceNet unmodifiedCAN CC baseline11-bit BASE_11 proposal; rejects extended29-bit orFD frames.',
    'can_frame_type': 'DeviceNet reviewed DATA baseline only; CAN remote frame not an implicit DeviceNet connection message.',
    'can_identifier': 'Actual11-bit identifier unknown, classic groups1..4 explicitly mapped to message/group/MAC, max2031; alternate DEVICE_SPECIFIC edition remains unknown and cannot establish conformance.',
    'can_termination_ohms': 'Own DeviceNet nominal121ohms proposal, two trunk-end resistors with1percent tolerance119.79..122.21. Installed counts/power/topology not inferred; not CAN120ohms exact default.',
    'can_bus_length_m': 'Actual farthest node/terminator path including appropriate end drops unknown metres; cableTHICK/MID/THIN/FLAT and selected125/250/500k rate bound independently. Mixed-cable budget requires actual evidence.',
    'can_stub_length_m': 'Actual longest trunk-to-node drop unknown0..6m; also cannot exceed known cumulative drops. No universal0.3m CAN application limit.',
    'dn_specification_source': 'Actual matched DeviceNet adaptation edition reference unknown; current licensedVolume3v1.16 not fully available/read. Public classic baseline is not all-edition conformance.',
    'dn_eds_source': 'Actual matching nodeEDS/device/firmware/capability reference unknown; no fabricated installed device support.',
    'dn_mac_id': 'Actual bus node MAC address unknown integer0..63; not CANopen1..127. Bus uniqueness separate duplicate-MAC evidence.',
    'dn_node_count': 'Actual bus node count unknown integer1..64; no assumed node count or verified unique addresses.',
    'dn_identifier_layout': 'Public classicGROUPS_1_4 proposal; alternateDEVICE_SPECIFIC requires matched edition/source and is not automatically validated classic mapping or DeviceNetofThingsGroup5.',
    'dn_message_group': 'Actual classic message group1..4 unknown; each has independent ID layout/range. Group4 contains no MAC field.',
    'dn_identifier_mac_id': 'Actual identifier-encoded MAC unknown integer0..63; may be source or destination depending connection, never equated automatically to node MAC.',
    'dn_message_id': 'Actual group-specific message ID unknown; group1max15/group2max7/group3max6/group4max47. Classic CANID formulas checked when components known.',
    'dn_cable_type': 'Actual THICK/MID/THIN/FLAT/MIXED cable unknown. Each public manual path limit independently evaluated with selected link rate; mixed sections need actual budget.',
    'dn_topology': 'DeviceNet trunk/drop nominal proposal; actual wiring/terminators/branch/loop verification remains unverified.',
    'dn_cumulative_drop_m': 'Actual sum of all drops unknown nonnegative metres; max156/78/39m at125/250/500k, independent of farthestpath and single-drop6m.',
    'dn_supply_voltage_v': 'Actual regulated supply under load unknown positive finite volts; nominal24V is not installed/verified voltage.',
    'dn_worst_node_voltage_v': 'Actual worst-case loaded node voltage unknown>=0V, <=known supply and >=known device minimum. Unknown voltage/current/path budget not inferred.',
    'dn_device_minimum_voltage_v': 'Actual matched device minimum operating voltage unknown positive finite volts; actual actuator requirements can differ, no universal example19.2V.',
    'dn_power_evidence': 'Actual cable cross-section/resistance/current/temperature/supply/voltage-drop reference unknown; 8A cable capacity or conditionalClass2 rules are not actual current defaults.',
    'dn_connection_type': 'Actual EXPLICIT/POLLED/BIT_STROBE/CYCLIC/CHANGE_OF_STATE unknown; EDS/scan-list/CIP mapping needed. Does not imply CANopenPDO or Ethernet connection.',
    'dn_connection_state': 'Actual UNCONNECTED/ESTABLISHED/FAULTED unknown; duplicateMACFalse precludesESTABLISHED. Positive declaration is not observed handshake.',
    'dn_duplicate_mac_passed': 'Actual duplicate-MAC test result unknown boolean; never defaultTrue. False prevents declared established connection.',
    'dn_connection_source': 'Actual connection/path/object/scan-list mapping reference unknown; differing Rockwell scanner auto-settings cannot become universalDeviceNet default.',
    'dn_expected_packet_rate_ms': 'Actual negotiated expectedpacket/watchdog milliseconds unknown>=0; precise zero/off/multiplier behavior requires matched connection/edition, not universal100ms.',
    'dn_inhibit_ms': 'Actual COS production-inhibit milliseconds unknown>=0; <=known heartbeat. It is not CAN arbitration priority or arbitrary retry timer.',
    'dn_heartbeat_ms': 'Actual COS heartbeat milliseconds unknown>=0, bounded against known inhibit; device/connection-specific zero behavior and timeout evidence remain explicit.',
    'dn_interscan_ms': 'Actual scanner interscan delay unknown>=0ms; throughput/load and scanner-family defaults differ, no universal10ms.',
    'dn_protocol_header_bytes': 'Actual DeviceNet/fragment/explicit header within selectedCAN frame unknown integer0..8; depends group/connection/fragment format, no universal1byte.',
    'dn_cip_data_bytes': 'Actual application bytes in selected frame unknown integer0..8; equals known framepayload minus protocolheader. Complete fragmented message size is separate.',
    'dn_complete_message_bytes': 'Actual complete reassembledCIP message unknown nonnegative integer; unfragmented<=8 and equals known application framebytes; fragmented>=known frameCIPbytes and <=known peer bound.',
    'dn_peer_message_limit_bytes': 'Actual peer/scanner complete-message limit unknown nonnegative integer;255B implementation example is not universal standard or per-frame8B.',
    'dn_fragmented': 'Actual fragmentation selection unknown boolean; False enforces oneframe bounds, True permits complete messages exceeding8 only within known peer contract. No executed fragmentation/ACK proof.',
    'dn_fragmentation_source': 'Actual matched fragmentation/XID/count/ACK/state/timeout/encoding reference unknown; Wireshark decoder itself has unimplemented fragment handling and is not capacity certification.'
})
removed = {
    'qos_priority': 'CANidentifier/group/connection determine actual arbitration; genericPCP3 is notDeviceNet.',
    'sync_method': 'No universalPTP/NTP/gPTP DeviceNet clock synchronization.',
    'reserved_bandwidth_percent': 'No genericDeviceNet10percent reservation.',
    'retransmission_rate': 'Probabilistic generic retry rate is not CAN automatic data-link retransmission or CIP connection handling.',
    'retry_limit': 'Generic retry3 is not CAN error state and adaptation-specific connection retry.',
    'retransmission_delay_ms': 'Generic0ms retry timer is notDeviceNet fragment/ACK/watchdog or scanner timing.',
    'gateway_maximum_throughput': 'No universal100Mbit/s DeviceNetgateway; actual CANrate/route/conversion evidence separate.',
    'gateway_input_buffer': 'No universal256-frame DeviceNetgateway buffer.',
    'gateway_output_buffer': 'No universal256-frame DeviceNetgateway outputbuffer.',
    'gateway_maximum_routes': 'No universal10000-route DeviceNetgateway table.',
    'gateway_maximum_messages_s': 'No universal100000message/s DeviceNetgateway capacity.'
}
spec = {'technology': 'devicenet', 'native': native, 'removed': removed,
    'sources': ['https://jp.odva.org/wp-content/uploads/2020/05/PUB00026R4-Tech-Adv-Series-DeviceNet.pdf',
                'https://www.odva.org/wp-content/uploads/2023/05/PUB00027R1_Cable_Guide.pdf',
                'https://literature.rockwellautomation.com/idc/groups/literature/documents/um/dnet-um004_-en-p.pdf',
                'https://www.can-cia.org/can-knowledge/devicenet',
                'https://raw.githubusercontent.com/wireshark/wireshark/master/epan/dissectors/packet-devicenet.c',
                *can['sources'][:-1]],
    'revisions': ['ODVA PUB00026R4 March2016 pages3..5; PUB00027R1 cover2003 cable manual sections1/4/AppendixB',
                  'RockwellDNET-UM004E-EN-P March2022 pages19/chapters6/11; primaryDeviceNetdecoder accessed2026-10-01',
                  *can['source_revisions'][:-1]],
    'scope': 'DeviceNet own rates/identifiers/payload-fragment boundaries/connections/trunk-drop cable limits/electrical unknowns. Specified CAN CC link fields individually reviewed and adaptation constraints override its generic defaults. SQL rejected-edit retention.',
    'validation': {'isolated_sql': True, 'suite': 'full_parameter_audit + standard_defaults + profile_semantics + capacity_can_schedule + parameter_review + required_parameters', 'passed': 0},
    'not_certified': ['Complete licensed currentVolume3v1.16 and actual EDS/firmware/scan-list not supplied or verified',
                      'Actual duplicateMAC, CIP services/UCMM/Group2 state, fragmentation/ACK/watchdog and power/arbitration execution not certified',
                      'Mixed-cable aggregate budgets, peer exactheader encoding and DeviceNetofThings alternate identifier layout remain unverified',
                      'No registered complete DeviceNet capacity/physical model; MODEL_MISSING is preserved, CANsize estimates do not certify DeviceNet scheduling']}
(root/'work/devicenet-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

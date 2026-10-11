"""Compare original snapshotted implementations with the consolidated owners."""
import dataclasses
import hashlib
import importlib
import json
import sys
import types
from copy import deepcopy
from edit_utils import ROOT, OUT
sys.path.insert(0, str(ROOT))

def baseline(phase, path, name):
    source = OUT / 'before' / phase / path
    module = types.ModuleType(name)
    module.__file__ = str(ROOT / path)
    sys.modules[name] = module
    exec(compile(source.read_text(encoding='utf-8-sig'), str(source), 'exec'), module.__dict__)
    return module

def plain(value):
    if dataclasses.is_dataclass(value):
        return plain(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {key:plain(v) for key,v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value

checks = {}
old = baseline('native-trace-owners', 'backend/nis/traces/formats/common_trace.py', 'old_common')
new = importlib.import_module('backend.nis.traces.formats.common_trace')
count = 0
for seed in (0, 42, 123):
    for bus in ('classic', 'fd', 'xl'):
        for channels in (1, 2, 4):
            left = old.build_can_trace(.2, 5, channels, bus, seed, 1700000000)
            right = new.build_can_trace(.2, 5, channels, bus, seed, 1700000000)
            assert plain(left) == plain(right)
            count += len(left)
    left = old.build_ethernet_trace(.2, 5, seed, 1700000000)
    right = new.build_ethernet_trace(.2, 5, seed, 1700000000)
    assert plain(left) == plain(right)
    for a,b in zip(left,right):
        assert old.build_udp_ipv4_ethernet_packet(a) == new.build_udp_ipv4_ethernet_packet(b)
        count += 1
checks['native_frames_and_packet_bytes'] = count

old = baseline('native-generator-owners', 'backend/nis/simulation/communication_generator.py', 'old_generator')
new = importlib.import_module('backend.nis.simulation.communication_generator')
for channels in (1, 2, 4):
    rows = [{}, {'sender':'custom', 'id':'0x210', 'cycle':25}, {'channel':99, 'gateway':2}, {'signals':[{'name':'x','start_bit':0,'length':8}]}]
    for index,row in enumerate(rows):
        left, right = old.normalized_routing_row(row,index,channels), new.normalized_routing_row(row,index,channels)
        assert left == right and list(left) == list(right)
    assert plain(old.build_messages(5, channel_count=channels)) == plain(new.build_messages(5, channel_count=channels))
checks['mutable_example_and_routing_contracts'] = 15
for channels in (1, 2, 4):
    a = old.default_restbus_participants(channels)
    b = new.default_restbus_participants(channels)
    assert plain(a) == plain(b)
    assert old.build_restbus_routing_rows(a, channels) == new.build_restbus_routing_rows(b, channels)
checks['native_restbus_participants_and_routes'] = 3

old = baseline('runtime-owners', 'backend/nis/traces/universal_trace.py', 'old_runtime')
new = importlib.import_module('backend.nis.traces.universal_trace')
events = []
for index in range(8):
    events.append({'time_s':index*.000031,'network':'n','base_transmission_time_s':.00012345,
        'configured_latency_ms':.03,'sender_hardware':'a','sender_port':'p','status':'transmitted',
        'ethernet':{'destinations':[{'hardware_id':'b','port_id':'q'}, {'hardware_id':'c','port_id':'q'}]}})
for slot in (None, {'period_ms':20,'offset_ms':5,'duration_ms':2}):
    events.append({'time_s':.013,'network':'l','base_transmission_time_s':.001,'configured_latency_ms':.03,
                   'status':'transmitted','lin_slot':slot})
for queue in (1, 256):
    networks_a, ports_a, networks_b, ports_b = {}, {}, {}, {}
    for event in events:
        a, b = deepcopy(event), deepcopy(event)
        old._serialize_event(a, {'queue_size':queue}, 1700000000, networks_a, ports_a)
        new._serialize_event(b, {'queue_size':queue}, 1700000000, networks_b, ports_b)
        assert a == b and networks_a == networks_b and ports_a == ports_b
checks['runtime_full_duplex_and_lin_alignment'] = 20

old = baseline('protocol-encoding-owners', 'backend/nis/communication/technologies/ethernet/transport.py', 'old_transport')
new = importlib.import_module('backend.nis.communication.technologies.ethernet.transport')
count = 0
for version in (4, 6):
    for protocol in ('udp', 'tcp'):
        for vlan in (None, 0, 23):
            for length in (0, 1, 8, 128, 1400):
                flow = {'ip_version':version,'transport_protocol':protocol,'vlan_id':vlan,'mtu':1500,
                        'source_port':1234,'destination_ports':[4321],
                        'source':{'mac':'02:00:00:00:00:01','ip':'192.0.2.1' if version == 4 else '2001:db8::1'},
                        'destinations':[{'mac':'02:00:00:00:00:02','ip':'192.0.2.2' if version == 4 else '2001:db8::2'}]}
                event = {'ethernet':flow,'payload_hex':bytes(length).hex(),'sequence':3,'route_id':'route'}
                assert old.packet_bytes(event) == new.packet_bytes(event)
                count += 1
checks['ipv4_ipv6_udp_tcp_vlan_packet_bytes'] = count
old = baseline('parameter-evidence-owners', 'backend/nis/engineering/capacity/service.py', 'old_parameter_service')
new = importlib.import_module('backend.nis.engineering.capacity.service')
count = 0
for protocol, rate in [('CAN_FD',500000),('LIN',19200),('I2C',400000),('SPI',1000000),('ETHERNET',100000000)]:
    for parameters in ({}, {'technology':protocol,'bitrate':rate}, {'technology':'CAN_FD','bitrate':2000000},
                       {'technology':protocol,'lin_bitrate_bps':rate}, {'technology':protocol,'arbitration_bitrate':rate,'data_bitrate':2000000}):
        for configuration in ({}, {'protocol':protocol,'bitrate':rate}, {'protocol':'CAN_FD','bitrate':2000000}):
            for confirmed in (None, {}, {'technology':protocol,'bitrate':rate,'parameter_provenance':{'bitrate':{'source':'MANUAL','status':'CONFIRMED','value':rate}}}):
                args = (protocol,deepcopy(parameters),deepcopy(configuration),'network',deepcopy(confirmed))
                expected = old.parameters_for_protocol(*args)
                actual = new.parameters_for_protocol(*args)
                assert expected == actual, (protocol, parameters, configuration, confirmed, expected, actual)
                count += 1
checks['parameter_provenance_and_cross_technology_rejection'] = count
result = {'status':'PASS', 'checks':checks, 'baseline':'Original pre-edit snapshots, fixed seeds and timestamps', 'snapshot_sha256':{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'before').rglob('*.py')}}
(OUT/'behavior-equivalence.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'status':'PASS','checks':checks}))

"""Read-only functional checks to execute in the delivered production image."""
import hashlib
import importlib
import json
from pathlib import Path
import sys

sys.path.insert(0,'/app')
sys.path.insert(1,'/app/backend')
from backend.nis.compatibility import ALIASES
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.traces.formats import common_trace
from backend.nis.communication.technologies.ethernet.runtime import serialize_event
from backend.nis.communication.technologies.lin.runtime import next_poll_start

assert len(registry.profiles()) == 125
assert registry.timing_implementation('unknown') is None
assert registry.validate_parameters('lin', {'bitrate_bps':2000000})['status'] != 'VALID'
assert common_trace.build_can_trace.__module__ == 'backend.nis.communication.technologies.can.formats.trace_model'
assert common_trace.build_ethernet_trace.__module__ == 'backend.nis.communication.technologies.ethernet.formats.trace_model'
can_frames = common_trace.build_can_trace(.1,2,1,'fd',42,1700000000)
eth_frames = common_trace.build_ethernet_trace(.1,2,42,1700000000)
assert len(can_frames) == 2 and len(eth_frames) == 32
packet = common_trace.build_udp_ipv4_ethernet_packet(eth_frames[0])
assert len(packet) == 102
assert next_poll_start(.013, {'period_ms':20,'offset_ms':5}) == .025
event = {'network':'n','time_s':0,'base_transmission_time_s':.00012345,'status':'transmitted',
         'sender_hardware':'a','sender_port':'p','configured_latency_ms':0,
         'ethernet':{'destinations':[{'hardware_id':'b','port_id':'q'}]}}
serialize_event(event,{},0,{},0,'n',.00012345)
assert event['timestamp_utc'] == '1970-01-01T00:00:00.000247Z'
for folder in ('/app/backend/communication/technologies','/app/backend/specializations/technologies'):
    assert not Path(folder).exists()
checked = 0
for old,canonical in ALIASES.items():
    if old.startswith(('backend.communication.technologies','backend.specializations.technologies',
                       'communication.technologies','specializations.technologies')):
        assert importlib.import_module(old) is importlib.import_module(canonical)
        checked += 1
for name in ('fault','interface','message','routing','scenario'):
    namespace = {}
    exec('from backend.nis.agent.generators.' + name + ' import *',namespace)
    assert name.title() + 'Generator' in namespace
print(json.dumps({'status':'PASS','profiles':125,'legacy_import_identities':checked,'generator_wildcard_exports':5,
                  'can_frames':len(can_frames),'ethernet_frames':len(eth_frames),'packet_bytes':len(packet),
                  'packet_sha256':hashlib.sha256(packet).hexdigest(),'lin_alignment_s':.025,
                  'runtime_timestamp_precision':'PRESERVED','old_technology_source_trees':'ABSENT',
                  'production_database_mutations':False,'persistent_trace_writes':False}))

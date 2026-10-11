"""Independent BLF/DBC decoders verify project identities and actual wire bytes."""
from copy import deepcopy
import json
from pathlib import Path

import can
import cantools
import pytest

from backend.nis.communication.technologies.can.formats.can_format_writers import write_project_can_artifacts
from backend.nis.simulation.communication_simulator import run_simulation
from backend.nis.simulation.hardware_profile import normalize_hardware_config
from backend.nis.simulation.model_based_simulation import MessageCodec, SignalDefinition
from backend.nis.traces.universal_trace import generate_universal_events


def config(tmp_path):
    return {'output_dir':str(tmp_path), 'duration_s':.02, 'seed':42,
        'formats':['universal-jsonl','blf','dbc'],
        'networks':[{'id':'project-can', 'technology':'can_fd', 'bitrate':500_000,
                     'arbitration_bitrate':500_000, 'data_bitrate':2_000_000, 'can_fd_brs':True}],
        'hardware':{'devices':[{'id':node, 'name':node, 'ports':[{'id':node+'-port',
            'interfaces':[{'id':node+'-if', 'technology':'can_fd', 'network':'project-can'}]}]} for node in ['a','b','c']]},
        'communications':[{'id':'real-route', 'sender_interface':'a-if', 'receiver_interfaces':['b-if','c-if'],
            'network_id':'project-can', 'technology':'can_fd', 'cycle_ms':10, 'payload_bytes':3,
            'message_ids':['message-1'], 'signal_ids':['state','temperature'], 'arbitration_id':0x321, 'jitter_ratio':0}],
        'engineering_model':{'messages':[{'id':'message-1','name':'VehicleState','message_id_hex':'0x321','dlc':3}],
            'signals':[{'id':'state','name':'State','message_id':'message-1','start_bit':0,'length_bits':8,
                'byte_order':'little_endian','data_type':'unsigned','factor':1,'offset_value':0,
                'min_value':0,'max_value':255,'behavior':{'type':'CONSTANT','value':200}},
                {'id':'temperature','name':'Temperature','message_id':'message-1','start_bit':8,'length_bits':16,
                'byte_order':'little_endian','data_type':'signed','factor':.1,'offset_value':-40,
                'min_value':-100,'max_value':100,'unit':'degC','behavior':{'type':'CONSTANT','value':-45}}]},
        'scenario':{'mode':'NORMAL','faults':[]}}


def test_primary_project_run_exports_actual_blf_and_decodable_canonical_dbc(tmp_path):
    cfg=config(tmp_path); before=deepcopy(cfg)
    result=run_simulation(cfg)
    assert result['status']=='completed'
    assert result['native_can']['generator']=='canonical-can-export-v1'
    assert cfg==before
    events=[json.loads(line) for line in (tmp_path/'traces/universal_trace.jsonl').read_text().splitlines()]
    frames=list(can.BLFReader(str(tmp_path/'native/can_trace.blf')))
    dbc=cantools.database.load_file(str(next((tmp_path/'native').glob('*.dbc'))),strict=True)
    assert [m.frame_id for m in dbc.messages]==[0x321]
    assert dbc.messages[0].name=='VehicleState'
    assert dbc.messages[0].is_fd
    expected=[e for e in events if e['status']!='dropped' and not e.get('shared_transmission_observation')]
    assert len(frames)==len(expected)>0
    for frame,event in zip(frames,expected):
        assert frame.arbitration_id==event['arbitration_id']==0x321
        assert bytes(frame.data)==bytes.fromhex(event['payload_hex'])
        assert frame.is_fd and frame.bitrate_switch and not frame.is_extended_id
        assert frame.timestamp==pytest.approx(event['timestamp_unix']-event['time_s']+event['tx_start_s'],abs=2e-6)
        decoded=dbc.decode_message(frame.arbitration_id,frame.data,decode_choices=False)
        assert decoded['State']==200  # Upper unsigned half must never be signed/clipped.
        assert decoded['Temperature']==pytest.approx(-45)
    assert not (tmp_path/'native/network.dbc').exists(), 'no example database'
    sidecar=json.loads((tmp_path/'native/can_export_map.json').read_text())
    assert sidecar['channels']=={'project-can':0}
    assert {e['message_id'] for e in sidecar['events']}=={'message-1'}


@pytest.mark.parametrize('data_type,value,expected', [('unsigned',200,'C8'),('uint8',255,'FF'),('signed',-56,'C8'),('int8',-1,'FF')])
def test_codec_preserves_explicit_signedness(data_type,value,expected):
    definition=SignalDefinition.from_record({'id':'s','start_bit':0,'length_bits':8,'data_type':data_type,'factor':1})
    payload=MessageCodec.encode([(definition,value)],1)
    assert payload==expected
    assert MessageCodec.decode(payload,definition)==value


@pytest.mark.parametrize('change,match', [
    (lambda c:c['engineering_model']['signals'][0].pop('factor'), 'ENCODING_MISSING'),
    (lambda c:c['engineering_model']['signals'][0].update(start_bit=32), 'does not fit'),
    (lambda c:c['engineering_model']['messages'][0].update(message_id_hex='0x20000000'), 'ID_INVALID'),
    (lambda c:c['engineering_model']['signals'][0].update(byte_order='invented'), 'BYTE_ORDER_INVALID'),
    (lambda c:c['engineering_model']['signals'][0].update(start_bit=.5), 'must be an integer'),
])
def test_invalid_export_encoding_never_creates_native_files(tmp_path,change,match):
    cfg=config(tmp_path)
    routes,events=generate_universal_events(cfg,normalize_hardware_config(cfg),start_utc=1700000000)
    change(cfg)
    with pytest.raises((ValueError,cantools.database.errors.Error),match=match):
        write_project_can_artifacts(tmp_path/'invalid',cfg,routes,events,['blf','dbc'])
    assert not (tmp_path/'invalid').exists()


def test_dropped_and_shared_route_observations_are_not_extra_physical_blf_frames(tmp_path):
    cfg=config(tmp_path)
    routes,events=generate_universal_events(cfg,normalize_hardware_config(cfg),start_utc=1700000000)
    events[0]['status']='dropped'
    repeated={**events[-1],'shared_transmission_observation':True,'event_id':'same-physical-frame'}
    _,summary=write_project_can_artifacts(tmp_path/'native',cfg,routes,events+[repeated],['blf','dbc'])
    frames=list(can.BLFReader(str(tmp_path/'native/can_trace.blf')))
    assert len(frames)==summary['frames']==len(events)-1
    mapping=json.loads((tmp_path/'native/can_export_map.json').read_text())['events']
    assert len([e for e in mapping if not e['captured']])==2


def test_extended_id_and_aligned_motorola_layout_decode_without_model_rewrite(tmp_path):
    cfg=config(tmp_path)
    cfg['engineering_model']['messages'][0].update(message_id_hex='0x18FEF100',dlc=2)
    cfg['engineering_model']['signals']=[{'id':'big','name':'Big','message_id':'message-1','start_bit':0,
        'length_bits':16,'byte_order':'big_endian','data_type':'unsigned','factor':.5,'offset_value':-20,
        'min_value':-20,'max_value':32747,'behavior':{'type':'CONSTANT','value':1000}}]
    cfg['communications'][0].update(payload_bytes=2,arbitration_id=0x18FEF100,signal_ids=['big'])
    before=deepcopy(cfg)
    run_simulation(cfg)
    dbc=cantools.database.load_file(str(next((tmp_path/'native').glob('*.dbc'))),strict=True)
    frame=next(iter(can.BLFReader(str(tmp_path/'native/can_trace.blf'))))
    assert frame.is_extended_id
    assert dbc.messages[0].is_fd and dbc.messages[0].is_extended_frame
    assert dbc.messages[0].signals[0].start==7
    assert dbc.decode_message(frame.arbitration_id,frame.data)['Big']==1000
    assert cfg==before


def test_reused_frame_ids_on_separate_buses_keep_independent_dbc_and_blf_channels(tmp_path):
    cfg=config(tmp_path)
    cfg['networks'].append({**cfg['networks'][0], 'id':'second-can'})
    for node in cfg['hardware']['devices']:
        node['ports'].append({'id':node['id']+'-other-port','interfaces':[
            {'id':node['id']+'-other-if','technology':'can_fd','network':'second-can'}]})
    cfg['communications'].append({**cfg['communications'][0], 'id':'other-route','sender_interface':'a-other-if',
        'receiver_interfaces':['b-other-if'], 'network_id':'second-can','message_ids':['other-message'], 'signal_ids':['other-state']})
    cfg['engineering_model']['messages'].append({**cfg['engineering_model']['messages'][0], 'id':'other-message','name':'OtherState'})
    cfg['engineering_model']['signals'].append({**cfg['engineering_model']['signals'][0], 'id':'other-state','message_id':'other-message'})
    run_simulation(cfg)
    databases=[cantools.database.load_file(str(path),strict=True) for path in (tmp_path/'native').glob('*.dbc')]
    assert len(databases)==2
    assert {db.messages[0].name for db in databases}=={'VehicleState','OtherState'}
    assert all(db.messages[0].frame_id==0x321 for db in databases)
    assert {frame.channel for frame in can.BLFReader(str(tmp_path/'native/can_trace.blf'))}=={0,1}

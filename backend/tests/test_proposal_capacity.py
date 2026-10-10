from backend.tests.native_transport_fixtures import lin_design, ethernet_mac
from backend.nis.agent.tools import proposal_service as proposal_service
import pytest


def test_network_preview_reads_one_inventory_and_still_rejects_existing_identifier(monkeypatch):
    from backend.nis.agent.tools import validation
    reads = []
    monkeypatch.setattr(proposal_service, 'networks', lambda: reads.append(True) or [{'id': 'existing'}])
    monkeypatch.setattr(validation, 'validate_effective_model', lambda changes: [])
    changes = [{'object_type': 'Network', 'action': 'CREATE', 'local_ref': f'network-{index}',
                'data': {'id': 'existing' if index == 25 else f'new-{index}', 'technology': 'LIN'}}
               for index in range(50)]
    result = proposal_service._validate_changes(changes)
    assert len(reads) == 1
    assert not result['valid']
    assert [(finding['index'], finding['message']) for finding in result['findings']] == [(25, 'Netzwerk-ID bereits vorhanden.')]


@pytest.mark.parametrize('other_parent,duplicate', [('one', True), ('two', False)])
def test_effective_name_uniqueness_preserves_parent_scope_and_update_overlay(monkeypatch, other_parent, duplicate):
    from backend.nis.agent.tools import validation
    from backend.nis.workflow.services.service import WorkflowStatusService
    rows = {'HardwareNode': [{'id': identifier, 'name': identifier} for identifier in ('one', 'two')],
            'Interface': [{'id': 'a', 'name': 'Original', 'hardware_node_id': 'one', 'interface_type': 'CAN_FD'},
                          {'id': 'b', 'name': ' Status ', 'hardware_node_id': other_parent, 'interface_type': 'CAN_FD'}]}
    monkeypatch.setattr(validation, 'objects', lambda kind: rows.get(kind, []))
    monkeypatch.setattr(validation, 'networks', lambda: [])
    monkeypatch.setattr(WorkflowStatusService, 'get', lambda self: {'parameters': {}, 'context': {}})
    changes = [{'action': 'UPDATE', 'object_type': 'Interface', 'object_id': 'a', 'data': {'name': 'STATUS'}}]
    findings = validation.validate_effective_model(changes)
    duplicates = [finding for finding in findings if finding['message'] == 'Ein Objekt mit diesem Namen existiert bereits im gleichen Elternobjekt.']
    assert bool(duplicates) is duplicate
    # A deletion in the same effective graph removes the conflicting name.
    findings = validation.validate_effective_model([*changes, {'action': 'DELETE', 'object_type': 'Interface', 'object_id': 'b'}])
    assert not any(finding['message'] == 'Ein Objekt mit diesem Namen existiert bereits im gleichen Elternobjekt.' for finding in findings)
    assert rows['Interface'][0]['name'] == 'Original'


def test_bus_frame_reuse_retains_distinct_payloads_and_every_release(monkeypatch):
    from backend.nis.agent.tools import validation
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    parameters = registry.simulation_defaults_for_project({'technology': 'lin', 'defaults_source': 'technology-registry',
                    'networks': [{'id': 'bus', 'technology': 'lin'}]}, ['lin'])
    rows = {'HardwareNode': [], 'HardwareNetworkInterface': [{'id': 'port', 'technology': 'lin', 'network_ref': 'bus'}],
            'Message': [{'id': 'small', 'hardware_interface_id': 'port', 'dlc': 1, 'cycle_ms': 100},
                        {'id': 'large', 'hardware_interface_id': 'port', 'dlc': 8, 'cycle_ms': 50},
                        {'id': 'large-again', 'hardware_interface_id': 'port', 'dlc': 8, 'cycle_ms': 200}]}
    monkeypatch.setattr(validation, 'objects', lambda kind: rows[kind])
    check = validation.review_simulation_capacity({'parameters': parameters})[0]
    assert check['message_count'] == 3
    assert check['load_percent'] == pytest.approx((54 / .1 + 124 / .05 + 124 / .2) / 19200 * 100)
    assert check['status'] == 'FEASIBLE_UNDER_ASSUMPTIONS'


def test_inactive_saved_ethernet_link_is_highlighted_without_reconfirming_its_rate(monkeypatch):
    from backend.nis.agent.tools import validation
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    parameters = registry.simulation_defaults_for_project({'technology': 'ethernet',
        'networks': [{'id': 'bus', 'technology': 'ethernet', 'bitrate': 1_000_000_000,
            'parameter_provenance': {'bitrate': {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': 1_000_000_000}}}]}, ['ethernet'])
    rows = {'HardwareNode': [], 'HardwareNetworkInterface': [{'id': 'port', 'technology': 'ethernet', 'network_ref': 'bus'}],
            'Message': [{'id': 'message', 'hardware_interface_id': 'port', 'dlc': 4, 'cycle_ms': 100}]}
    monkeypatch.setattr(validation, 'objects', lambda kind: rows[kind])
    state = {'parameters': parameters}
    assert validation.review_simulation_capacity(state)[0]['status'] == 'FEASIBLE_UNDER_ASSUMPTIONS'
    assumed = parameters['simulation_parameter_assumptions']['ethernet']
    assumed['values']['eth_link_up'] = assumed['provenance']['eth_link_up']['value'] = False
    for _ in range(3):
        check = validation.review_simulation_capacity(state)[0]
        assert check['status'] == 'INVALID'
        assert check['parameter_fields'] == ['eth_link_up']
        assert check['rates']['bitrate'] == 1_000_000_000
        finding = next(row for row in validation.review_parameter_findings(state) if row['code'] == 'SIMULATION_CAPACITY_INVALID')
        assert finding['parameter_fields'] == ['eth_link_up']
        assert finding['severity'] == 'ERROR'
        assert assumed['values']['eth_link_up'] is False
    assumed['values']['eth_link_up'] = assumed['provenance']['eth_link_up']['value'] = True
    assert validation.review_simulation_capacity(state)[0]['status'] == 'FEASIBLE_UNDER_ASSUMPTIONS'
    assert all(row['code'] == 'CAPACITY_DEVICE_EVIDENCE_MISSING' for row in validation.review_parameter_findings(state))


def test_saved_rates_are_used_for_pending_and_canonical_bus_review_without_rate_confirmation_loop(monkeypatch):
    from backend.nis.agent.tools import validation
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    from copy import deepcopy
    rows={'HardwareNode':[],'HardwareNetworkInterface':[],'Message':[]}
    monkeypatch.setattr(validation,'objects',lambda kind:rows[kind])
    parameters=registry.simulation_defaults_for_project({'industry':'automotive','technology':'can_fd','defaults_source':'technology-registry','networks':[]},['lin','can_fd','ethernet'])
    changes=[]
    for technology in ('lin','can_fd','ethernet'):
        changes.extend([
            {'object_type':'Network','action':'CREATE','local_ref':'net-'+technology,'data':{'id':'bus-'+technology,'name':technology+' bus','technology':technology}},
            {'object_type':'HardwareNode','action':'CREATE','local_ref':'ecu-'+technology,'data':{'name':technology+' device'}},
            {'object_type':'HardwareNetworkInterface','action':'CREATE','local_ref':'port-'+technology,'data':{'hardware_node_id':'$ecu-'+technology,'technology':technology,'network_ref':'bus-'+technology,'bitrate':None}},
            {'object_type':'Message','action':'CREATE','local_ref':'m-'+technology,'data':{'hardware_interface_id':'$port-'+technology,'dlc':4,'cycle_ms':100}},
        ])
    state={'parameters':parameters}
    before=deepcopy(state)
    pending=validation.review_simulation_capacity(state,changes)
    assert len(pending)==3
    assert all(item['status']=='FEASIBLE_UNDER_ASSUMPTIONS' and item['load_percent']>0 for item in pending)
    findings=validation.review_parameter_findings(state,changes)
    assert len(findings)==3 and all(item['code']=='CAPACITY_DEVICE_EVIDENCE_MISSING' for item in findings)
    assert all(not any('bitrate' in field for field in item['parameter_fields']) for item in findings)
    assert all(not item['hardware_evidence'] for item in findings)
    assert len(validation.review_bus_rate_plans(state,changes))==3
    assert state==before
    for change in changes:
        row={**change['data'],'id':'$'+change['local_ref']}
        if change['object_type']=='Network': parameters['networks'].append(change['data'])
        else: rows[change['object_type']].append(row)
    assert validation.review_simulation_capacity(state)==pending


def test_missing_scenario_parameters_have_one_port_finding_without_duplicate_network_errors(monkeypatch):
    from backend.nis.agent.tools import validation
    rows = {'HardwareNode': [],
            'HardwareNetworkInterface': [{'id': 'port', 'technology': 'can_fd', 'network_ref': 'bus', 'bitrate': None}],
            'Message': [{'id': 'message', 'hardware_interface_id': 'port', 'dlc': 1, 'cycle_ms': 100}]}
    monkeypatch.setattr(validation, 'objects', lambda kind: rows[kind])
    state = {'parameters': {'technology': 'can_fd', 'defaults_source': 'technology-registry',
                            'networks': [{'id': 'bus', 'technology': 'can_fd'}]}}
    checks = validation.review_simulation_capacity(state)
    assert checks[0]['status'] == 'INVALID' and checks[0]['load_percent'] is None
    findings = validation.review_parameter_findings(state)
    assert len(findings) == 1 and findings[0]['code'] == 'CAPACITY_UNVERIFIED'
    assert findings[0]['severity'] == 'ERROR'
    assert set(findings[0]['parameter_fields']) == {'arbitration_bitrate', 'data_bitrate'}


def test_shared_bus_review_aggregates_publishers_without_duplicate_multicast_load(monkeypatch):
    from backend.nis.agent.tools import validation
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    parameters=registry.simulation_defaults_for_project({'technology':'lin','defaults_source':'technology-registry','networks':[{'id':'bus','technology':'lin'}]},['lin'])
    ports=[{'id':key,'hardware_node_id':key,'technology':'lin','network_ref':'bus','bitrate':None} for key in ('one','two')]
    messages=[{'id':key,'hardware_interface_id':key,'dlc':8,'cycle_ms':20} for key in ('one','two')]
    messages[0]['configuration']={'physical_transmit_bindings':[{'hardware_interface_id':'one','network_id':'bus'}]}
    rows={'HardwareNode':[],'HardwareNetworkInterface':ports,'Message':messages}
    monkeypatch.setattr(validation,'objects',lambda kind:rows[kind])
    state={'parameters':parameters}
    check=validation.review_simulation_capacity(state)[0]
    assert check['message_count']==2
    assert check['load_percent']==pytest.approx(2*124/19200/.02*100)
    assert check['status']=='OVERLOAD'
    assert any(item['code']=='SIMULATION_CAPACITY_OVERLOAD' for item in validation.review_parameter_findings(state))


def test_saved_network_rate_does_not_hide_contradictory_physical_port_rate(monkeypatch):
    from backend.nis.agent.tools import validation
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    p=registry.simulation_defaults_for_project({'technology':'lin','defaults_source':'technology-registry',
        'networks':[{'id':'bus','technology':'lin','lin_bitrate_bps':19200}]},['lin'])
    rows={'HardwareNode':[],'HardwareNetworkInterface':[{'id':'port','technology':'lin','network_ref':'bus','bitrate':9600}],
        'Message':[{'id':'m','hardware_interface_id':'port','dlc':1,'cycle_ms':100}]}
    monkeypatch.setattr(validation,'objects',lambda kind:rows[kind])
    check=validation.review_simulation_capacity({'parameters':p})[0]
    assert check['status']=='PARAMETER_CONFLICT' and check['load_percent'] is None
    assert 'lin_bitrate_bps' in check['parameter_fields']


@pytest.mark.parametrize('code, reviewable', [
    ('SIMULATION_CAPACITY_OVERLOAD', True),
    ('SIMULATION_CAPACITY_PARAMETER_CONFLICT', False),
])
def test_structural_review_keeps_capacity_repair_possible_without_hiding_conflicts(monkeypatch, code, reviewable):
    from backend.nis.agent.tools import validation
    finding = {'code': code, 'severity': 'ERROR', 'object_id': 'bus',
               'message': 'A capacity repair is required.', 'hardware_evidence': False}
    monkeypatch.setattr(validation, 'validate_effective_model', lambda changes: [finding])
    result = proposal_service._validate_changes([])
    assert result['valid'] is reviewable
    assert result['validation_scope'] == 'MODEL_STRUCTURE'
    assert result['findings'][0]['severity'] == ('OPEN' if reviewable else 'ERROR')
    if reviewable:
        assert result['capacity_status'] == 'UNVERIFIED'


@pytest.mark.parametrize('technology', ['I2C', 'ModbusRTU', 'ModbusTCP', 'SPI', 'GPIO', 'CAN_FD'])
def test_named_network_preserves_registered_technology(technology):
    from backend.nis.agent.tools.wizard_generation import _network_protocol
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    protocol = _network_protocol(technology)
    assert DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(protocol) == DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(technology)
    result = proposal_service._validate_changes([{
        'object_type': 'Network', 'action': 'CREATE', 'local_ref': 'network',
        'data': {'id': 'local-control', 'technology': protocol},
    }])
    assert result['valid'], result


def test_unknown_network_technology_is_not_accepted():
    result = proposal_service._validate_changes([{
        'object_type': 'Network', 'action': 'CREATE', 'local_ref': 'network',
        'data': {'id': 'local-control', 'technology': 'UnspecifiedBus'},
    }])
    assert not result['valid']
    assert any('Unbekannte Netzwerktechnologie' in finding['message'] for finding in result['findings'])


def test_wizard_scale_proposal_exceeds_the_old_2000_change_ceiling(monkeypatch):
    captured = {}

    def fake_create(payload):
        captured["payload"] = payload
        return {"proposal_id": "large-proposal"}

    def fake_write(proposal_id, contract, **_kwargs):
        return {"proposal_id": proposal_id, "changes": contract["changes"]}

    monkeypatch.setattr(proposal_service.legacy, "create_proposal", fake_create)
    monkeypatch.setattr(proposal_service, "_write", fake_write)
    changes = [
        {"object_type": "Network", "data": {"id": f"network-{index}", "technology": "CAN_FD"}}
        for index in range(3000)
    ]

    proposal = proposal_service.create("WIZARD_ENGINEERING_MODEL", changes, "large wizard model")

    assert len(proposal["changes"]) == 3000
    assert len(captured["payload"]["proposed_objects"]) == 3000

@pytest.mark.parametrize('technology,confirmed,network,expected', [
    ('LIN', {'technology': 'CAN', 'bitrate': 500000}, {}, True),
    ('LIN', {'technology': 'LIN', 'protocol': 'CAN', 'bitrate': 500000}, {}, True),
    ('LIN', {'technology': 'CAN', 'networks': [{'id': 'bus', 'technology': 'LIN', 'protocol': 'CAN', 'bitrate': 500000}]}, {}, True),
    ('LIN', {'technology': 'CAN', 'networks': [{'id': 'bus', 'technology': 'CAN', 'bitrate': 500000}]}, {}, True),
    ('LIN', {'technology': 'CAN', 'networks': [{'id': 'bus', 'technology': 'unknown', 'bitrate': 500000}]}, {}, True),
    ('LIN', {'technology': 'CAN', 'networks': [{'id': 'bus', 'technology': 'LIN', **lin_design(), 'bitrate': 19200}]}, {}, False),
    ('LIN', {}, {'technology': 'CAN', 'bitrate': 500000}, True),
    ('LIN', {}, {'technology': 'LIN', **lin_design(), 'bitrate': 19200}, False),
    ('CAN_FD', {'technology': 'CAN_FD', 'arbitration_bitrate': 500000}, {}, True),
    ('CAN_FD', {'technology': 'CAN_FD', 'arbitration_bitrate': 500000, 'data_bitrate': 2000000}, {}, False),
    ('Ethernet', {'technology': 'Ethernet', **ethernet_mac(), 'bitrate': 100000000}, {}, False),
])
def test_proposal_capacity_resolves_only_matching_confirmed_rates(monkeypatch, technology, confirmed, network, expected):
    from backend.nis.agent.tools import validation as validation
    from backend.nis.workflow.services.service import WorkflowStatusService
    node = {'id': 'ecu', 'name': 'Motor', 'device_type': 'ECU'}
    port = {'id': 'port', 'name': 'MotorPort', 'hardware_node_id': 'ecu', 'technology': technology, 'network_ref': 'bus', 'bitrate': None}
    message = {'id': 'message', 'name': 'Moment', 'interface_id': 'logical', 'hardware_interface_id': 'port', 'dlc': 1, 'cycle_ms': 100}
    logical = {'id': 'logical', 'hardware_node_id': 'ecu', 'interface_type': technology}
    rows = {'HardwareNode': [node], 'HardwareNetworkInterface': [port], 'Message': [message], 'Interface': [logical]}
    monkeypatch.setattr(validation, 'objects', lambda kind: rows.get(kind, []))
    monkeypatch.setattr(validation, 'networks', lambda: [{'id': 'bus', 'technology': technology, **network}])
    monkeypatch.setattr(WorkflowStatusService, 'get', lambda self: {'parameters': confirmed, 'context': {}})
    findings = validation.validate_effective_model([{'action': 'UPDATE', 'object_type': 'HardwareNetworkInterface', 'object_id': 'port', 'data': {}}])
    capacity = [finding for finding in findings if finding.get('code') == 'CAPACITY_UNVERIFIED']
    assert bool(capacity) is expected
    if expected:
        assert capacity[0]['object_name'] == 'MotorPort' and capacity[0]['node_name'] == 'Motor'
        assert capacity[0]['missing_fields'] and capacity[0]['repair_action'] == 'REVIEW_TECHNOLOGY_PARAMETERS'
        if technology == 'CAN_FD':
            assert capacity[0]['missing_fields'] == ['data_bitrate']


@pytest.mark.parametrize('technology,fields', [('LIN',['lin_bitrate_bps']),('CAN_FD',['arbitration_bitrate','data_bitrate']),('ETHERNET',['bitrate'])])
def test_current_parameter_review_uses_native_fields_and_ignores_proposal_history(monkeypatch, technology, fields):
    from backend.nis.agent.tools import validation
    port={'id':'port','hardware_node_id':'ecu','technology':technology,'network_ref':'local','name':'Local port','bitrate':None}
    rows={'HardwareNode':[{'id':'ecu','name':'Controller'}],'HardwareNetworkInterface':[port],
          'Message':[{'id':'message','hardware_interface_id':'port','dlc':1,'cycle_ms':100}]}
    monkeypatch.setattr(validation,'objects',lambda kind:rows[kind])
    state={'parameters':{'technology':'can_fd','defaults_source':'technology-registry','networks':[{'id':'local','name':'Local bus','technology':technology}],
                        'simulation_parameter_assumptions':{'can_fd':{'values':{'arbitration_bitrate':500000,'data_bitrate':2000000}}}}}
    from copy import deepcopy
    before=deepcopy(state)
    findings=validation.review_parameter_findings(state)
    assert findings and findings[0]['code']=='CAPACITY_UNVERIFIED'
    assert set(fields) <= set(findings[0]['parameter_fields'])
    if technology == 'LIN':
        assert 'lin_device_source' in findings[0]['parameter_fields']
        assert 'lin_schedule_source' in findings[0]['parameter_fields']
    assert findings[0]['network_id']=='local' and findings[0]['node_name']=='Controller'
    assert state==before


def test_current_parameter_review_disappears_only_after_matching_rate_confirmation(monkeypatch):
    from backend.nis.agent.tools import validation
    rows={'HardwareNode':[{'id':'ecu','name':'Controller'}],
          'HardwareNetworkInterface':[{'id':'port','hardware_node_id':'ecu','technology':'CAN_FD','network_ref':'bus','bitrate':None}],
          'Message':[{'id':'m','hardware_interface_id':'port','dlc':1,'cycle_ms':100}]}
    monkeypatch.setattr(validation,'objects',lambda kind:rows[kind])
    state={'parameters':{'technology':'can_fd','defaults_source':'technology-registry','networks':[{'id':'bus','technology':'CAN_FD'}]}}
    assert validation.review_parameter_findings(state)
    values={'arbitration_bitrate':500000,'data_bitrate':2000000}
    state['parameters']['technology_parameters']={'can_fd':{'values':values,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v} for k,v in values.items()}}}
    assert validation.review_parameter_findings(state)==[]
    state['parameters']['technology_parameters']['can_fd']['provenance']['data_bitrate']['value']=1000000
    assert validation.review_parameter_findings(state)[0]['parameter_fields']==['data_bitrate']


def test_native_review_shares_equal_port_inputs_but_retains_a_changed_clock(monkeypatch):
    from backend.nis.agent.tools import validation
    from backend.nis.engineering.capacity import service
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    parameters = registry.simulation_defaults_for_project({
        'technology':'lin', 'defaults_source':'technology-registry',
        'networks':[{'id':'bus','technology':'lin'}]}, ['lin'])
    ports = [{'id':f'port-{index}', 'hardware_node_id':f'node-{index}',
              'technology':'lin', 'network_ref':'bus', 'bitrate':None,
              'channel_index':index+1, 'controller_ref':f'controller-{index}',
              'physical_port_ref':f'connector-{index}', 'modified_at':str(index)} for index in range(20)]
    rows = {'HardwareNode':[], 'HardwareNetworkInterface':ports,
            'Message':[{'id':f'message-{index}', 'hardware_interface_id':port['id'],
                        'dlc':1, 'cycle_ms':100} for index,port in enumerate(ports)]}
    monkeypatch.setattr(validation,'objects',lambda kind:rows[kind])
    original = service.simulation_parameters_for_protocol
    calls = []
    def resolve(*args,**kwargs):
        calls.append(args)
        return original(*args,**kwargs)
    monkeypatch.setattr(service,'simulation_parameters_for_protocol',resolve)
    result = validation.review_simulation_capacity({'parameters':parameters})[0]
    assert len(calls)==1
    assert result['message_count']==20
    assert result['load_percent']==pytest.approx(20*54/19200/.1*100)
    assert result['status']=='FEASIBLE_UNDER_ASSUMPTIONS'
    assert result['hardware_evidence'] is False and result['functional_timing_accepted'] is False
    ports[-1]['bitrate']=9600
    calls.clear()
    changed = validation.review_simulation_capacity({'parameters':parameters})[0]
    assert len(calls)==2
    assert changed['message_count']==20
    assert changed['status']=='PARAMETER_CONFLICT' and changed['load_percent'] is None


@pytest.mark.parametrize('field,value',[
    ('lin_bitrate_bps',9600), ('bitrate',9600), ('data_bitrate',2000000),
    ('protocol','can_fd'), ('lin_device_source','different-device'),
    ('parameter_provenance',{'bitrate':{'source':'USER_CONFIRMED','status':'CONFIRMED','value':9600}}),
    ('capabilities',{'local_timing_evidence':{'device_id':'different-device','clock_hz':40000000}}),
    ('simulation_parameter_assumptions',{'lin':{'values':{'lin_bitrate_bps':9600}}}),
])
def test_native_resolution_key_preserves_clocks_evidence_identity_and_assumptions(field,value):
    from backend.nis.agent.tools.validation import _parameter_scope_key
    metadata = {}
    base = {'technology':'lin','id':'one','channel_index':1,'physical_port_ref':'connector-one'}
    key = _parameter_scope_key('lin','bus',base,metadata)
    assert key==_parameter_scope_key('lin','bus',{**base,'id':'two','channel_index':2,
        'physical_port_ref':'connector-two'},metadata)
    assert key!=_parameter_scope_key('lin','bus',{**base,field:value},metadata)
    assert key!=_parameter_scope_key('lin','another-bus',base,metadata)

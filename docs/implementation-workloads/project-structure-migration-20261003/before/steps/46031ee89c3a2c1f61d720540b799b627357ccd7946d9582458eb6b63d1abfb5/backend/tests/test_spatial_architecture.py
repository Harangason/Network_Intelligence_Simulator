"""Spatial identity is reusable beyond the automotive example."""
import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
import pytest

from backend.engineering.models import EngineeringValidationError
from backend.engineering.spatial_architecture import architecture_from, location_decision
from backend.engineering.spatial_zoning import node_zones, plan_zoning, spatial_assessment, zone_findings
from test_spatial_zoning import fixture, accept_pure


@pytest.mark.parametrize('name,zone', [('FrontLeftRotor', 'FL'), ('RearRightRotor', 'RR'),
    ('RotorVorneLinks', 'FL'), ('UpperRotor', 'UPPER'), ('LowerRotor', 'LOWER'),
    ('Motor1', 'UNKNOWN'), ('Motor4CCW', 'UNKNOWN'), ('FlightControl', 'UNKNOWN'),
    ('UpperFrontLeftRotor', 'UNKNOWN')])
def test_rotors_have_evidence_not_assumed_motor_numbering(name, zone):
    decision = location_decision(name)
    assert decision['zone_id'] == zone
    assert decision['status'] == ('UNRESOLVED' if zone == 'UNKNOWN' else 'DERIVED')


def test_drone_four_rotors_four_local_branches_and_unchanged_function():
    state, objects, routes = fixture(names=['FlightController', 'FrontLeftRotor', 'FrontRightRotor', 'RearLeftRotor', 'RearRightRotor'])
    state['parameters']['industry'] = 'aerospace'
    for net in state['parameters']['networks']: net.update(technology='CAN', bitrate=500000)
    for hw in objects['HardwareNetworkInterface']: hw.update(technology='CAN', bitrate=500000)
    for n in state['topology']['nodes']:
        for p in n['ports']: p['bus'] = 'can'
    for edge in state['topology']['edges']: edge['bus'] = 'can'
    for route in routes:
        for endpoint in [route['source'], *route['destinations']]: endpoint['protocol'] = 'CAN'
    plan = plan_zoning(state, objects, routes)
    assert {n['installation_zone'] for n in plan['networks']} == {'FL', 'FR', 'RL', 'RR'}
    assert len(plan['creations']) == 3
    assert all(r['destinations'][0]['node_id'] == '0' for r in plan['routes'])
    assert all(n['technology'] == 'CAN' and n['bitrate'] == 500000 for n in plan['networks'])
    new = accept_pure(state, objects, routes, plan)
    assert not zone_findings(new[0]['topology'], new[1]['HardwareNode'])
    assert not plan_zoning(*new)['changes']


def rooms():
    return {'reference_frame': 'Building-A', 'zones': [
        {'id': 'floor1', 'label': 'Etage 1'},
        {'id': 'floor1/room1', 'label': 'Raum 1', 'parent_id': 'floor1'},
        {'id': 'floor1/room2', 'label': 'Raum 2', 'parent_id': 'floor1'}],
        'assignments': {'FrontLeftSuspensionTravel': 'floor1/room1',
                        'FrontLeftDamperPosition': 'floor1/room1', 'RearRightSuspensionTravel': 'floor1/room2'}}


def test_hierarchical_rooms_share_engine_and_persist_evidence():
    state, objects, routes = fixture()
    state['parameters'].update(industry='building_automation', spatial_architecture=rooms())
    plan = plan_zoning(state, objects, routes)
    assert {n['installation_zone'] for n in plan['networks']} == {'floor1/room1', 'floor1/room2'}
    assert {d['status'] for d in plan['decisions'].values()} == {'CONFIRMED', 'UNRESOLVED'}
    state, objects, routes = accept_pure(state, objects, routes, plan)
    assert not plan_zoning(state, objects, routes)['changes']
    assert spatial_assessment(state, objects['HardwareNode'])['known_devices'] == 3
    assert objects['HardwareNode'][1]['identity']['spatial_decision']['reference_frame'] == 'Building-A'


def test_functional_owner_does_not_establish_colocation_or_room():
    state, objects, _ = fixture(names=['FrontLeftRobotArm', 'Motor1', 'Motor2', 'Motor3'])
    zones, _ = node_zones(state['topology'], objects['HardwareNode'])
    assert zones == {'0': 'FL', '1': 'UNKNOWN', '2': 'UNKNOWN', '3': 'UNKNOWN'}
    assert location_decision('FrontLeftMotor', architecture=architecture_from({'spatial_architecture': rooms()}))['zone_id'] == 'UNKNOWN'


@pytest.mark.parametrize('broken', [
    {'zones': [{'id': 'room1', 'label': 'Raum'}]},
    {'reference_frame': 'A', 'zones': [{'id': 'a', 'label': 'A', 'parent_id': 'b'}, {'id': 'b', 'label': 'B', 'parent_id': 'a'}]},
    {'reference_frame': 'A', 'zones': [{'id': 'a', 'label': 'A', 'parent_id': 'missing'}]},
    {'assignments': {'Motor1': 'nonexistent'}}, {'assignments': {'Motor1': {'zone': 'FL'}}},
    {'assignments': {'Motor1': 'FL', 'motor1': 'FR'}}])
def test_invalid_spatial_contract_rejected(broken):
    with pytest.raises(EngineeringValidationError): architecture_from({'spatial_architecture': broken})


def test_confirmed_assignment_and_reference_frame_conflicts_are_not_overwritten():
    architecture = architecture_from({'spatial_architecture': {'reference_frame': 'drone-body', 'assignments': {'Motor1': 'FR'}}})
    with pytest.raises(EngineeringValidationError, match='widerspricht'):
        location_decision('Motor1', {'installation_zone': 'FL'}, architecture=architecture)
    with pytest.raises(EngineeringValidationError, match='Bezugsrahmen'):
        location_decision('Motor1', {'installation_zone': 'FR', 'installation_reference_frame': 'another-drone'}, architecture=architecture)


def test_declared_shared_backbone_is_not_forced_into_separate_local_buses():
    state, objects, routes = fixture()
    state['parameters']['networks'][0]['spatial_scope'] = 'backbone'
    plan = plan_zoning(state, objects, routes)
    assert not plan['creations'] and not plan['divisions'] and not plan['routes']
    assert not zone_findings(state['topology'], objects['HardwareNode'], parameters=state['parameters'])


def test_wizard_applies_explicit_motor_mapping_before_building_bus_ids():
    from backend.engineering.agent_tools.wizard_generation import _confirmed_local_io_memberships, _local_io_physical_network
    graph = [{'bus_name': 'Drone', 'controllers': [{'ecu': 'FlightController', 'actuators': ['Motor1', 'Motor2', 'Motor3', 'Motor4']}]}]
    architecture = {'reference_frame': 'drone-body', 'assignments': dict(zip(['Motor1', 'Motor2', 'Motor3', 'Motor4'], ['FR', 'RL', 'FL', 'RR']))}
    prompt = '- Projekt-Modelltyp: aerospace\n- Systemcluster-Graph: '+json.dumps(graph)+'\n- Raumarchitektur: '+json.dumps(architecture)
    members = _confirmed_local_io_memberships(prompt, {f'motor{i}': 'can' for i in range(1,5)})
    networks = [_local_io_physical_network('can', members, {'name': f'Motor{i}'}, {'name': 'FlightController'}) for i in range(1,5)]
    assert len({network[0] for network in networks}) == 4
    assert 'VR' in networks[0][1] and 'HL' in networks[1][1]


def test_spatial_tools_stay_available_even_with_large_tool_selection():
    from backend.agent_core.orchestration.tool_selection import select_tools
    from backend.engineering.agent_tools.services import TOOLS
    selected = select_tools('Drohne Raumcluster Hardware Signal Nachricht Routing Netz CAN Simulation Trace', [{'name': name} for name in TOOLS])
    assert selected[0]['name'] == 'inspect_spatial_architecture'


def test_spatial_reasoning_receives_rules_and_main_model(monkeypatch):
    from backend.agent_core.orchestration.local_reasoner import LocalEngineeringReasoner
    from backend.agent_core.context.agent_context import AgentContext
    monkeypatch.setenv('LOCAL_AI_MODEL', 'main-test-model')
    monkeypatch.setenv('LOCAL_AI_FAST_MODEL', 'fast-test-model')
    captured = {}
    async def run():
        reasoner = LocalEngineeringReasoner()
        async def post(url, json):
            captured.update(json)
            return SimpleNamespace(is_error=False, json=lambda: {'message': {'content': 'Positionen prüfen.'}})
        reasoner.client.post = post
        try:
            await reasoner.next([{'role': 'user', 'content': 'Raumcluster einer Drohne mit 4 Rotoren prüfen'}], AgentContext(active_project_id='test'), [])
        finally: await reasoner.close()
    asyncio.run(run())
    assert captured['model'] == 'main-test-model'
    assert 'inspect_spatial_architecture' in captured['messages'][0]['content']
    assert 'Motor 1–4' in captured['messages'][0]['content']


def test_saved_spatial_contract_reaches_wizard_and_conflicts_are_rejected():
    from backend.engineering.spatial_architecture import with_spatial_architecture
    parameters = {'spatial_architecture': rooms()}
    prompt = with_spatial_architecture('Create building network', parameters)
    assert architecture_from(prompt=prompt) == architecture_from(parameters)
    assert with_spatial_architecture(prompt, parameters) == prompt
    with pytest.raises(EngineeringValidationError, match='widerspricht'):
        architecture_from(parameters, '- Raumarchitektur: '+json.dumps({'reference_frame': 'Other-building'}))
    with pytest.raises(EngineeringValidationError, match='JSON'):
        architecture_from(prompt='- Raumarchitektur: invalid-json')


def test_partial_parameter_edits_keep_spatial_definition():
    from uuid import uuid4
    from backend.engineering.agent_tools.runtime import ToolAuthority, execute
    from backend.agent_core.api.tool_contract import Permission
    from backend.engineering.workflow.service import WorkflowStatusService
    authority = ToolAuthority('pytest-spatial-parameters-'+str(uuid4()))
    def edit(_):
        workflow = WorkflowStatusService(authority.project_id)
        workflow.save_parameters({'spatial_architecture': rooms(), 'spatial_zoning': {'enabled': True}})
        saved = workflow.save_parameters({'target_bus_load_percent': 55})
        assert saved['parameters']['spatial_architecture'] == architecture_from({'spatial_architecture': rooms()})
        assert saved['parameters']['spatial_zoning']['enabled']
        return True
    assert execute(authority, 'test_spatial_parameters', Permission.READ_MODEL, {}, edit).success

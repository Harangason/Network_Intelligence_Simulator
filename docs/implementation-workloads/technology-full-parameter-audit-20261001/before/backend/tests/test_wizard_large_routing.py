"""The captured complete wizard graph, without post-generation fixture repairs."""
import json
import re
from pathlib import Path
from uuid import uuid4

from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.agent_tools import model, proposal_service, wizard_generation
from backend.engineering.capacity.service import CapacityTimingService
from backend.engineering.physical_ports import topology_port_findings
from backend.engineering.workflow.service import WorkflowStatusService


def test_full_captured_model_and_all_routing_validate_without_rewriting_inputs():
    prompt = (Path(__file__).resolve().parents[2] / 'frontend/e2e/fixtures/wizard-large-50-250-250.txt').read_text(encoding='utf-8')
    authority = ToolAuthority('pytest-wizard-full-routing-' + str(uuid4()))

    def call(name, function):
        result = execute(authority, name, Permission.GENERATE_PROPOSAL, {}, lambda _: function())
        assert result.success, result.model_dump()
        return result.data

    call('persist_confirmed_wizard_request', lambda: WorkflowStatusService(authority.project_id).set_context({
        'agent_wizard_status': {'agent_prompt': prompt},
    }))
    proposal = call('generate_full_model', lambda: wizard_generation.generate({'prompt': prompt}))
    checked = call('validate_full_model', lambda: proposal_service.validate(proposal['proposal_id']))
    assert checked['validation_result']['valid'], json.dumps(checked['validation_result'], default=str)
    approved = call('review_full_model', lambda: proposal_service.review(proposal['proposal_id'],
        revision=checked['revision'], decision='approve', actor='isolated-test-review', trace_id=str(uuid4())))
    call('apply_full_model', lambda: proposal_service.apply(approved['proposal_id'], actor='isolated-test-review', trace_id=str(uuid4())))
    hardware = call('read_complete_hardware', lambda: model.objects('HardwareNode'))
    assert len(hardware) == 552
    assert sum(item['device_type'] == 'SensorController' for item in hardware) == 250
    assert sum(item['device_type'] == 'ActuatorController' for item in hardware) == 250
    before = call('source_revision', model.model_revision)
    routing = call('generate_full_routing', lambda: wizard_generation.generate_routing({'prompt': prompt}))
    checked_routing = call('validate_full_routing', lambda: proposal_service.validate(routing['proposal_id']))
    assert checked_routing['validation_result']['valid'], json.dumps(checked_routing['validation_result'], default=str)
    from collections import Counter
    hardware_types = {str(item['id']): item['device_type'] for item in hardware}
    graph_line = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])$', prompt, re.M)
    assert graph_line is not None
    graph = json.loads(graph_line.group(1))
    assert sum(bool(route.get('signals')) for cluster in graph
               for route in cluster.get('hmi_routes') or []) == 15
    route_roles = Counter()
    for change in routing['changes']:
        route = change['data']
        source_role = hardware_types.get(str((route.get('source') or {}).get('node_id')), '?')
        for destination in route.get('destinations') or []:
            route_roles[(source_role, hardware_types.get(str(destination.get('node_id')), '?'))] += 1
    # The captured graph explicitly enables only 15 HMI deliveries; its
    # excluded signals must not revive older implicit monitoring recipients.
    # Check each communication role so a smaller count cannot hide missing
    # sensor values, actuator commands, or actuator feedback.
    assert route_roles == Counter({
        ('SensorController', 'ECU'): 250,
        ('ECU', 'ActuatorController'): 250,
        ('ActuatorController', 'ECU'): 250,
        ('ECU', 'ECU'): 16,
    })
    assert before == call('unchanged_source_revision', model.model_revision)
    resumed = call('resume_same_routing', lambda: wizard_generation.generate_routing({
        'prompt': prompt + '\nFortsetzung des bestätigten Wizard-Auftrags:\nBitte weiter prüfen.'}))
    assert resumed['proposal_id'] == routing['proposal_id']

    def approve_apply(proposal):
        checked = proposal_service.validate(proposal['proposal_id'])
        assert checked['validation_result']['valid'], json.dumps(checked['validation_result'], default=str)
        approved = proposal_service.review(checked['proposal_id'], revision=checked['revision'],
            decision='approve', actor='isolated-test-review', trace_id=str(uuid4()))
        return proposal_service.apply(approved['proposal_id'], actor='isolated-test-review', trace_id=str(uuid4()))

    call('apply_all_routes', lambda: approve_apply(routing))
    topology = call('generate_complete_topology', lambda: wizard_generation.generate_network_topology({'prompt': prompt}))
    call('apply_complete_topology', lambda: approve_apply(topology))
    call('complete_registry_parameters', lambda: wizard_generation.generate_parameters({'prompt': prompt}))
    call('calculate_full_capacity', lambda: CapacityTimingService(authority.project_id).calculate(persist=True))
    before_repair = call('canonical_before_capacity_repair', model.model_revision)
    signal_encoding = call('signal_encoding_before_capacity_repair', lambda: model.objects('Signal'))
    message_frames = call('message_frames_before_capacity_repair', lambda: {
        item['id']: {key: item.get(key) for key in ('dlc', 'cycle_ms', 'message_id_hex', 'direction')}
        for item in model.objects('Message')})
    repair = call('generate_full_capacity_repair', lambda: wizard_generation.generate_capacity_network_repair({'prompt': prompt}))
    channels = [change for change in repair['changes'] if change['object_type'] == 'HardwareNetworkInterface'
                and change['action'] == 'CREATE']
    assert len(channels) > 100, 'The complete split must exercise shared source/recipient channels.'
    signatures = [(change['data']['hardware_node_id'], change['data']['name'].casefold()) for change in channels]
    assert len(signatures) == len(set(signatures))
    assert call('capacity_preview_did_not_write_model', model.model_revision) == before_repair
    call('apply_full_capacity_repair', lambda: approve_apply(repair))

    def verify_capacity_repair():
        state = WorkflowStatusService(authority.project_id).get()
        assert not topology_port_findings(state['topology'], model.objects('HardwareNode'), model.objects('HardwareNetworkInterface'))
        assert all(not port['hardwareInterfaceId'].startswith('$')
                   for node in state['topology']['nodes'] for port in node['ports'])
        assert model.objects('Signal') == signal_encoding, 'Adding channels must not change any signal encoding.'
        assert {item['id']: {key: item.get(key) for key in ('dlc', 'cycle_ms', 'message_id_hex', 'direction')}
                for item in model.objects('Message')} == message_frames
        result = CapacityTimingService(authority.project_id).calculate(persist=False)
        errors = [item for item in result['findings'] if item.get('severity') == 'ERROR']
        assert result['status'] != 'ERROR', json.dumps(errors, default=str)
        assert result['results']['overview']['capacity_verified'] is True
        assert not any(item['code'] == 'CAPACITY_RATE_UNVERIFIED' for item in result['findings'])
        assert any(item['code'] == 'LIN_SCHEDULE_RESERVE_UNMET' and item['severity'] == 'WARNING' for item in result['findings'])
        return result
    call('verify_full_capacity_repair', verify_capacity_repair)

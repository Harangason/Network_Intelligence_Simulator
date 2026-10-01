from uuid import uuid4
import json
from pathlib import Path

from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools import project_draft
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.agent_tools.wizard_commands import WizardCommand, resolve_request
from backend.engineering.agent_tools.wizard_generation import extract_specification


def test_multi_interface_controller_preserves_endpoint_connections():
    authority = ToolAuthority('multi-interface-draft-' + uuid4().hex)
    def call(data, handler):
        return execute(authority, 'multi-interface-test', Permission.GENERATE_PROPOSAL, data, handler)
    created = call({'action': 'CREATE', 'operation_id': uuid4().hex,
                    'requirement': 'Raspberry Pi mit drei Temperatursensoren'}, project_draft.command)
    draft = created.data['draft']
    owner = next(d for d in draft['devices'] if d['role'] == 'CONTROLLER')
    sensors = [d for d in draft['devices'] if d['role'] == 'SENSOR']
    updates = [{'device_id': owner['id'], 'technologies': ['SPI', 'I2C', 'GPIO']}]
    updates += [{'device_id': d['id'], 'technology': tech, 'owner_id': owner['id']}
                for d, tech in zip(sensors, ['SPI', 'I2C', 'GPIO'])]
    resolved = call({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 1,
                     'allow_simulation_defaults': True, 'devices': updates}, project_draft.command)
    assert resolved.success, resolved.findings
    draft = resolved.data['draft']
    assert not draft['issues']
    controller = next(d for d in draft['devices'] if d['id'] == owner['id'])
    assert len(controller['technologies']) == 3
    prompt = project_draft.planning_prompt(draft)
    specification = extract_specification(prompt)
    actual = {c['hardware_name']: c['interface_type'] for c in specification['chains']}
    assert [actual[d['name']] for d in sensors] == ['SPI', 'I2C', 'GPIO']
    # A later primary-interface edit cannot silently retain contradictory capabilities.
    rejected = call({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 2,
        'devices': [{'device_id': owner['id'], 'technology': 'CAN_FD', 'technologies': ['SPI']}]}, project_draft.command)
    assert not rejected.success

    rejected_primary = call({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 2,
        'devices': [{'device_id': owner['id'], 'technology': 'CAN_FD'}]}, project_draft.command)
    assert not rejected_primary.success
    unchanged = call({}, project_draft.inspect)
    current_owner = next(d for d in unchanged.data['devices'] if d['id'] == owner['id'])
    assert current_owner['technologies'] == controller['technologies']
    assert current_owner['technology'] == controller['technology']


def test_s01_explicit_sensor_contracts_survive_draft_adapter():
    authority = ToolAuthority('s01-draft-' + uuid4().hex)
    prompt = json.loads((Path(__file__).resolve().parents[2] / 'tests/fixtures/industry60-intake-regressions.json').read_text(encoding='utf8'))['S01-A']
    created = execute(authority, 's01-create', Permission.GENERATE_PROPOSAL,
        {'action': 'CREATE', 'operation_id': uuid4().hex, 'requirement': prompt}, project_draft.command)
    assert created.success, created.findings
    draft = created.data['draft']
    owner = next(d for d in draft['devices'] if d['role'] == 'CONTROLLER')
    updates = [{'device_id': owner['id'], 'technologies': ['SPI', 'I2C', 'GPIO', 'PWM', 'CAN_FD']}]
    for device in draft['devices']:
        if device['role'] == 'CONTROLLER':
            continue
        update = {'device_id': device['id'], 'owner_id': owner['id']}
        if device['role'] == 'ACTUATOR':
            relay, motor = 'relais' in device['name'].lower(), 'motor' in device['name'].lower()
            maximum = 1 if relay else 6000 if motor else 100
            update['command'] = {'length_bits': 1 if relay else 13 if motor else 7,
                'data_type': 'boolean' if relay else 'unsigned', 'unit': 'code' if relay else 'rpm' if motor else '%',
                'factor': 1, 'min_value': 0, 'max_value': maximum,
                'semantic': {'semantic_type': 'BOOLEAN' if relay else 'NUMERIC'},
                'data': {'enum_values': {'OFF': 0, 'ON': 1}} if relay else {'minimum': 0, 'maximum': maximum, 'resolution': 1}}
            if relay:
                update['technology'] = 'GPIO'
        updates.append(update)
    resolved = execute(authority, 's01-resolve', Permission.GENERATE_PROPOSAL,
        {'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': draft['revision'],
         'allow_simulation_defaults': True, 'devices': updates}, project_draft.command)
    assert resolved.success, resolved.findings
    draft = resolved.data['draft']
    assert not draft['issues']
    specification = extract_specification(project_draft.planning_prompt(draft))
    chains = {c['hardware_name']: c for c in specification['chains']}
    temperature = next(c for name, c in chains.items() if 'PT100' in name)
    pressure = next(c for name, c in chains.items() if 'Druck' in name)
    assert (temperature['min_value'], temperature['max_value'], temperature['factor'], temperature['cycle_ms']) == (-20, 150, .1, 100)
    assert (pressure['min_value'], pressure['max_value'], pressure['factor'], pressure['cycle_ms']) == (0, 10, .01, 20)
    planned = execute(authority, 's01-plan', Permission.GENERATE_PROPOSAL,
        {'draft_id': draft['draft_id'], 'revision': draft['revision']}, project_draft.plan_model)
    assert planned.success, planned.findings
    assert planned.data['validation_result']['valid'], planned.data['validation_result']['findings']
    function_names = {change['data']['name'] for change in planned.data['changes']
                      if change['object_type'] == 'Function'}
    assert {'TemperatureMonitoring', 'PressureControl', 'SpeedControl', 'SafetyShutdown'} <= function_names
    from backend.engineering.agent_tools import proposal_service, wizard_generation
    proposal = planned.data
    def accept(_):
        proposal_service.review(proposal['proposal_id'], revision=proposal['revision'],
            decision='approve', actor='isolated-test-review', trace_id=uuid4().hex)
        return proposal_service.apply(proposal['proposal_id'], actor='isolated-test-review', trace_id=uuid4().hex)
    applier = ToolAuthority(authority.project_id, 'isolated-test-review', authority.permissions | {Permission.APPLY_APPROVED_PROPOSAL})
    applied = execute(applier, 's01-test-review-apply', Permission.APPLY_APPROVED_PROPOSAL, {}, accept)
    assert applied.success, applied.findings
    routed = execute(authority, 's01-routing', Permission.GENERATE_PROPOSAL,
        {'prompt': project_draft.planning_prompt(draft)}, wizard_generation.generate_routing)
    assert routed.success, routed.findings
    validated = execute(authority, 's01-routing-validation', Permission.VALIDATE, {},
        lambda _: proposal_service.validate(routed.data['proposal_id']))
    assert validated.success, validated.findings
    assert validated.data['validation_result']['valid'], validated.data['validation_result']['findings']
    proposal = validated.data
    assert execute(applier, 's01-test-route-review-apply', Permission.APPLY_APPROVED_PROPOSAL, {}, accept).success
    topology = execute(authority, 's01-topology', Permission.GENERATE_PROPOSAL,
        {'prompt': project_draft.planning_prompt(draft)}, wizard_generation.generate_network_topology)
    assert topology.success, topology.findings
    validated_topology = execute(authority, 's01-topology-validation', Permission.VALIDATE, {},
        lambda _: proposal_service.validate(topology.data['proposal_id']))
    assert validated_topology.success, validated_topology.findings
    assert validated_topology.data['validation_result']['valid'], validated_topology.data['validation_result']['findings']
    proposal = validated_topology.data
    applied_topology = execute(applier, 's01-test-topology-apply', Permission.APPLY_APPROVED_PROPOSAL, {}, accept)
    assert applied_topology.success, applied_topology.findings
    from backend.engineering.capacity.service import CapacityTimingService
    capacity = execute(authority, 's01-capacity', Permission.VALIDATE, {},
        lambda _: CapacityTimingService(authority.project_id).calculate())
    assert capacity.success, capacity.findings


def test_chat_and_wizard_share_inventory_and_stale_start_is_rejected():
    authority = ToolAuthority('shared-draft-' + uuid4().hex)
    def call(data, handler):
        return execute(authority, 'shared-draft-test', Permission.GENERATE_PROPOSAL, data, handler)
    created = call({'action': 'CREATE', 'operation_id': uuid4().hex,
                    'requirement': 'Raspberry Pi mit drei Temperatursensoren'}, project_draft.command)
    draft = created.data['draft']
    owner = next(d for d in draft['devices'] if d['role'] == 'CONTROLLER')
    resolved = call({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 1,
                     'allow_simulation_defaults': True,
                     'devices': [{'device_id': d['id'], 'technology': 'ethernet',
                                  **({'owner_id': owner['id']} if d['role'] == 'SENSOR' else {})} for d in draft['devices']]}, project_draft.command)
    assert resolved.success, resolved.findings
    draft = resolved.data['draft']
    run = uuid4().hex
    arguments = {'draft_id': draft['draft_id'], 'revision': 2, 'run_id': run,
                 'scope_ids': ['engineering_model'], 'project_name': 'Temperaturregelung'}
    prepared = call(arguments, project_draft.workflow_request)
    assert prepared.success, prepared.findings
    payload = prepared.data
    direct = extract_specification(project_draft.planning_prompt(draft))
    wizard = extract_specification(payload['prompt'])
    assert wizard['targetCounts'] == direct['targetCounts']
    assert wizard['chains'] == direct['chains']
    command = WizardCommand(action='START', run_id=run, operation_id=uuid4().hex,
                            target=payload['target'], wizard_context=payload['context'])
    started = call({}, lambda _: resolve_request(command, payload['prompt'], {}, authority.project_id))
    assert started.success, started.findings
    forged = call({}, lambda _: resolve_request(command, payload['prompt'].replace('ethernet', 'CAN_FD'), {}, authority.project_id))
    assert not forged.success
    assert call({'action': 'AMEND', 'operation_id': uuid4().hex, 'revision': 2,
                 'requirement': 'Die Regelungsaufgabe wird noch präzisiert.'}, project_draft.command).success
    assert not call({}, lambda _: resolve_request(command, payload['prompt'], {}, authority.project_id)).success

"""Real isolated canonical writes from a mocked reviewed plan; no Qwen/E2E claim."""
from uuid import uuid4

from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.nis.agent.tools import project_draft, proposal_service, wizard_generation, model
from backend.nis.agent.tools.runtime import ToolAuthority, execute
from backend.tests.test_reference_design import fixture_request, wire
from backend.tests.test_reference_reasoner import complete_design
from backend.tests.test_reference_design_integration import marker


def test_accepted_reference_model_survives_normal_validation_review_apply(monkeypatch):
    """Keep full facts, real recipients, local dependencies, ports and assumption role."""
    async def local_unit_fixture(_self, prepared):
        plan = complete_design(prepared)
        ids = {fact['name']: key for key, fact in prepared['facts'].items()}
        for row in plan['functions']:
            if row['source_fact_id'] == ids['Gesamtfunktion']:
                row.update(realization='COMPOSITE', executor_device_ids=[],
                           realized_by_fact_ids=[ids['Regelung'], ids['Diagnose']])
        for row in plan['communication']:
            if row['role'] == 'COMMAND':
                row.update(producer_fact_id=ids['Regelung'], transmission_mode='CYCLIC', cycle_ms=50)
                for field in ('request_source', 'request_communication_id', 'response_processing_ms', 'min_interval_ms'):
                    row.pop(field, None)
            elif row['role'] == 'MEASUREMENT':
                row['consumer_fact_ids'] = [ids['Regelung']]
        plan['functional_dependencies'] = [{'id': 'control-diagnostic', 'producer_fact_id': ids['Regelung'],
            'consumer_fact_ids': [ids['Diagnose']], 'executor_device_id': 'C', 'signal_name': 'ControlDiagnostic',
            'encoding': wire(), 'rationale': 'Local explicit test dependency'}]
        # Explicit status contract, never a generator-invented default recipient.
        status = {'length_bits': 4, 'data_type': 'unsigned', 'unit': 'code', 'factor': 1,
            'min_value': 0, 'max_value': 15, 'semantic': {'semantic_type': 'STATE', 'meaning': 'Controller state'},
            'data': {'enum_values': {'OFF': 0, 'INIT': 1, 'READY': 2, 'ACTIVE': 3, 'DEGRADED': 4, 'ERROR': 5},
                     'invalid_raw': [15], 'reserved_raw': list(range(6, 15)), 'default_value': 0}}
        plan['communication'].append({'id': 'state', 'producer_device_id': 'C', 'consumer_device_ids': ['A'],
            'producer_fact_id': ids['Diagnose'], 'source_port_id': 'PC', 'consumer_port_ids': ['PA'],
            'scope': 'LOCAL_IO', 'role': 'STATUS', 'signal_name': 'ControllerState', 'encoding': status,
            'transmission_mode': 'CYCLIC', 'cycle_ms': 100, 'rationale': 'Explicit test state recipient'})
        # Distinct receive-only Ethernet port exercises the public CORE bitrate alias.
        plan['ports'].append({'id': 'BACKBONE', 'device_id': 'C', 'technology': 'ethernet', 'role': 'BACKBONE',
            'network_scope': 'backbone', 'parameters': {'bitrate': 1000000000}, 'rationale': 'Explicit example assumption'})
        return intake.validate_reference_design(plan, prepared)

    monkeypatch.setattr(LocalEngineeringReasoner, 'plan_reference_design', local_unit_fixture)
    authority = ToolAuthority('reference-model-' + uuid4().hex, 'test-human')
    request = fixture_request()
    request.update(source_request_id=uuid4().hex)
    request['prompt'] = ('- Projekt-Modelltyp: embedded_systems\n- Industrie: Embedded Systems\n'
                         '- Netzwerktechnologien: CAN (can), Ethernet (ethernet)\n- Systemcluster-Graph: []\n'
                         + request['prompt'])
    def call(name, handler, arguments=None):
        result = execute(authority, name, Permission.GENERATE_PROPOSAL, arguments or {}, handler)
        assert result.success, result.model_dump(mode='json')
        return result.data

    record = call('reference', project_draft.generate_reference_design, request)
    assert not record['proposal']['unresolved'], record['proposal']['unresolved']
    record = call('accept', project_draft.accept_reference_design,
                  {key: record[key] for key in ('design_id', 'revision', 'request_sha256')})
    prompt = request['prompt'] + '\n' + marker(record)
    proposal = call('generate', wizard_generation.generate, {'prompt': prompt})
    checked = call('validate', lambda _: proposal_service.validate(proposal['proposal_id']))
    assert checked['status'] == 'VALIDATED', checked['validation_result']
    approved = call('review', lambda _: proposal_service.review(checked['proposal_id'],
        revision=checked['revision'], decision='approve', actor='test-human', trace_id=uuid4().hex))
    applied = call('apply', lambda _: proposal_service.apply(approved['proposal_id'], actor='test-human', trace_id=uuid4().hex))
    assert applied['status'] == 'APPLIED'
    def saved_model(_):
        from backend.nis.workflow.services.service import WorkflowStatusService
        from backend.nis.engineering.projects.project_context import current_project_id
        saved = {kind: model.objects(kind) for kind in
                 ('HardwareNode', 'Function', 'HardwareNetworkInterface', 'Message', 'Signal')}
        saved['DataObject'] = WorkflowStatusService(current_project_id()).get()['parameters']['engineering_models']['DataObject']
        return saved
    objects = call('read', saved_model)
    assert len(objects['HardwareNode']) == 3
    interfaces = objects['HardwareNetworkInterface']
    assert len(interfaces) == 4
    assert len({row['physical_port_ref'] for row in interfaces}) == 4
    ethernet = next(row for row in interfaces if row['technology'] == 'Ethernet')
    assumptions = ethernet['capabilities']['simulation_parameter_assumptions']['ethernet']
    assert assumptions['values']['bitrate_bps'] == 1000000000
    assert assumptions['provenance']['bitrate_bps']['hardware_evidence'] is False
    assert assumptions['provenance']['bitrate_bps']['reference_origin']['qualification'] == 'UNVERIFIED'
    assert ethernet['name'].startswith('ETH_')
    functions = objects['Function']
    covered = [entry for row in functions for entry in row.get('configuration', {}).get('reference_source_coverage', [])]
    assert len({entry['fact_id'] for entry in covered}) == 3
    assert any(entry['realization'] == 'COMPOSITE' for entry in covered)
    assert all(row.get('configuration', {}).get('processing_evidence') == 'NONE' for row in functions)
    requirements = [entry for row in objects['HardwareNode'] for entry in row.get('identity', {}).get('reference_source_requirements', [])]
    assert len(requirements) == 1
    assert requirements[0]['source_quote'] == 'REQ-001: Das System MUSS diagnostizierbar sein.'
    assert requirements[0]['allocation'] == 'UNALLOCATED_SOURCE_SCOPE'
    assert len(objects['DataObject']) == 1
    assert len(objects['Message']) == len(record['proposal']['communication'])
    assert len(objects['Signal']) == len(record['proposal']['communication'])
    hardware_ids = {row['name']: str(row['id']) for row in objects['HardwareNode']}
    device_ids = {row['id']: hardware_ids[row['name']] for row in record['proposal']['devices']}
    expected_communication = {row['id']: row for row in record['proposal']['communication']}
    for message in objects['Message']:
        config = message['configuration']
        expected = expected_communication[config['reference_design']['communication_id']]
        contract = config['communication_contract']
        assert contract['producer_ref'] == device_ids[expected['producer_device_id']]
        assert contract['consumer_refs'] == [device_ids[key] for key in expected['consumer_device_ids']]
        assert config['transport_unit']['consumer_refs'] == contract['consumer_refs']
    # Repeating generation may propose nothing but must never duplicate canonical objects.
    repeated = call('repeat', wizard_generation.generate, {'prompt': prompt})
    assert not [row for row in repeated.get('changes', []) if row.get('action', 'CREATE') == 'CREATE']

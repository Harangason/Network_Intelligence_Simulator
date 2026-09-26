"""Question schemas must teach the same contract enforced by the MCP service."""
import asyncio
from uuid import uuid4

import pytest

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.orchestration.local_reasoner import _tool_parameters
from backend.agent_core.orchestration.tool_arguments import prepare_arguments
from backend.agent_core.orchestration.tool_selection import select_tools
from backend.engineering.agent_tools.runtime import ToolAuthority
from backend.engineering.agent_tools.services import TOOLS
from backend.simulator_engineering_mcp.server import create_server


def schema():
    return _tool_parameters(TOOLS['ask_engineering_question'].input_model.model_json_schema())


def question():
    return {'question_id': 'diagnostic_trigger',
            'question': 'Wodurch soll die Diagnoseabfrage ausgelöst werden?',
            'options': [{'id': 'manual', 'label': 'Manuell'},
                        {'id': 'cyclic', 'label': 'Zyklisch'}]}


def test_question_schema_exposes_option_identity_label_and_finite_impact():
    properties = schema()['properties']
    option = properties['options']['items']
    assert {'id', 'label', 'description', 'recommended', 'disabled', 'reason'} <= option['properties'].keys()
    assert 'label' in option['required']
    assert properties['engineering_impact']['enum'] == ['OPTIONAL', 'REQUIRED', 'CRITICAL']
    assert properties['question']['maxLength'] == 2000


@pytest.mark.parametrize('change', [
    lambda q: q['options'][0].pop('id'),
    lambda q: q['options'][0].pop('label'),
    lambda q: q['options'][0].update(id=''),
    lambda q: q['options'][0].update(disabled='perhaps'),
    lambda q: q.update(engineering_impact='Hoch'),
    lambda q: q.update(question='x' * 2001),
])
def test_bad_questions_fail_before_tool_dispatch(change):
    args = question(); change(args)
    with pytest.raises(ValueError):
        prepare_arguments(args, schema())


@pytest.mark.parametrize('legacy', [False, True])
def test_advertised_question_contract_works_through_real_mcp(legacy):
    args = question()
    if legacy:
        for item in args['options']:
            item['value'] = item.pop('id')
    prepared = prepare_arguments(args, schema())

    async def run():
        async with EngineeringMCPClient(create_server(ToolAuthority(f'question-contract-{uuid4()}'))) as client:
            return await client.call('ask_engineering_question', prepared)
    result = asyncio.run(run())
    assert result.success, result
    value = result.data['agent_response']['question']
    assert [item['id'] for item in value['options']] == ['manual', 'cyclic']
    assert value['engineering_impact'] == 'REQUIRED'
    assert value['question'] == args['question']


@pytest.mark.parametrize('corruption', ['duplicate', 'disabled_recommendation'])
def test_domain_question_invariants_remain_strict(corruption):
    args = question()
    if corruption == 'duplicate':
        args['options'][1]['id'] = 'manual'
    else:
        args['options'][0]['disabled'] = True
        args['recommended_options'] = ['manual']
    async def run():
        async with EngineeringMCPClient(create_server(ToolAuthority(f'question-rejection-{uuid4()}'))) as client:
            return await client.call('ask_engineering_question', args)
    result = asyncio.run(run())
    assert not result.success and result.status == 'INVALID_INPUT'


@pytest.mark.parametrize('prompt', [
    'Lege eine Diagnoseabfrage für alle Stellglieder an.',
    'Create a diagnostic request for every actuator.',
    'Reparatur Hardwarearchitektur Signal Nachricht CAN Bus Routing Simulation Trace Fehler',
    'Erstelle Hardware mit Signal Nachricht Routing Netz CAN Simulation Trace und räumlicher Zuordnung',
])
def test_discovery_and_canonical_identity_tools_survive_selection_budget(prompt):
    selected = select_tools(prompt, [{'name': name} for name in TOOLS])
    assert len(selected) <= 24
    assert {'inspect_project', 'inspect_object', 'search_model', 'discover_engineering_tools',
            'ask_engineering_question'} <= {item['name'] for item in selected}

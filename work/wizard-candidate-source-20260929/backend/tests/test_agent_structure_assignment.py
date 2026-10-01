"""Real SQL parity for UI hierarchy changes and reviewed MCP proposals."""
from uuid import uuid4

from backend.engineering.agent_tools import proposal_service
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.agent_tools.services import TOOLS
from backend.agent_core.api.tool_contract import Permission
from backend.engineering.repository import create_object, get_object
from backend.engineering.structure import apply_structure


def test_agent_and_ui_assign_the_same_hierarchy_and_reject_stale_review():
    authority = ToolAuthority('structure-parity-' + uuid4().hex)
    def transaction(operation):
        result = execute(authority, 'test_structure', Permission.READ_MODEL, {}, lambda _: operation())
        assert result.success, result.findings
        return result.data
    def setup():
        old = create_object('HardwareNode', {'name': 'OldController', 'device_type': 'EmbeddedController'})
        target = create_object('HardwareNode', {'name': 'TargetController', 'device_type': 'EmbeddedController'})
        first = create_object('Function', {'name': 'AgentFunction', 'hardware_node_id': str(old['id'])})
        second = create_object('Function', {'name': 'UIFunction', 'hardware_node_id': str(old['id'])})
        return {'target': str(target['id']), 'first': str(first['id']), 'second': str(second['id']), 'old': str(old['id'])}
    ids = transaction(setup)
    assignment = {'child_type': 'Function', 'child_id': ids['first'], 'parent_type': 'HardwareNode', 'parent_id': ids['target']}
    tool = TOOLS['plan_structure_assignments']
    def plan(assignments):
        args = tool.input_model.model_validate({'assignments': assignments, 'rationale': 'Funktionen ausdrücklich dem Zielcontroller zuordnen.'}).model_dump()
        return execute(authority, tool.name, tool.permission, args, tool.handler)
    assert not plan([assignment, assignment]).success
    proposal = plan([assignment])
    assert proposal.success, proposal.findings
    assert proposal.data['status'] == 'VALIDATED', proposal.data
    assert transaction(lambda: get_object('Function', ids['first']))['hardware_node_id'] == ids['old']
    # UI mutation changes the model revision; an older agent review must fail.
    transaction(lambda: apply_structure({'assignments': [{**assignment, 'child_id': ids['second']}]}))
    stale = execute(authority, 'test_review', Permission.READ_MODEL, {}, lambda _: proposal_service.review(
        proposal.data['proposal_id'], revision=proposal.data['revision'], decision='approve', actor='human', trace_id=uuid4().hex))
    assert stale.success and stale.data['status'] == 'OUTDATED'
    assert stale.data['canonical_ids'] == []
    fresh = plan([assignment])
    assert fresh.success, fresh.findings
    transaction(lambda: proposal_service.review(fresh.data['proposal_id'], revision=fresh.data['revision'], decision='approve', actor='human', trace_id=uuid4().hex))
    transaction(lambda: proposal_service.apply(fresh.data['proposal_id'], actor='human', trace_id=uuid4().hex))
    assert str(transaction(lambda: get_object('Function', ids['first']))['hardware_node_id']) == ids['target']
    assert str(transaction(lambda: get_object('Function', ids['second']))['hardware_node_id']) == ids['target']
    transaction(lambda: proposal_service.apply(fresh.data['proposal_id'], actor='human', trace_id=uuid4().hex))

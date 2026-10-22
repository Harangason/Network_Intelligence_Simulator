"""Isolated source/draft/review regressions; not native Qwen or E2E proof."""
from copy import deepcopy
import json
from uuid import uuid4

import pytest

from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.tools.runtime import ToolAuthority, execute
from backend.nis.agent.tools import project_draft as drafts
from backend.nis.agent.orchestration import project_intake as intake
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
from backend.tests.test_reference_design import fixture_request, fixture_design


def marker(record):
    return drafts.REFERENCE_DESIGN_MARKER + json.dumps({key: record[key] for key in (
        'schema_version', 'design_id', 'revision', 'request_sha256', 'source_sha256',
        'status', 'proposal', 'fact_id_map', 'decision_evidence', 'protected_fields')}, ensure_ascii=False)


@pytest.fixture
def reference(monkeypatch):
    calls = []
    async def unit_inference(_self, prepared):
        calls.append(prepared['request_sha256'])
        return intake.validate_reference_design(fixture_design(prepared), prepared)
    monkeypatch.setattr(LocalEngineeringReasoner, 'plan_reference_design', unit_inference)
    authority = ToolAuthority('reference-draft-' + uuid4().hex, 'local-human')
    request = {**fixture_request(), 'source_request_id': uuid4().hex}
    result = execute(authority, 'reference-plan', Permission.GENERATE_PROPOSAL, request, drafts.generate_reference_design)
    assert result.success, result.findings
    return authority, request, result.data, calls


def run(authority, handler, arguments=None):
    result = execute(authority, handler.__name__, Permission.GENERATE_PROPOSAL, arguments or {}, handler)
    return result


def test_native_draft_planning_persists_complete_source_and_replays_same_operation(reference):
    authority, request, record, calls = reference
    assert record['status'] == 'REVIEW_REQUIRED' and record['canonical_writes'] is False
    assert record['request']['prompt'] == request['prompt']
    repeated = run(authority, drafts.generate_reference_design, request)
    assert repeated.success and repeated.data == record
    assert calls == [record['request_sha256']]
    current = execute(authority, 'read', Permission.READ_MODEL, {}, lambda _: drafts.inspect()).data
    assert current['source_format'] == 'REFERENCE_DOCUMENT'
    assert current['sources'][0]['text'] == record['source_evidence']['source_text']
    from backend.nis.agent.tools import model
    assert execute(authority, 'objects', Permission.READ_MODEL, {}, lambda _: model.objects('HardwareNode')).data == []


def test_same_reference_operation_cannot_change_source(reference):
    authority, request, record, calls = reference
    changed = {**request, 'reference_sources': [{'id': 'extra', 'name': 'design', 'role': 'USER_CLARIFICATION',
        'text': 'Beispiel', 'source_sha256': __import__('hashlib').sha256(b'Beispiel').hexdigest(), 'allowed_fields': ['ports']}]}
    rejected = run(authority, drafts.generate_reference_design, changed)
    assert not rejected.success
    assert calls == [record['request_sha256']]


def test_reference_review_is_bound_to_project_and_revision(reference):
    authority, _request, record, _calls = reference
    args = {key: record[key] for key in ('design_id', 'revision', 'request_sha256')}
    assert not run(ToolAuthority('other-' + uuid4().hex), drafts.accept_reference_design, args).success
    assert not run(authority, drafts.accept_reference_design, {**args, 'revision': record['revision'] + 3}).success
    accepted = run(authority, drafts.accept_reference_design, args)
    assert accepted.success, accepted.findings
    assert accepted.data['status'] == 'ACCEPTED'
    assert run(authority, drafts.accept_reference_design, args).data == accepted.data
    assert accepted.data['canonical_writes'] is False


def test_client_cannot_relabel_or_replace_reference_decisions(reference):
    authority, request, record, _calls = reference
    accepted = run(authority, drafts.accept_reference_design, {key: record[key] for key in ('design_id', 'revision', 'request_sha256')}).data
    for field, value in [('proposal', {}), ('decision_evidence', []), ('protected_fields', {'commands': {}})]:
        altered = deepcopy(accepted)
        altered[field] = value
        if altered[field] == accepted[field]:
            continue
        prompt = request['prompt'] + '\n' + marker(altered)
        result = run(authority, lambda _: drafts.reference_design_for_prompt(prompt))
        assert not result.success, field


def test_literal_inventory_parser_cannot_replace_rich_document_draft(reference):
    authority, _request, record, _calls = reference
    current = execute(authority, 'read', Permission.READ_MODEL, {}, lambda _: drafts.inspect()).data
    result = run(authority, drafts.command, {'action': 'AMEND', 'operation_id': uuid4().hex,
                                           'revision': current['revision'], 'requirement': 'Ein Sensor'})
    assert not result.success
    assert execute(authority, 'read', Permission.READ_MODEL, {}, lambda _: drafts.inspect()).data == current


def test_accepted_source_plan_survives_normal_wizard_capture(reference):
    authority, request, record, _calls = reference
    accepted = run(authority, drafts.accept_reference_design, {key: record[key] for key in ('design_id', 'revision', 'request_sha256')}).data
    prompt = request['prompt'] + '\n' + marker(accepted)
    def capture(_):
        from backend.nis.agent.tools import conversation, structured_project_draft
        state = conversation.read()
        structured_project_draft.capture(state, {'run_id': 'test-run', 'revision': 1, 'prompt': prompt, 'target': 'simulation'},
                                         {'industry': 'embedded_systems', 'technologies': ['CAN'], 'task': 'full original'})
        conversation.write(state)
        return drafts.reference_design_for_prompt(prompt)
    result = run(authority, capture)
    assert result.success, result.findings
    assert result.data == accepted


def test_reference_acceptance_is_not_an_agent_approval_tool():
    from backend.nis.agent.tools.services import TOOLS
    assert 'generate_reference_design' in TOOLS
    assert 'inspect_reference_design' in TOOLS
    assert 'accept_reference_design' not in TOOLS


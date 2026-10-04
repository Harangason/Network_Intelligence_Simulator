"""Replay a captured wizard prompt in an isolated model proposal; never apply it."""
import json
from pathlib import Path
from uuid import uuid4
import pytest
from backend.nis.agent.tools.runtime import ToolAuthority
from backend.nis.agent.tools.runtime import execute
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.tools import wizard_generation as wizard_generation
from backend.nis.agent.tools import proposal_service as proposal_service

def test_actual_wizard_model_is_valid():
    if not Path('backend/runtime/wizard-audit-workflow.json').exists():
        pytest.skip('Local captured wizard evidence is not available')
    authority = ToolAuthority('pytest-wizard-actual-' + str(uuid4()))
    generated = execute(authority, 'generate_model', Permission.GENERATE_PROPOSAL, {'prompt': json.loads(Path('backend/runtime/wizard-audit-workflow.json').read_text(encoding='utf-8'))['context']['wizard_request']['prompt']}, wizard_generation.generate)
    assert generated.success, generated.model_dump()
    validated = execute(authority, 'validate_proposal', Permission.VALIDATE, {'proposal_id': generated.data['proposal_id']}, lambda a: proposal_service.validate(a['proposal_id']))
    assert validated.success, validated
    assert validated.data['validation_result']['valid'], validated.data['validation_result']


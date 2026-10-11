"""Explicit project creation with a durable reservation and recoverable dispatch.

The origin's canonical model is never copied or changed. Only the selected
draft revision crosses the project boundary, with recorded provenance.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from backend.agent_core.api.tool_contract import Permission
from ..db import ConcurrentUpdateError
from ..project_context import current_project_id
from ..workflow.service import WorkflowStatusService
from . import conversation
from .runtime import PostCommitAction, ToolAuthority, execute


class CreateProject(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation_id: str = Field(min_length=8, max_length=120)
    draft_id: str = Field(min_length=1, max_length=80)
    revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)


def create(arguments):
    request = CreateProject.model_validate({k: v for k, v in arguments.items() if not k.startswith('_')})
    if not request.name.strip():
        raise ValueError('Ein Projektname ist erforderlich.')
    origin = current_project_id()
    state = conversation.read()
    operations = state.setdefault('project_creation_operations', {})
    signature = hashlib.sha256(json.dumps(request.model_dump(), sort_keys=True).encode()).hexdigest()
    reservation = operations.get(request.operation_id)
    if reservation and reservation['signature'] != signature:
        raise ConcurrentUpdateError('Diese Operations-ID gehört zu einer anderen Projektanlage.')
    if not reservation:
        draft = state.get('engineering_draft')
        if not draft or draft['draft_id'] != request.draft_id or draft['revision'] != request.revision:
            raise ConcurrentUpdateError('Der Projektentwurf wurde inzwischen geändert.')
        target = 'network-project-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')[:17] + '-' + uuid4().hex[:8]
        reservation = {'signature': signature, 'project_id': target, 'draft': deepcopy(draft), 'name': request.name.strip()}
        operations[request.operation_id] = reservation
        conversation.write(state)
    target = reservation['project_id']
    lineage = {'project_id': origin, 'draft_id': request.draft_id, 'revision': request.revision,
               'operation_id': request.operation_id}

    def initialize(_):
        target_state = conversation.read()
        existing = target_state.get('engineering_draft')
        if existing and existing.get('origin') != lineage:
            raise ConcurrentUpdateError('Das Zielprojekt enthält bereits einen anderen Entwurf.')
        if not existing:
            existing = {**deepcopy(reservation['draft']), 'draft_id': str(uuid4()), 'project_id': target,
                        'revision': 1, 'origin': lineage, 'project_name': reservation['name']}
            existing.pop('proposal_id', None)
            existing.pop('model_proposal_id', None)
            target_state['engineering_draft'] = existing
            conversation.write(target_state)
            WorkflowStatusService(target).set_context({
                'project_name': reservation['name'],
                'engineering_wizard_settings': {'project_name': reservation['name'],
                                                'model_type': existing.get('industry') or 'custom'},
            }, summary=True)
        return {'project_id': target, 'draft': existing, 'created': True,
                'receipt': {'operation_id': request.operation_id, 'accepted': True}, 'origin': lineage}

    return PostCommitAction(
        dispatch=lambda: execute(ToolAuthority(target, arguments.get('_actor', 'engineering-agent')),
                                 'initialize_project_draft', Permission.GENERATE_PROPOSAL, {}, initialize),
        failed=lambda: None,  # Reservation remains retryable after a process failure.
    )

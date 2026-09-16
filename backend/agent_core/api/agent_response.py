"""Data-only response contract, shared by every engineering-agent consumer."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
import logging
from .input_output import AgentOutputEnvelope
from pydantic import BaseModel, ConfigDict, Field, model_validator

ChatMessageType = Literal['TEXT', 'QUESTION', 'MULTI_SELECT', 'SINGLE_SELECT', 'RECOMMENDATION',
    'FINDING', 'PROGRESS', 'RESULT', 'APPROVAL', 'ERROR']
QuestionStatus = Literal['OPEN', 'ANSWERED', 'SKIPPED', 'EXPIRED', 'OUTDATED']


class InteractiveOption(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=300)
    description: str = Field(default='', max_length=2000)
    recommended: bool = False
    disabled: bool = False
    reason: str = Field(default='', max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class InteractiveQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(default_factory=lambda: str(uuid4()))
    question: str = Field(min_length=1, max_length=2000)
    description: str = ''
    selection_mode: Literal['SINGLE', 'MULTI'] = 'SINGLE'
    options: list[InteractiveOption] = Field(min_length=2, max_length=8)
    recommended_options: list[str] = Field(default_factory=list)
    required: bool = True
    engineering_impact: Literal['OPTIONAL', 'REQUIRED', 'CRITICAL'] = 'REQUIRED'
    context_refs: list[dict[str, str]] = Field(default_factory=list)
    status: QuestionStatus = 'OPEN'

    @model_validator(mode='after')
    def valid_options(self):
        ids = [o.id for o in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError('Auswahl-IDs müssen eindeutig sein.')
        recommended = self.recommended_options or [o.id for o in self.options if o.recommended]
        if not set(recommended) <= {o.id for o in self.options if not o.disabled}:
            raise ValueError('Empfehlungen müssen verfügbare Optionen sein.')
        if self.selection_mode == 'SINGLE' and len(recommended) > 1:
            raise ValueError('Eine Einfachauswahl hat höchstens eine Empfehlung.')
        self.recommended_options = recommended
        return self


class AgentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['QUESTION_ANSWER', 'SKIP_QUESTION', 'RESUME', 'FINDING_ACTION'] = 'QUESTION_ANSWER'
    question_id: str = Field(default='', max_length=200)
    finding_id: str = Field(default='', max_length=200)
    selected_options: list[str] = Field(default_factory=list, max_length=8)


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    outputs: list[AgentOutputEnvelope] = Field(default_factory=list, max_length=20)
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: ChatMessageType
    text: str = Field(default='', max_length=30000)
    title: str = Field(default='', max_length=300)
    context_refs: list[dict[str, str]] = Field(default_factory=list, max_length=100)
    question: InteractiveQuestion | None = None
    options: list[InteractiveOption] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list, max_length=12)
    findings: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    progress: list[dict[str, str]] = Field(default_factory=list, max_length=20)
    recommendation: dict[str, Any] | None = None
    approval: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Existing bounded workload/proposal payloads remain compatible with MCP.
    proposal: dict[str, Any] | None = None
    workload: dict[str, Any] | None = None
    status: str = ''
    severity: str = ''

    @model_validator(mode='after')
    def question_required(self):
        if self.type in {'QUESTION', 'SINGLE_SELECT', 'MULTI_SELECT'} and self.question is None:
            raise ValueError('Eine Auswahlantwort benötigt eine strukturierte Frage.')
        if self.proposal is not None:
            required = {'proposal_id', 'revision', 'status', 'rationale', 'assumptions', 'changes', 'validation_result', 'canonical_ids'}
            if not required <= self.proposal.keys() or not isinstance(self.proposal['changes'], list):
                raise ValueError('Ungültiger Freigabevorschlag.')
        return self


def validate_response(value: dict) -> dict:
    """Fail closed to inert text; never interpret markup or arbitrary UI code."""
    try:
        return AgentResponse.model_validate(value).model_dump(mode='json', exclude_none=True)
    except (ValueError, TypeError) as error:
        logging.getLogger(__name__).warning('Invalid engineering AgentResponse (%s); using TEXT fallback', error)
        return AgentResponse(type='TEXT', text='Die Antwort konnte nicht als Engineering-Karte dargestellt werden. Bitte die Anfrage präzisieren.',
            metadata={'contract_error': True}).model_dump(mode='json', exclude_none=True)

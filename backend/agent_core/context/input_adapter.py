"""Adapt existing accepted requests without introducing a second command protocol."""
from hashlib import sha256
from ..api.input_output import AgentInputEnvelope
from ..orchestration.capability_intent import connection_request
from ..orchestration.project_intake import is_project_request


def adapt_input(prompt, context, *, run_id, raw_input=None, operation_id=None, revision=None):
    files = []
    for document in context.document_sources:
        files.append({'name': document.name, 'format': document.format, 'size': document.size,
                      'truncated': document.truncated,
                      'extracted_text_sha256': sha256(document.text.encode('utf-8')).hexdigest()})
    kind = 'USER_DECISION' if raw_input else 'FILE' if files else 'SELECTION' if context.selected_object_refs else 'TEXT'
    return AgentInputEnvelope(input_type=kind, content={'text': prompt, 'decision': raw_input},
        project_ref=context.active_project_id, run_ref=run_id, operation_ref=operation_id,
        request_revision=str(revision) if revision is not None else None,
        selected_objects=context.selected_object_refs, active_view=context.active_view, files=files,
        user_intent='CONNECT_FUNCTIONS' if connection_request(prompt) else context.requested_mode or ('CREATE_ARCHITECTURE' if is_project_request(prompt) else 'ENGINEERING_REQUEST'),
        constraints=context.user_constraints)

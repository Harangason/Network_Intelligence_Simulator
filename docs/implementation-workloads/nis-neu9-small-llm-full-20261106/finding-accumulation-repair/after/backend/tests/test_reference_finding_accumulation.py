"""Repeated native findings remain open once, with every distinct decision retained."""
from copy import deepcopy
import json

import pytest

from backend.nis.agent.orchestration import local_reasoner as r
from backend.tests.test_reference_reasoner import (
    effective_reference_context, reasoner_with_transport, run_reference,
)


@pytest.mark.parametrize('different_field', ['code', 'message', 'target_ref', 'native'])
def test_repeated_native_findings_do_not_multiply_or_hide_distinct_decisions(monkeypatch, different_field):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch)
    original = r._reference_stream_response
    first = {'code': 'NEEDS_REVIEW', 'message': 'Physical interface evidence remains missing.', 'target_ref': 'source-target'}
    if different_field == 'native':
        # Byte-equivalent finding records from the real qwen3.5:9b counter
        # on 2026-11-08. Surrounding workflow remains explicitly mocked.
        first = {'code': 'MISSING_HARDWARE_EVIDENCE', 'target_ref': 'offline-a',
                 'message': 'No measured hardware qualification evidence for offline-a.'}
        different = {**first, 'target_ref': 'offline-b',
                     'message': 'No measured hardware qualification evidence for offline-b.'}
    else:
        different = {**first, different_field: first[different_field] + ' different'}
    replies = []

    async def repeat(client, url, payload, callback):
        context = effective_reference_context(payload['messages'])
        current = context['current_candidate']['unresolved']
        keys = [json.dumps(row, sort_keys=True) for row in current]
        assert len(keys) == len(set(keys)), 'Previously reported identical findings multiplied in planning context'
        if current:
            assert current == [first, different], 'A distinct open decision was lost or reordered'
        response = await original(client, url, payload, callback)
        content = json.loads(response['message']['content'])
        content['unresolved'] = [deepcopy(first), deepcopy(first), deepcopy(different)]
        response['message']['content'] = json.dumps(content)
        replies.append(deepcopy(response))
        return response

    monkeypatch.setattr(r, '_reference_stream_response', repeat)
    # The normal proposal remains subject to review with both findings open;
    # constructing it is not canonical model acceptance.
    result = run_reference(reasoner, prepared)
    assert result['status'] == 'REVIEW_REQUIRED'
    assert result['canonical_writes'] is False
    assert result['proposal']['unresolved'] == [first, different]
    assert len(observed) >= 5
    assert all(json.loads(row['message']['content'])['unresolved'] == [first, first, different] for row in replies)
    assert any(row['current_candidate']['unresolved'] == [first, different] for row in observed)


def test_invalid_repeated_finding_is_rejected_before_accumulation(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch)
    original = r._reference_stream_response

    async def malformed(client, url, payload, callback):
        response = await original(client, url, payload, callback)
        content = json.loads(response['message']['content'])
        content['unresolved'] = [{'code': 'NEEDS_REVIEW', 'message': 'Missing target field'}] * 2
        response['message']['content'] = json.dumps(content)
        return response

    monkeypatch.setattr(r, '_reference_stream_response', malformed)
    with pytest.raises(ValueError):
        run_reference(reasoner, prepared)
    assert len(observed) == 2
    assert all(row['current_candidate']['unresolved'] == [] for row in observed)

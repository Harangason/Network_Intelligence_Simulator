"""Prepare bounded complete handoff and lossless durable continuation."""
from pathlib import Path

OUT = Path(__file__).parent
REL = 'backend/nis/agent/context/limits.py'
(OUT / 'staged' / REL).write_text('''"""Shared bounded sizes for complete source-bound engineering requests."""
MAX_DOCUMENT_SOURCE_CHARS = 1_000_000
# Original text, reviewed source snapshot, bounded typed evidence and choices.
# This bounds storage/transport; individual inference context budgets remain.
MAX_REQUIREMENT_LENGTH = 4 * MAX_DOCUMENT_SOURCE_CHARS + 100_000
MAX_REQUIREMENT_REQUEST_BYTES = 12 * MAX_REQUIREMENT_LENGTH + 1_048_576
''', encoding='utf-8')

REL = 'backend/nis/agent/orchestration/project_intake.py'
p = OUT / 'staged' / REL
text = p.read_text(encoding='utf-8')
text = text.replace('DOCUMENT_SOURCE_MAX_CHARS = 1_000_000', 'from backend.nis.agent.context.limits import MAX_DOCUMENT_SOURCE_CHARS\n\nDOCUMENT_SOURCE_MAX_CHARS = MAX_DOCUMENT_SOURCE_CHARS')
p.write_text(text, encoding='utf-8')

REL = 'backend/nis/agent/tools/run_status.py'
text = (OUT / 'before' / REL).read_text(encoding='utf-8')
old = '    return original[:max(0, maximum - len(suffix))] + suffix'
assert text.count(old) == 1
text = text.replace(old, "    if len(original) + len(suffix) > maximum:\n        raise ValueError('Der vollständige Auftrag mit Fortsetzung überschreitet die zulässige Länge; die Originalquelle wird nicht gekürzt.')\n    return original + suffix")
(OUT / 'staged' / REL).write_text(text, encoding='utf-8')

REL = 'backend/nis/agent/tools/api.py'
text = (OUT / 'before' / REL).read_text(encoding='utf-8')
text = text.replace('from backend.nis.agent.context.limits import MAX_REQUIREMENT_LENGTH', 'from backend.nis.agent.context.limits import MAX_REQUIREMENT_LENGTH, MAX_REQUIREMENT_REQUEST_BYTES')
text = text.replace('def chat():\n    payload = request.get_json(silent=True)', 'def chat():\n    request.max_content_length = MAX_REQUIREMENT_REQUEST_BYTES\n    payload = request.get_json(silent=True)')
old = "    if payload.get('wizard_command') is None:\n        payload['prompt'] = restore_wizard_continuation_prompt(\n            payload['prompt'], (workflow.get('context') or {}).get('agent_wizard_status'))"
assert text.count(old) == 1
text = text.replace(old, "    if payload.get('wizard_command') is None:\n        try:\n            payload['prompt'] = restore_wizard_continuation_prompt(\n                payload['prompt'], (workflow.get('context') or {}).get('agent_wizard_status'))\n        except ValueError as exc:\n            return jsonify({'error': str(exc)}), 400")
(OUT / 'staged' / REL).write_text(text, encoding='utf-8')

REL = 'backend/tests/test_agent_chat_ux.py'
text = (OUT / 'before' / REL).read_text(encoding='utf-8')
old = "    assert len(restore_wizard_continuation_prompt(compact, {'run_id': run_id, 'agent_prompt': original}, 180)) <= 180"
assert text.count(old) == 1
text = text.replace(old, "    with pytest.raises(ValueError, match='nicht gekürzt'):\n        restore_wizard_continuation_prompt(compact, {'run_id': run_id, 'agent_prompt': original}, 180)")
text += '''

def test_complete_reviewed_document_request_can_exceed_legacy_120k_limit_without_losing_source():
    from backend.nis.agent.context.agent_context import AgentContext
    from backend.nis.agent.context.limits import MAX_DOCUMENT_SOURCE_CHARS, MAX_REQUIREMENT_LENGTH
    original = 'Strukturierte Vorgaben fuer den Engineering-Agenten:\\nLauf-ID: source-bound-12345678\\nper Wizard-Uebernehmen bestaetigt\\n' + ('Vollständige Dokumentquelle.\\n' * 7000)
    assert len(original) > 120_000
    context = AgentContext(active_project_id='robotics-document-bounds-test', current_requirement=original)
    assert context.current_requirement == original
    restored = restore_wizard_continuation_prompt('Lauf-ID: source-bound-12345678\\nWeiter', {'run_id': 'source-bound-12345678', 'agent_prompt': original})
    assert restored.startswith(original) and len(restored) > len(original)
    assert MAX_REQUIREMENT_LENGTH >= 4 * MAX_DOCUMENT_SOURCE_CHARS


def test_durable_continuation_rejects_overflow_instead_of_slicing_the_confirmed_source():
    original = 'Strukturierte Vorgaben fuer den Engineering-Agenten:\\nper Wizard-Uebernehmen bestaetigt\\nOriginalquelle am Ende unbedingt erhalten.'
    with pytest.raises(ValueError, match='nicht gekürzt'):
        restore_wizard_continuation_prompt('Lauf-ID: source-bound-12345678\\nWeiter', {'run_id': 'source-bound-12345678', 'agent_prompt': original}, maximum=len(original) + 10)
'''
(OUT / 'staged' / REL).write_text(text, encoding='utf-8')
print('Staged shared request bounds and lossless continuation prepared.')

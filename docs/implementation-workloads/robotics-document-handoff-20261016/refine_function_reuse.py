from pathlib import Path
S = Path(__file__).parent / 'semantic-staged'
p = S / 'backend/nis/agent/tools/wizard_generation.py'
s = p.read_text(encoding='utf-8')
anchor = 'def _reviewed_document_functions('
helper = '''def _reviewed_function_reuse_matches(fact: dict, existing: dict, *, shared_citation: bool) -> bool:
    """A shared list citation cannot collapse distinct canonical functions."""
    quote = str(existing.get('source_quote') or '').strip()
    if len(quote) < 3 or quote not in fact['source_quote']:
        return False
    if not shared_citation:
        return True
    subject = str(fact['name']).rsplit(' [', 1)[0].strip().casefold()
    return str(existing.get('name') or '').strip().casefold() == subject or quote.lstrip('-* ').casefold() == subject


'''
assert anchor in s
s = s.replace(anchor, helper + anchor, 1)
old = "            if row.get('hardware_node_id') == host_ref and len(quote) >= 3 and quote in duty['source_quote'] and (not any(other.get('kind') == 'FUNCTION' and other.get('source_quote') == duty['source_quote'] and other.get('name') != duty['name'].rsplit(' [', 1)[0] and other.get('source_context', []) == duty.get('source_context', []) for other in (document_evidence or {}).get('components', [])) or duty['name'].rsplit(' [', 1)[0] in quote):"
new = "            shared_citation = any(other.get('kind') == 'FUNCTION' and other.get('source_quote') == duty['source_quote']\n                                  and other.get('name') != duty['name'].rsplit(' [', 1)[0]\n                                  and other.get('source_context', []) == duty.get('source_context', [])\n                                  for other in (document_evidence or {}).get('components', []))\n            if row.get('hardware_node_id') == host_ref and _reviewed_function_reuse_matches(\n                    duty, configuration.get('source_scoped_function') or {}, shared_citation=shared_citation):"
assert old in s
s = s.replace(old, new)
p.write_text(s, encoding='utf-8')
p = S / 'backend/tests/test_wizard_generation.py'
s = p.read_text(encoding='utf-8') + '''

def test_atomic_functions_never_reuse_a_combined_list_function_or_another_subject():
    combined = {'name': 'Perception, Planning', 'source_quote': 'Perception, Planning'}
    perception = {'name': 'Perception', 'source_quote': 'Perception'}
    for subject in ['Perception', 'Planning']:
        fact = {'name': subject + ' [0123456789]', 'source_quote': combined['source_quote']}
        assert not wizard_generation._reviewed_function_reuse_matches(fact, combined, shared_citation=True)
        assert wizard_generation._reviewed_function_reuse_matches(fact, perception, shared_citation=True) is (subject == 'Perception')
'''
p.write_text(s, encoding='utf-8')

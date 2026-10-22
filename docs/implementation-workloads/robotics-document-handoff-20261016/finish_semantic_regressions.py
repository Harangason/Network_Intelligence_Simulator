from pathlib import Path
OUT = Path(__file__).parent
S = OUT / 'semantic-staged'
p = S / 'backend/nis/agent/orchestration/project_intake.py'
s = p.read_text(encoding='utf-8')
old = "            policy = row_policy if normative_row else document_component_policy(clause)\n            if function_section"
new = "            policy = row_policy if normative_row else document_component_policy(clause)\n            if architecture_section is not None and policy is None:\n                policy = {'kind': 'CATEGORY', 'role': 'OTHER', 'quantity': None}\n            if function_section"
assert old in s
p.write_text(s.replace(old, new), encoding='utf-8')
p = S / 'backend/nis/agent/tools/wizard_generation.py'
s = p.read_text(encoding='utf-8').replace('wizard-model-v26-reviewed-document-facts', 'wizard-model-v27-source-bound-function-atoms')
p.write_text(s, encoding='utf-8')
p = S / 'backend/tests/test_wizard_generation.py'
s = p.read_text(encoding='utf-8') + '''

def test_shared_list_quote_never_transfers_a_different_function_owner():
    from backend.nis.agent.orchestration.project_intake import document_fact_identity
    facts = [{'name': name, 'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None,
              'source_quote': 'Perception, Planning', 'source_context': ['Robot', 'Functions']}
             for name in ['Perception', 'Planning']]
    chain = {'hardware_name': 'ADC', 'device_type': 'ECU', 'configuration': {
        'source_scoped_functions': [{'name': 'Perception', 'source_quote': 'Perception'}],
        'document_equipment_evidence': {'source_context': ['Robot', 'Architecture']}}}
    evidence = {'components': facts, 'source_sha256': 'a' * 64}
    with pytest.raises(ValueError, match='Planning'):
        wizard_generation._reviewed_document_functions(evidence, ['adc', 'planner'], [chain])
    evidence['function_assignments'] = {document_fact_identity(facts[1]): 'Planner'}
    result = wizard_generation._reviewed_document_functions(evidence, ['adc', 'planner'], [chain])
    assert [duty['host'] for duty in result] == ['adc', 'planner']
    assert result[0]['assignment_source'] == 'source_scoped_function'
    assert result[1]['assignment_source'] == 'explicit_user_statement'
'''
p.write_text(s, encoding='utf-8')
# The second native validator requires each atom identity, not simply one
# shared list quote, and locates the original unchanged baseline correctly.
for name in ['verify_robotics_dom.py', 'capture_source_units.py']:
    p = OUT / 'native-attempt-2' / name
    s = p.read_text(encoding='utf-8').replace("OUT.parent / 'industrial-robotics-wizard-20261016/source-baseline.json'", "OUT.parents[1] / 'industrial-robotics-wizard-20261016/source-baseline.json'")
    s = s.replace("if not any(piece in fact['quote'] and", "if not any(piece in fact['quote'] and (not unit.get('source_quote') or fact['name'] == unit['text'][:120]) and")
    p.write_text(s, encoding='utf-8')

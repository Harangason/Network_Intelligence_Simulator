from pathlib import Path
S = Path(__file__).parent / 'semantic-staged'
p = S / 'backend/nis/agent/orchestration/project_intake.py'
s = p.read_text(encoding='utf-8')
old = "        policy = document_component_policy(component.source_quote)"
new = "        if component.kind in {'INSTANCE', 'CATEGORY'} and component.source_quote not in eligible_source:\n            semantic_errors.append(f'{component.name}: Test-/Indexzitat belegt keine installierte Hardware.')\n        policy = document_component_policy(component.source_quote)"
assert old in s
s = s.replace(old, new).replace('    for line in source.splitlines():', '    for line in eligible_source.splitlines():')
p.write_text(s, encoding='utf-8')
p = S / 'backend/tests/test_qwen_document_intake.py'
s = p.read_text(encoding='utf-8') + '''

def test_test_only_controller_declarations_never_create_alias_or_installed_hardware_obligations():
    source = '# Robot\\n## Verification\\nTC-R-01: Controller (ABC) fails.\\n'
    data = {**interpretation(), 'components': [], 'technologies': []}
    assert validate_document_interpretation(data, source)['components'] == []
    data['components'] = [{'name': 'Controller (ABC)', 'kind': 'INSTANCE', 'role': 'CONTROLLER', 'quantity': 1,
                           'source_quote': 'TC-R-01: Controller (ABC) fails.'}]
    with pytest.raises(ValueError, match='Test-/Indexzitat'):
        validate_document_interpretation(data, source)
'''
p.write_text(s, encoding='utf-8')

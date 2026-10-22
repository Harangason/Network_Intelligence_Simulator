from pathlib import Path
S = Path(__file__).parent / 'semantic-staged'
p = S / 'backend/nis/agent/orchestration/project_intake.py'
s = p.read_text(encoding='utf-8')
assert r'(?:[\w/-]+[- ]?)*(?:zellen|cells)' in s
s = s.replace(r'(?:[\w/-]+[- ]?)*(?:zellen|cells)', r'[\w/ -]*(?:zellen|cells)')
p.write_text(s, encoding='utf-8')
p = S / 'backend/tests/test_qwen_document_intake.py'
s = p.read_text(encoding='utf-8') + '''

def test_composite_cell_match_is_bounded_for_long_non_cell_declarations():
    from backend.nis.agent.orchestration.project_intake import document_component_policy
    assert document_component_policy('Unspecified mechanism with ' + 'long ' * 100 + 'description') is None
    assert document_component_policy('Manuelle Steuerung des Arms')['role'] == 'CONTROLLER'
'''
p.write_text(s, encoding='utf-8')

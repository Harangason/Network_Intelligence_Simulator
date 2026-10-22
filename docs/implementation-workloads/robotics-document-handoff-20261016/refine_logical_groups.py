from pathlib import Path
S = Path(__file__).parent / 'semantic-staged'
p = S / 'backend/nis/agent/orchestration/project_intake.py'
s = p.read_text(encoding='utf-8').replace('Fleet Manager|Map|Traffic Service|MES|WMS-Anbindung', 'Fleet Manager|Map|Traffic Service|MES|WMS-Anbindung|Lagerverwaltung|Warehouse Management|Safety Zones')
old = "    role = None\n    if re.search"
new = "    # Composite cells are physical groupings, not a single PLC/robot role.\n    if re.fullmatch(r'\\s*(?:[\\w/-]+[- ]?)*(?:zellen|cells)\\s*\\.?\\s*', text, re.I):\n        return {'kind': 'CATEGORY', 'role': 'OTHER', 'quantity': None}\n    role = None\n    if re.search"
assert old in s
p.write_text(s.replace(old, new), encoding='utf-8')
p = S / 'backend/tests/test_qwen_document_intake.py'
s = p.read_text(encoding='utf-8').replace("['Fleet Manager', 'MES', 'Historian', 'Datenbank', 'Traceability', 'Alarmmanagement']", "['Fleet Manager', 'MES', 'Historian', 'Datenbank', 'Traceability', 'Alarmmanagement', 'Lagerverwaltung', 'Safety Zones']")
s += '''

def test_mixed_plc_robot_cells_do_not_assert_a_single_controller_role():
    from backend.nis.agent.orchestration.project_intake import document_component_policy
    assert document_component_policy('PLC-/Robotikzellen') == {'kind': 'CATEGORY', 'role': 'OTHER', 'quantity': None}
'''
p.write_text(s, encoding='utf-8')

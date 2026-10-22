from pathlib import Path
S = Path(__file__).parent / 'semantic-staged'
p = S / 'backend/nis/agent/orchestration/project_intake.py'
s = p.read_text(encoding='utf-8')
old = "            interface_section = heading[1] if heading else ''\n        if heading and platform_section"
new = "            interface_section = heading[1] if heading else ''\n        elif re.match(r'^(?:Aufgaben|Tasks|Responsibilities|Funktionen|Functions|Systemfunktionen|Funktionsbeschreibung|Hardware|Architektur|Architecture|Plattform|Platform|Implementierung|Implementation|Sensorik|Aktorik|Anforderungen|Requirements)\\s*(?::|\\(|$)', structural, re.I) or re.match(r'^(?:Controller|Gateway|ECU)\\s*:', structural, re.I):\n            interface_section = None\n        if heading and platform_section"
assert old in s
s = s.replace(old, new)
s = s.replace("r'^(?:Aufgaben|Tasks|Responsibilities|Funktionen|Functions|Schnittstellen|Interfaces|Anschlüsse|Anforderungen|Requirements)\\s*:'", "r'^(?:Aufgaben|Tasks|Responsibilities|Funktionen|Functions|Systemfunktionen|Funktionsbeschreibung|Hardware|Architektur|Architecture|Sensorik|Aktorik|Schnittstellen|Interfaces|Anschlüsse|Anforderungen|Requirements)\\s*(?::|\\(|$)'")
p.write_text(s, encoding='utf-8')
p = S / 'backend/tests/test_qwen_document_intake.py'
s = p.read_text(encoding='utf-8').replace("    assert len(functions) == 1 and 'Motorsteuerung' in functions[0]['text'] and 'Getriebelogik' in functions[0]['text']", "    assert [unit['text'] for unit in functions] == ['Motorsteuerung', 'Getriebelogik']\n    assert len({unit['source_ref'] for unit in functions}) == 2\n    assert all('Schnittstellen:' not in unit['text'] for unit in functions)")
s += '''

def test_plain_interface_and_platform_scopes_end_at_explicit_function_or_hardware_captions():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    source = 'Schnittstellen:\\nCAN\\nFunktionen:\\nPlanung\\nPlattform:\\nAUTOSAR Adaptive\\nSensorik (Kamera, Radar)\\nAufgaben:\\nDiagnose'
    units = document_component_sources(document_source_references(source))
    assert [unit['text'] for unit in units] == ['Planung', 'Sensorik (Kamera, Radar)', 'Diagnose']
    assert [unit['policy']['kind'] for unit in units] == ['FUNCTION', 'CATEGORY', 'FUNCTION']
    assert all(unit['required'] for unit in units)
'''
p.write_text(s, encoding='utf-8')

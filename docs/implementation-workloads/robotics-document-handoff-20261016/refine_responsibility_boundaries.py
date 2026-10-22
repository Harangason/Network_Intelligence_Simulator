from pathlib import Path
import hashlib
import json
OUT = Path(__file__).parent.resolve()
S = OUT / 'semantic-staged'
p = S / 'backend/nis/agent/orchestration/project_intake.py'
s = p.read_text(encoding='utf-8')
s = s.replace('    assurance_section = None\n    markdown_path', '    assurance_section = None\n    platform_section = None\n    markdown_path')
old = "        if heading and re.match(r'^(?:Schnittstellen|Interfaces|Anschlüsse|Connections)\\b', structural, re.I):\n            interface_section = heading[1]"
new = "        if (heading and re.match(r'^(?:Schnittstellen|Interfaces|Anschlüsse|Connections)\\b', structural, re.I)) or re.match(r'^(?:Schnittstellen|Interfaces|Anschlüsse|Connections)\\s*:', structural, re.I):\n            interface_section = heading[1] if heading else ''\n        if heading and platform_section is not None and not heading[1].startswith(platform_section + '.'):\n            platform_section = None\n        if re.match(r'^(?:Plattform|Platform|Implementierung|Implementation)\\s*(?::|$)', structural, re.I):\n            platform_section = heading[1] if heading else ''\n        elif re.match(r'^(?:Aufgaben|Tasks|Responsibilities|Funktionen|Functions|Schnittstellen|Interfaces|Anschlüsse|Anforderungen|Requirements)\\s*:', structural, re.I):\n            platform_section = None"
assert old in s
s = s.replace(old, new)
old = "        elif function_section is not None and re.match(r'^(?:Schnittstellen|Interfaces|Anschlüsse|Sensorik|Aktorik|Hardware|Anforderungen|Requirements|Kommunikation|Energieversorgung)\\s*:\\s*$', text, re.I):"
new = "        elif function_section is not None and re.match(r'^(?:Schnittstellen|Interfaces|Anschlüsse|Sensorik|Aktorik|Hardware|Anforderungen|Requirements|Kommunikation|Energieversorgung|Plattform|Platform|Implementierung|Implementation)\\s*:', text, re.I):"
assert old in s
s = s.replace(old, new)
anchor = "        if interface_section is not None and not normative_row:"
s = s.replace(anchor, "        if platform_section is not None and not normative_row:\n            continue  # Platform metadata stays literal source context, not an executable function.\n        if not normative_row and re.match(r'^(?:Direkte?\\s+|Direct\\s+)?(?:Sensorlinks?|sensor links?|Punkt-zu-Punkt-Links|point-to-point links?)\\b', text, re.I):\n            continue\n" + anchor)
old = "(unit['policy']['kind'] == 'FUNCTION' and unit['function_scope']))"
new = "(unit['policy']['kind'] == 'FUNCTION' and unit['function_scope'] and (unit['function_heading'] or (pending and pending[0]['function_heading']))))"
assert old in s
s = s.replace(old, new)
p.write_text(s, encoding='utf-8')
p = S / 'backend/tests/test_qwen_document_intake.py'
s = p.read_text(encoding='utf-8') + '''

def test_separate_controller_responsibility_rows_keep_distinct_identity_and_exclude_platform_interfaces():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, resolve_document_references
    source = '2.3 ADAS Domain Controller (ADC)\\nAufgaben:\\nSensorfusion (Radar, Kamera)\\n\\nPerception (Objekte, Spuren)\\n\\nPlanning (Trajektorien, Manöver)\\nVehicle Control (Längs-/Querführung)\\nPlattform:\\nAUTOSAR Adaptive\\nPOSIX-OS\\nHochleistungs-SoC\\nSchnittstellen:\\nEthernet\\nDirekte Sensorlinks (GMSL, GigE)\\nAnforderungen:\\nREQ-ADC-01: ADC MUSS alle Quellen erhalten.'
    rows = document_source_references(source)
    units = document_component_sources(rows)
    functions = [unit for unit in units if unit['policy'] and unit['policy']['kind'] == 'FUNCTION']
    assert [unit['text'] for unit in functions] == ['Sensorfusion (Radar, Kamera)', 'Perception (Objekte, Spuren)', 'Planning (Trajektorien, Manöver)', 'Vehicle Control (Längs-/Querführung)']
    assert len({unit['source_ref'] for unit in functions}) == 4
    assert all(unit['required'] and 'source_rows' not in unit for unit in functions)
    facts = resolve_document_references({'components': [{'source_ref': unit['source_ref'], **unit['policy']} for unit in units if unit['required']], 'technologies': []}, rows)['components']
    assert len([fact for fact in facts if fact['kind'] == 'FUNCTION']) == 4
    assert all('AUTOSAR' not in fact['source_quote'] and 'Schnittstellen:' not in fact['source_quote'] for fact in facts)
    assert any(fact['kind'] == 'REQUIREMENT' and 'REQ-ADC-01' in fact['source_quote'] for fact in facts)
'''
p.write_text(s, encoding='utf-8')
path = OUT / 'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
proof = OUT.parent / 'document-clarification-repair-20261016/peer-canonical-post-semantic-controller-function-policy.json'
work['repair']['evidence'].append({'path': str(proof), 'sha256': hashlib.sha256(proof.read_bytes()).hexdigest()})
work['repair']['root_cause'] += ' Read-only vehicle counterprobe additionally proved adjacent plain responsibilities were coalesced and a missing Platform boundary absorbed runtime metadata into the same FUNCTION.'
work['repair']['acceptance_criteria'].append('Distinct plain controller duties remain distinct; platform and interface metadata cannot become executable function claims; named function subsections retain their descriptions.')
path.write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')

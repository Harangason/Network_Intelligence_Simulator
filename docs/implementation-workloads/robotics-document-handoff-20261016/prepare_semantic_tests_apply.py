"""Add native-failure regressions, then guard/apply the complete repair."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import sys

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
stage = OUT / 'semantic-staged'
p = stage / 'backend/tests/test_qwen_document_intake.py'
s = p.read_text(encoding='utf-8')
s = s.replace("assert len(functions) == 10", "assert len(functions) > 60\n    assert len({unit['source_quote'] for unit in functions}) == 10\n    assert all(unit['text'] in unit['source_quote'] for unit in functions)")
s += '''

@pytest.mark.parametrize('label', ['Fleet Manager', 'MES', 'Historian', 'Datenbank', 'Traceability', 'Alarmmanagement'])
def test_logical_architecture_service_does_not_assert_a_hardware_quantity(label):
    from backend.nis.agent.orchestration.project_intake import document_component_policy
    assert document_component_policy(label) == {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None}
    assert document_component_policy(label + '-Server')['role'] == 'CONTROLLER'


def test_combined_assurance_chapter_preserves_complete_requirements_across_windows():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    prefix = '# Robot\\n## 8. Safety, Security, Qualität und Betrieb\\n'
    paragraph = 'Die Sicherheits- und Betriebsargumentation behandelt Sensorblindheit und DCS/SIS-Ausfall.'
    units = document_component_sources(document_source_references(paragraph + '\\n## 9. Architektur\\nSafety PLC'), scope_prefix=prefix)
    assert units[0]['text'] == paragraph
    assert units[0]['policy'] == {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}
    assert units[1]['policy']['role'] == 'CONTROLLER'


def test_function_atoms_share_full_literal_list_citation_but_cannot_cover_one_another():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, resolve_document_references
    source = '# Robot\\n## Funktionen\\n- Bahnplanung, Kraftregelung, Power and Force Limiting, Tool Change und Diagnose..'
    rows = document_source_references(source)
    units = document_component_sources(rows)
    assert [unit['text'] for unit in units] == ['Bahnplanung', 'Kraftregelung', 'Power and Force Limiting', 'Tool Change', 'Diagnose']
    facts = resolve_document_references({'components': [{'source_ref': unit['source_ref'], **unit['policy']} for unit in units], 'technologies': []}, rows)['components']
    assert [fact['name'] for fact in facts] == [unit['text'] for unit in units]
    assert len({fact['source_quote'] for fact in facts}) == 1
    data = {**interpretation(), 'components': facts, 'technologies': []}
    assert len(validate_document_interpretation(data, source)['components']) == 5
    data['components'] = facts[:-1]
    with pytest.raises(ValueError, match='Quellenangabe fehlt'):
        validate_document_interpretation(data, source)


def test_test_only_bus_mentions_are_not_project_transport_evidence():
    from backend.nis.agent.orchestration.project_intake import document_transport_candidates, document_output_schema, DocumentInterpretation
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    profiles = DEFAULT_TECHNOLOGY_REGISTRY.profiles()
    prefix = '# Robot\\n## Verifikation und Testfälle\\n'
    text = '- TC-057-06: WLAN-Roamingfehler.\\n'
    assert document_transport_candidates(text, profiles, scope_prefix=prefix) == []
    schema = document_output_schema(text, DocumentInterpretation.model_json_schema(), scope_prefix=prefix)
    assert schema['properties']['technologies']['maxItems'] == 0
    full = '# Robot\\n## Schnittstellen\\nWLAN\\n## Verifikation und Testfälle\\n' + text
    assert [p['id'] for p in document_transport_candidates(full, profiles)] == ['wifi']


def test_unclassified_architecture_role_remains_other_in_the_model_grammar():
    from backend.nis.agent.orchestration.project_intake import document_output_schema, DocumentInterpretation
    schema = document_output_schema('# Robot\\n## Architecture\\nOptik', DocumentInterpretation.model_json_schema())
    branches = schema['$defs']['DocumentComponent']['oneOf']
    assert branches[0]['properties']['role']['enum'] == ['OTHER']
    assert 'INSTANCE' not in branches[0]['properties']['kind']['enum']
'''
p.write_text(s, encoding='utf-8')
p = stage / 'frontend/src/features/agent/lib/engineering-specification.test.mjs'
s = p.read_text(encoding='utf-8') + '''

test('PLC and Safety PLC have independent quantity questions in every source profile', () => {
  const components = ['A', 'B'].flatMap(profile => ['PLC', 'Safety PLC'].map(name => ({ name, kind: 'CATEGORY', role: 'CONTROLLER', quantity: null, source_quote: name, source_context: [profile, 'Architecture'] })));
  const questions = documentDeviceQuestions('PLC, Safety PLC', { interpretation: { components, technologies: [] } });
  assert.equal(questions.length, 4);
  assert.equal(new Set(questions.map(question => question.id)).size, 4);
});

test('a global source transport never selects the reviewed main computer connection', () => {
  const source = '# Robot\\n## Architecture\\nHauptrechner\\n## Interfaces\\nCAN, Ethernet';
  const fact = { name: 'Hauptrechner', kind: 'INSTANCE', role: 'CONTROLLER', quantity: 1, source_quote: 'Hauptrechner', source_context: ['Robot', 'Architecture'] };
  const equipment = reviewDocumentEquipment(source, { interpretation: { components: [fact], technologies: [] } }, {}, false);
  const spec = extractEngineeringSpecification(`${source}\\n- Dokument-Geräte: ${JSON.stringify(equipment)}`);
  assert.equal(spec.chains.length, 1);
  assert.equal(spec.chains[0].interface_type, 'Other');
});

test('shared function list evidence cannot assign Planning to the Perception duty host', () => {
  const quote = 'Perception, Planning';
  const facts = ['Perception', 'Planning'].map(name => ({ name, kind: 'FUNCTION', role: 'OTHER', quantity: null, source_quote: quote, source_context: ['Robot', 'Functions'] }));
  const owners = [{ name: 'ADC', source_context: ['Robot', 'Architecture'], duties: [{ source_quote: 'Perception' }] }];
  assert.deepEqual(documentSourceFunctionAssignments(facts, owners), { [documentFactIdentity(facts[0])]: 'ADC' });
});

test('reviewed declared controller retains only its own source duties and explicit interface', () => {
  const source = '2. Architektur\\n2.1 Controller Alpha (A)\\nAufgaben:\\n- Perception\\nSchnittstellen:\\nEthernet\\n2.2 Controller Beta (B)\\nAufgaben:\\n- Planning\\nSchnittstellen:\\nCAN';
  const components = ['Alpha (A)', 'Beta (B)'].map((name, index) => ({ name: `Controller ${name}`, kind: 'INSTANCE', role: 'CONTROLLER', quantity: 1, source_quote: `2.${index + 1} Controller ${name}`, source_context: ['2. Architektur', `2.${index + 1} Controller ${name}`] }));
  const equipment = reviewDocumentEquipment(source, { interpretation: { components, technologies: [] } }, {}, false);
  const spec = extractEngineeringSpecification(`${source}\\n- Dokument-Geräte: ${JSON.stringify(equipment)}`);
  assert.equal(spec.chains.length, 2);
  assert.equal(spec.chains[0].interface_type, 'Ethernet');
  assert.equal(spec.chains[1].interface_type, 'CAN');
  const first = JSON.stringify(spec.chains[0].configuration.source_scoped_functions);
  assert.match(first, /Perception/);
  assert.doesNotMatch(first, /Planning/);
});
'''
p.write_text(s, encoding='utf-8')

path = OUT / 'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
current = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in work['revision_after']}
assert current == work['revision_after']
work['revision_history'].append({'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'revision_after': current, 'scope': 'First complete native candidate FAILED; next semantic repair'})
work['revision_before'] = current
work['verification_phase'] = 'NATIVE_FAILED_SEMANTIC_REPAIR'
work['repair']['root_cause'] += ' Complete native result proved unrestricted roles for unclassified clauses, combined assurance headings not recognized, substring quantity-question suppression, project-wide interface fallback and function-list granularity/host evidence coupling.'
for name in ['native-verification.json', 'native-classification-review.json', 'native-equipment-fields.json', 'native-stack-cleanup.json']:
    evidence = OUT / name
    work['repair']['evidence'].append({'path': str(evidence), 'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()})
work['repair']['acceptance_criteria'] += ['Combined assurance narrative is retained as REQUIREMENT/OTHER.', 'Logical services do not imply physical hardware; unknown roles stay OTHER.', 'Every explicit function list member has a separate identity and complete citation; shared citations cannot transfer another function owner.', 'PLC/Safety PLC quantities remain distinct; reviewed physical connections never inherit a global bus.', 'Test-only technology citations cannot override real project interface evidence.']
path.write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
guard = subprocess.run([sys.executable, 'F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py', '--workload', str(path), 'before-apply'], capture_output=True, text=True, encoding='utf-8')
(OUT / 'semantic-before-apply-guard.json').write_text(guard.stdout, encoding='utf-8')
assert guard.returncode == 0 and json.loads(guard.stdout)['allowed'], guard.stdout + guard.stderr
changed = []
for relative in current:
    data = (stage / relative).read_bytes()
    if data != (ROOT / relative).read_bytes():
        (ROOT / relative).write_bytes(data)
        changed.append(relative)
    after = OUT / 'after' / relative
    after.parent.mkdir(parents=True, exist_ok=True)
    after.write_bytes(data)
work['revision_after'] = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in current}
work['semantic_repair'] = {'status': 'APPLIED_FOR_VERIFICATION', 'changed': changed}
path.write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(work['semantic_repair']))

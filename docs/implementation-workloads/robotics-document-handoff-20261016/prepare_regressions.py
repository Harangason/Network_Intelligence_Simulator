"""Prepare regression additions without changing active release inputs."""
from pathlib import Path
import shutil

OUT = Path(__file__).parent
FIXTURE = 'frontend/e2e/fixtures/document-intake-industrial-robotics.md'
target = OUT / 'staged' / FIXTURE
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(r'C:/Users/marti/PycharmProjects/Benchmark_Modelle/INDUSTRIEPORTFOLIO_100_KATEGORIENPAKET/D_INDUSTRIAL_ROBOTICS_054_063.md', target)
REL = 'backend/tests/test_qwen_document_intake.py'
text = (OUT / 'before' / REL).read_text(encoding='utf-8')
text += '''

def test_robotics_markdown_preserves_all_ten_function_scopes_and_110_requirements_without_test_hardware():
    import re
    from pathlib import Path
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    fixture = Path(__file__).resolve().parents[2] / 'frontend/e2e/fixtures/document-intake-industrial-robotics.md'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == '8fc201a55e8b0afeb7b708ac70abd0c72a7b25eb17d90fceca71d80a291f3cef'
    source = fixture.read_text(encoding='utf-8')
    units = document_component_sources(document_source_references(source))
    assert all(unit['text'] in source for unit in units)
    assert not any('TC-' in unit['text'] or unit['text'].startswith('|') for unit in units)
    functions = [unit for unit in units if unit['source_context'][-1:] == ['4. Funktionsbeschreibung']]
    assert len(functions) == 10
    assert all(unit['policy'] == {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None} and unit['required'] for unit in functions)
    requirement_ids = set(re.findall(r'REQ-\\d{3}-[A-Z]+-\\d{3}', '\\n'.join(unit['text'] for unit in units if unit['policy'] and unit['policy']['kind'] == 'REQUIREMENT')))
    assert requirement_ids == set(re.findall(r'REQ-\\d{3}-[A-Z]+-\\d{3}', source))
    assert len(requirement_ids) == 110
    names = [unit['text'] for unit in units]
    assert 'Teach Pendant' in names and 'Endeffektor' in names
    encoders = [unit for unit in units if unit['text'] == 'Encoder']
    assert len(encoders) >= 2 and len({tuple(unit['source_context']) for unit in encoders}) == len(encoders)


def test_markdown_test_sections_override_hardware_words_and_normative_language_across_windows():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    prefix = '# Building\\n## Verification and test cases\\n'
    source = '- TC-BLD-01: Sensor drift must be detected.\\n## Architecture\\nRoomcontroller\\n## Functions\\nSensor fault handling\\n## Requirements\\nREQ-BLD-01: The room controller shall report faults.'
    units = document_component_sources(document_source_references(source), scope_prefix=prefix)
    assert not any('TC-BLD' in unit['text'] for unit in units)
    assert [unit['policy']['kind'] for unit in units] == ['CATEGORY', 'FUNCTION', 'REQUIREMENT']
    assert units[1]['source_context'] == ['Building', 'Functions']


@pytest.mark.parametrize('section', ['Safety', 'Security', 'Sicherheit', 'Systemkontext', 'Operating modes'])
def test_explicit_safety_and_context_requirements_survive_without_fault_scenario_hardware(section):
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    source = f'# {section}\\nREQ-SAFE-01: Das System MUSS Sensorausfälle erkennen.\\n'
    units = document_component_sources(document_source_references(source))
    assert len(units) == 1
    assert units[0]['policy'] == {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}
    assert units[0]['text'] == 'REQ-SAFE-01: Das System MUSS Sensorausfälle erkennen.'
    assert units[0]['source_context'] == [section]


def test_a_safety_plc_in_architecture_is_a_controller_and_not_a_safety_section():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    units = document_component_sources(document_source_references('# Robot\\n## Architecture\\nSafety-PLC\\n'))
    assert len(units) == 1
    assert units[0]['policy'] == {'kind': 'CATEGORY', 'role': 'CONTROLLER', 'quantity': None}


def _reviewed_room_document():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, resolve_document_references
    source = '# Building\\n## Architecture\\nRaumcontroller\\n## Functions\\nRaumtemperatur regeln.\\n## Requirements\\nREQ-BLD-01: The room controller shall report faults.'
    rows = document_source_references(source)
    units = document_component_sources(rows)
    facts = resolve_document_references({'components': [{'source_ref': unit['source_ref'], **unit['policy']} for unit in units], 'technologies': []}, rows)['components']
    envelope = {'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'source_chars': len(source),
                'source_name': 'building.md', 'source_text': source, 'facts': facts, 'technologies': [], 'questions': [], 'answers': []}
    return source, envelope


def test_reviewed_document_handoff_retains_every_typed_fact_in_proposal_source_evidence():
    from backend.nis.agent.orchestration.project_intake import reviewed_document_evidence
    source, envelope = _reviewed_room_document()
    evidence = reviewed_document_evidence(source + '\\n- Dokument-Geräte: ' + json.dumps(envelope))
    assert evidence['components'] == envelope['facts']
    assert {fact['kind'] for fact in evidence['components']} == {'CATEGORY', 'FUNCTION', 'REQUIREMENT'}
    assert evidence['source_sha256'] == envelope['source_sha256']
    assert evidence['canonical_writes'] is False and evidence['approval_required'] is True


@pytest.mark.parametrize('change', ['hash', 'omit_requirement', 'context', 'hardware_function'])
def test_reviewed_document_handoff_rejects_changed_source_incomplete_facts_and_wrong_context(change):
    from backend.nis.agent.orchestration.project_intake import reviewed_document_evidence
    source, envelope = _reviewed_room_document()
    if change == 'hash':
        envelope['source_sha256'] = '0' * 64
    elif change == 'omit_requirement':
        envelope['facts'] = [fact for fact in envelope['facts'] if fact['kind'] != 'REQUIREMENT']
    elif change == 'context':
        envelope['facts'][0]['source_context'] = ['An unrelated building']
    else:
        envelope['facts'][1].update(kind='CATEGORY', role='CONTROLLER')
    with pytest.raises(ValueError):
        reviewed_document_evidence(source + '\\n- Dokument-Geräte: ' + json.dumps(envelope))


def test_same_component_name_in_different_source_contexts_is_not_deduplicated():
    from backend.nis.agent.orchestration.project_intake import compose_document_proposal
    component = {'name': 'Encoder', 'kind': 'CATEGORY', 'role': 'SENSOR', 'quantity': None, 'source_quote': 'Encoder'}
    parts = [{'components': [{**component, 'source_context': ['Robot A', 'Architecture']}], 'technologies': []},
             {'components': [{**component, 'source_context': ['Robot B', 'Architecture']}], 'technologies': []}]
    assert len(compose_document_proposal(parts)['components']) == 2


def test_markdown_context_validation_survives_different_normative_grouping_at_window_boundaries():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, resolve_document_references, compose_document_proposal
    lines = ['# Building\\n', '## Requirements\\n', *[f'REQ-BLD-{index:03d}: The controller shall retain this original requirement and its complete source text.\\n' for index in range(12)]]
    source = ''.join(lines)
    first = ''.join(lines[:5])
    pieces = [first, source[len(first):]]
    parts, prefix = [], ''
    for piece in pieces:
        rows = document_source_references(piece)
        units = document_component_sources(rows, scope_prefix=prefix)
        parts.append(resolve_document_references({'components': [{'source_ref': unit['source_ref'], **unit['policy']} for unit in units], 'technologies': []}, rows, scope_prefix=prefix))
        prefix += piece
    combined = compose_document_proposal(parts)
    accepted = validate_document_interpretation(combined, source, aggregate=True)
    assert all(fact['source_context'] == ['Building', 'Requirements'] for fact in accepted['components'])
    assert all(f'REQ-BLD-{index:03d}' in '\\n'.join(fact['source_quote'] for fact in accepted['components']) for index in range(12))
'''
(OUT / 'staged' / REL).write_text(text, encoding='utf-8')

REL = 'frontend/src/features/agent/lib/engineering-specification.test.mjs'
text = (OUT / 'before' / REL).read_text(encoding='utf-8')
text += '''

test('reviewed typed document facts replace lexical counts and retain functions and requirements', () => {
  const source = '# Robot\\n## Architecture\\nHauptrechner\\nEncoder\\nGelenkaktuatoren\\n## Functions\\nSensorfehler erkennen\\n## Requirements\\nREQ-ROBOT-001: The system shall monitor 6 controllers and 2 sensors.';
  const facts = [
    { name: 'Hauptrechner', kind: 'INSTANCE', role: 'CONTROLLER', quantity: 1, source_quote: 'Hauptrechner', source_context: ['Robot', 'Architecture'] },
    { name: 'Encoder', kind: 'CATEGORY', role: 'SENSOR', quantity: null, source_quote: 'Encoder', source_context: ['Robot', 'Architecture'] },
    { name: 'Gelenkaktuatoren', kind: 'CATEGORY', role: 'ACTUATOR', quantity: null, source_quote: 'Gelenkaktuatoren', source_context: ['Robot', 'Architecture'] },
    { name: 'Sensorfehler erkennen', kind: 'FUNCTION', role: 'OTHER', quantity: null, source_quote: 'Sensorfehler erkennen', source_context: ['Robot', 'Functions'] },
    { name: 'REQ-ROBOT-001', kind: 'REQUIREMENT', role: 'OTHER', quantity: null, source_quote: 'REQ-ROBOT-001: The system shall monitor 6 controllers and 2 sensors.', source_context: ['Robot', 'Requirements'] },
  ];
  const proposal = { source_sha256: 'a'.repeat(64), source_chars: source.length, interpretation: { components: facts, technologies: [] } };
  const equipment = reviewDocumentEquipment(source, proposal, {}, false);
  const prompt = `${source}\\n- Dokument-Geräte: ${JSON.stringify(equipment)}`;
  const roundtrip = readReviewedDocumentEquipment(prompt);
  assert.deepEqual(roundtrip.facts, facts);
  assert.equal(roundtrip.source_text, source);
  const spec = extractEngineeringSpecification(prompt);
  assert.equal(spec.targetCounts.ecus, 1);
  assert.equal(spec.targetCounts.sensors, 0);
  assert.equal(spec.targetCounts.actuators, 0);
  assert.deepEqual([...new Set(spec.chains.map(chain => chain.hardware_name))], ['Hauptrechner']);
  assert.equal(spec.unresolvedInventoryGroups.length, 2);
  assert.ok(spec.unresolvedInventoryGroups.some(finding => finding.includes('Encoder')));
});

test('equal device labels from separate profiles retain distinct clarification and inventory identities', () => {
  const source = '# Robots\\n## 054. Arm\\n### Architecture\\nEncoder\\n## 056. Mobile\\n### Architecture\\nEncoder';
  const components = [
    { name: 'Encoder', kind: 'CATEGORY', role: 'SENSOR', quantity: null, source_quote: 'Encoder', source_context: ['Robots', '054. Arm', 'Architecture'] },
    { name: 'Encoder', kind: 'CATEGORY', role: 'SENSOR', quantity: null, source_quote: 'Encoder', source_context: ['Robots', '056. Mobile', 'Architecture'] },
  ];
  const proposal = { source_sha256: 'a'.repeat(64), interpretation: { components, technologies: [] } };
  const questions = documentDeviceQuestions(source, proposal);
  assert.equal(questions.length, 2);
  assert.notEqual(questions[0].id, questions[1].id);
  const partial = reviewDocumentEquipment(source, proposal, { [questions[0].id]: '1' }, false);
  const partialSpec = extractEngineeringSpecification(`${source}\\n- Dokument-Geräte: ${JSON.stringify(partial)}`);
  assert.deepEqual(partialSpec.chains.map(chain => chain.hardware_name), ['Encoder [054]']);
  const equipment = reviewDocumentEquipment(source, proposal, Object.fromEntries(questions.map(question => [question.id, '1'])), false);
  const spec = extractEngineeringSpecification(`${source}\\n- Dokument-Geräte: ${JSON.stringify(equipment)}`);
  assert.equal(new Set(spec.chains.map(chain => chain.hardware_name)).size, 2);
  assert.equal(spec.targetCounts.sensors, 2);
  assert.equal(spec.unresolvedInventoryGroups.length, 0);
});

test('unknown source device roles need an explicit type answer rather than a controller fallback', () => {
  const source = 'Architecture: Optical unit';
  const proposal = { source_sha256: 'a'.repeat(64), interpretation: { components: [
    { name: 'Optical unit', kind: 'CATEGORY', role: 'OTHER', quantity: null, source_quote: 'Optical unit' },
  ], technologies: [] } };
  const [question] = documentDeviceQuestions(source, proposal);
  assert.equal(question.role, 'OTHER');
  assert.throws(() => reviewDocumentEquipment(source, proposal, { [question.id]: '1' }, false), /Geräteart/);
  const equipment = reviewDocumentEquipment(source, proposal, { [question.id]: '1' }, false, { [question.id]: 'SENSOR' });
  const spec = extractEngineeringSpecification(`${source}\\n- Dokument-Geräte: ${JSON.stringify(equipment)}`);
  assert.equal(spec.targetCounts.sensors, 1);
  assert.equal(spec.targetCounts.ecus, 0);
});
'''
(OUT / 'staged' / REL).write_text(text, encoding='utf-8')
print('Staged regressions and byte-identical original fixture prepared.')

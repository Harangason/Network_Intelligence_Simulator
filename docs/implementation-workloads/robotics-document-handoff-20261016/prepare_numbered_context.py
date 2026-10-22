"""Preserve numeric-outline identity using literal source context."""
from pathlib import Path

OUT = Path(__file__).parent


def edit(relative, transform):
    path = OUT / 'staged' / relative
    path.write_text(transform(path.read_text(encoding='utf-8')), encoding='utf-8')


def replace(text, old, new):
    assert text.count(old) == 1, (old[:100], text.count(old))
    return text.replace(old, new)


def intake(text):
    helpers = '''def _document_context_heading(text: str) -> bool:
    """Numbered outlines are scopes; explicit quantity rows are not headings."""
    if not re.match(r'^\\d+(?:\\.\\d+)*[.)]?\\s+.+', text):
        return False
    if re.match(r'^\\d+\\s+', text):
        policy = document_component_policy(text)
        if policy and policy['kind'] == 'INSTANCE':
            return False
    return True


def document_source_contexts(source: str):
    """Bind Markdown and numeric headings to their original character offsets."""
    offsets, contexts, markdown_path, numbered_path = [0], [[]], [], []
    offset = 0
    for line in source.splitlines(keepends=True):
        text = line.strip()
        markdown = re.match(r'^(#{1,6})\\s+(.+?)(?:\\s+#+)?$', text)
        heading = re.match(r'^(\\d+(?:\\.\\d+)*)[.)]?\\s+(.+)', text)
        if markdown:
            level = len(markdown[1])
            markdown_path = [entry for entry in markdown_path if entry[0] < level]
            markdown_path.append((level, markdown[2]))
            numbered_path = []
        elif heading and _document_context_heading(text):
            identifier = heading[1]
            numbered_path = [entry for entry in numbered_path if identifier.startswith(entry[0] + '.')]
            numbered_path.append((identifier, text))
        else:
            offset += len(line)
            continue
        # Numeric headings may themselves declare a controller. Their context
        # starts on the heading row, rather than after its newline.
        offsets.append(offset)
        contexts.append([entry[1] for entry in [*markdown_path, *numbered_path]])
        offset += len(line)
    return offsets, contexts


def document_source_scope(context: list[str]) -> list[str]:
    """Remove only a semantic section caption, retaining named device scopes."""
    if not context:
        return []
    label = re.sub(r'^\\d+(?:\\.\\d+)*[.)]?\\s+', '', context[-1]).rstrip(':').strip()
    if re.fullmatch(r'(?:Architektur|Architecture|Hardware(?:komponenten| components)?|Systemfunktionen|Funktionsbeschreibung|Functional description|Funktionen|Functions|Aufgaben|Responsibilities|(?:Referenz[- ]?)?Anforderungen|(?:Reference )?Requirements|Schnittstellen|Interfaces|Anschlüsse|Connections)', label, re.I):
        return context[:-1]
    return context[:]


'''
    text = replace(text, "source_context: list[str] = Field(default_factory=list, max_length=6)",
                   "source_context: list[str] = Field(default_factory=list, max_length=64)")
    text = replace(text, "def document_component_sources(rows: list, *, scope_prefix=''):",
                   helpers + "def document_component_sources(rows: list, *, scope_prefix=''):")
    text = replace(text, '    markdown_path = []\n    heading_sequence = 0',
                   '    markdown_path = []\n    numbered_path = []\n    heading_sequence = 0')
    text = replace(text, "            heading = {1: '.'.join(entry[2] for entry in markdown_path), 2: structural}",
                   "            heading = {1: '.'.join(entry[2] for entry in markdown_path), 2: structural}\n            numbered_path = []\n        elif heading and _document_context_heading(logical):\n            identifier = heading[1]\n            numbered_path = [entry for entry in numbered_path if identifier.startswith(entry[0] + '.')]\n            numbered_path.append((identifier, logical))")
    text = replace(text, "'source_context': [entry[1] for entry in markdown_path],",
                   "'source_context': [entry[1] for entry in [*markdown_path, *numbered_path]],")
    start = text.index('    context_offsets, context_values, context_path = [0], [[]], []\n')
    end = text.index('    context_cache = {}\n', start)
    text = text[:start] + '    context_offsets, context_values = document_source_contexts(scope_prefix + source)\n' + text[end:]
    text = replace(text, "        contexts = context_cache[component.source_quote]\n        if component.source_context", """        contexts = context_cache[component.source_quote]
        unique_contexts = {tuple(context) for context in contexts}
        if not component.source_context and len(unique_contexts) == 1:
            component.source_context = list(next(iter(unique_contexts)))
        elif 'source_context' not in component.model_fields_set and len(unique_contexts) > 1:
            semantic_errors.append(f'{component.name}: Abschnittskontext fehlt bei mehrdeutiger Quellenangabe.')
        if component.source_context""")
    return text


edit('backend/nis/agent/orchestration/project_intake.py', intake)


def clarification(text):
    text = replace(text, 'export function documentFactIdentity(fact: DocumentFact) {', '''export function documentSourceScope(context: string[]) {
  if (!context.length) return [];
  const label = context.at(-1)!.replace(/^\\d+(?:\\.\\d+)*[.)]?\\s+/u, '').replace(/:\\s*$/u, '').trim();
  return /^(?:Architektur|Architecture|Hardware(?:komponenten| components)?|Systemfunktionen|Funktionsbeschreibung|Functional description|Funktionen|Functions|Aufgaben|Responsibilities|(?:Referenz[- ]?)?Anforderungen|(?:Reference )?Requirements|Schnittstellen|Interfaces|Anschlüsse|Connections)$/iu.test(label) ? context.slice(0, -1) : [...context];
}

function documentOwnerScopeMatches(owner: string[], fact: string[]) {
  const hostScope = documentSourceScope(owner), factScope = documentSourceScope(fact);
  return JSON.stringify(hostScope) === JSON.stringify(factScope)
    || (hostScope.length > 0 && hostScope.length < factScope.length && hostScope.every((label, index) => factScope[index] === label));
}

export function documentFactIdentity(fact: DocumentFact) {''')
    text = replace(text, "JSON.stringify((owner.source_context ?? []).slice(0, -1)) === JSON.stringify((fact.source_context ?? []).slice(0, -1))",
                   "documentOwnerScopeMatches(owner.source_context ?? [], fact.source_context ?? [])")
    start = text.index('  const contexts = new Set(peers.filter(')
    end = text.index('\n}\n\n/** Counts describe source facts;', start)
    text = text[:start] + '''  const contexts = [...new Map(peers.filter(peer => (peer.name ?? peer.label) === name)
    .map(peer => [JSON.stringify(peer.source_context ?? []), peer.source_context ?? []])).values()];
  const own = item.source_context ?? [];
  if (contexts.length < 2 || !own.length) return name;
  const identityPath = (context: string[]) => {
    const scope = documentSourceScope(context);
    return contexts.some(other => JSON.stringify(other) !== JSON.stringify(context)
      && JSON.stringify(documentSourceScope(other)) === JSON.stringify(scope)) ? context : scope;
  };
  const path = identityPath(own);
  const tokens = (context: string[]) => identityPath(context).map(label => label.match(/^\\d+(?:\\.\\d+)*/)?.[0] ?? label);
  const ownTokens = tokens(own);
  for (let width = 1; width <= ownTokens.length; width += 1) {
    const suffix = ownTokens.slice(-width).join('/');
    if (!contexts.some(other => JSON.stringify(other) !== JSON.stringify(own) && tokens(other).slice(-width).join('/') === suffix)) return `${name} [${suffix}]`;
  }
  return `${name} [${JSON.stringify(path)}]`;''' + text[end:]
    return text


edit('frontend/src/features/agent/lib/document-clarification.ts', clarification)


def generator(text):
    text = replace(text, '    from backend.nis.agent.orchestration.project_intake import document_fact_identity\n',
                   '    from backend.nis.agent.orchestration.project_intake import document_fact_identity, document_source_scope\n')
    text = replace(text, "            if context[:-1] != fact.get('source_context', [])[:-1]:\n                continue", """            host_scope = document_source_scope(context)
            fact_scope = document_source_scope(fact.get('source_context', []))
            if host_scope != fact_scope and not (host_scope and fact_scope[:len(host_scope)] == host_scope):
                continue""")
    return text


edit('backend/nis/agent/tools/wizard_generation.py', generator)

relative = 'backend/tests/test_qwen_document_intake.py'
path = OUT / 'staged' / relative
text = path.read_text(encoding='utf-8') + '''


def test_numeric_plain_text_profiles_preserve_equal_hardware_and_function_facts():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, resolve_document_references, compose_document_proposal
    source = '1. Anlage Nord\\n1.1 Architektur\\nController: SPS\\n1.2 Funktionen\\nRegelung\\n2. Anlage Süd\\n2.1 Architektur\\nController: SPS\\n2.2 Funktionen\\nRegelung\\n'
    rows = document_source_references(source)
    units = document_component_sources(rows)
    facts = resolve_document_references({'components': [{'source_ref': unit['source_ref'], **unit['policy']} for unit in units], 'technologies': []}, rows)['components']
    assert [fact['source_context'] for fact in facts] == [
        ['1. Anlage Nord', '1.1 Architektur'], ['1. Anlage Nord', '1.2 Funktionen'],
        ['2. Anlage Süd', '2.1 Architektur'], ['2. Anlage Süd', '2.2 Funktionen']]
    combined = compose_document_proposal([{'components': [fact], 'technologies': []} for fact in facts])
    assert len(combined['components']) == 4
    assert len(validate_document_interpretation(combined, source, aggregate=True)['components']) == 4


def test_numeric_context_covers_declaring_heading_and_survives_window_prefix():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, resolve_document_references
    source = '1. Architektur\\n1.1 Hauptrechner\\n1.1.1 Aufgaben\\nBahnplanung\\n'
    rows = document_source_references(source)
    units = document_component_sources(rows)
    facts = resolve_document_references({'components': [{'source_ref': unit['source_ref'], **unit['policy']} for unit in units], 'technologies': []}, rows)['components']
    data = {**interpretation(), 'components': facts, 'technologies': []}
    assert validate_document_interpretation(data, source)['components'] == facts
    prefix = '1. Anlage Nord\\n1.1 Architektur\\n'
    unit = document_component_sources(document_source_references('Controller: SPS\\n'), scope_prefix=prefix)[0]
    assert unit['source_context'] == ['1. Anlage Nord', '1.1 Architektur']


def test_missing_numeric_context_is_derived_only_for_an_unambiguous_literal_quote():
    data = {**interpretation(), 'components': [{'name': 'SPS', 'source_quote': 'Controller: SPS', 'kind': 'CATEGORY', 'role': 'CONTROLLER', 'quantity': None}], 'technologies': []}
    source = '1. Anlage Nord\\n1.1 Architektur\\nController: SPS\\n'
    result = validate_document_interpretation(data, source)
    assert result['components'][0]['source_context'] == ['1. Anlage Nord', '1.1 Architektur']
    with pytest.raises(ValueError, match='Abschnittskontext'):
        validate_document_interpretation(data, source + '2. Anlage Süd\\n2.1 Architektur\\nController: SPS\\n')


def test_explicit_hardware_quantity_line_does_not_replace_the_numeric_profile_context():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    source = '1. Anlage Nord\\n1.1 Architektur\\n3 Sensoren\\n'
    units = document_component_sources(document_source_references(source))
    assert units[0]['source_context'] == ['1. Anlage Nord', '1.1 Architektur']
    assert units[0]['policy']['quantity'] == 3
'''
path.write_text(text, encoding='utf-8')

relative = 'frontend/src/features/agent/lib/engineering-specification.test.mjs'
path = OUT / 'staged' / relative
text = path.read_text(encoding='utf-8') + '''

test('numeric source scopes preserve literal controller responsibility across sibling hosts', () => {
  const quote = 'Perception (Objekte, Spuren)';
  const fact = { name: 'Perception', kind: 'FUNCTION', role: 'OTHER', quantity: null, source_quote: quote,
    source_context: ['2. Architektur', '2.3 ADAS Domain Controller (ADC)', '2.3.1 Aufgaben'] };
  const owners = [
    { name: 'ADC', source_context: ['2. Architektur', '2.3 ADAS Domain Controller (ADC)'], duties: [{ source_quote: quote }] },
    { name: 'CGW', source_context: ['2. Architektur', '2.1 Central Gateway'], duties: [{ source_quote: quote }] },
  ];
  assert.deepEqual(documentSourceFunctionAssignments([fact], owners), { [documentFactIdentity(fact)]: 'ADC' });
});

test('same numeric profile ordinal in different roots keeps unique stable device names', () => {
  const source = '# Industry A\\n## 054. Arm\\n### Architecture\\nEncoder\\n# Industry B\\n## 054. Other\\n### Architecture\\nEncoder';
  const components = [
    { name: 'Encoder', kind: 'CATEGORY', role: 'SENSOR', quantity: null, source_quote: 'Encoder', source_context: ['Industry A', '054. Arm', 'Architecture'] },
    { name: 'Encoder', kind: 'CATEGORY', role: 'SENSOR', quantity: null, source_quote: 'Encoder', source_context: ['Industry B', '054. Other', 'Architecture'] },
  ];
  const proposal = { interpretation: { components, technologies: [] } };
  const questions = documentDeviceQuestions(source, proposal);
  const partial = reviewDocumentEquipment(source, proposal, { [questions[0].id]: '1' }, false);
  const first = extractEngineeringSpecification(`${source}\\n- Dokument-Geräte: ${JSON.stringify(partial)}`);
  assert.deepEqual(first.chains.map(chain => chain.hardware_name), ['Encoder [Industry A/054]']);
  const all = reviewDocumentEquipment(source, proposal, Object.fromEntries(questions.map(question => [question.id, '1'])), false);
  const complete = extractEngineeringSpecification(`${source}\\n- Dokument-Geräte: ${JSON.stringify(all)}`);
  assert.equal(complete.targetCounts.sensors, 2);
  assert.ok(complete.chains.some(chain => chain.hardware_name === first.chains[0].hardware_name));
  assert.equal(new Set(complete.chains.map(chain => chain.hardware_name)).size, 2);
});
'''
path.write_text(text, encoding='utf-8')

relative = 'backend/tests/test_wizard_generation.py'
path = OUT / 'staged' / relative
text = path.read_text(encoding='utf-8') + '''


def test_numeric_controller_heading_and_child_tasks_keep_the_same_explicit_function_host():
    quote = 'Perception (Objekte, Spuren)'
    fact = {'name': 'Perception', 'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None, 'source_quote': quote,
            'source_context': ['2. Architektur', '2.3 ADAS Domain Controller (ADC)', '2.3.1 Aufgaben']}
    evidence = {'components': [fact], 'source_sha256': 'a' * 64}
    def host(name, scope):
        return {'hardware_name': name, 'device_type': 'ECU', 'configuration': {
            'source_scoped_functions': [{'source_quote': quote}], 'document_equipment_evidence': {'source_context': scope}}}
    chains = [host('ADC', ['2. Architektur', '2.3 ADAS Domain Controller (ADC)']),
              host('CGW', ['2. Architektur', '2.1 Central Gateway'])]
    result = wizard_generation._reviewed_document_functions(evidence, ['adc', 'cgw'], chains)
    assert result[0]['host'] == 'adc'
    assert result[0]['assignment_source'] == 'source_scoped_function'
'''
path.write_text(text, encoding='utf-8')
print('Numeric contexts, stable identity and explicit host scopes staged.')

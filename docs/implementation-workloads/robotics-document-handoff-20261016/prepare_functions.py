"""Extend staged reviewed facts with explicit function ownership, without writes."""
from pathlib import Path
import hashlib
import json

OUT = Path(__file__).parent


def edit(relative, replacements):
    path = OUT / 'staged' / relative
    text = path.read_text(encoding='utf-8')
    for old, new in replacements:
        assert text.count(old) == 1, (relative, old[:100], text.count(old))
        text = text.replace(old, new)
    path.write_text(text, encoding='utf-8')


edit('frontend/src/features/agent/lib/document-clarification.ts', [
    ('  facts?: DocumentFact[];', '  facts?: DocumentFact[];\n  function_assignments?: Record<string, string>;'),
    ('roleAnswers: Record<string, string> = {}): ReviewedDocumentEquipment',
     'roleAnswers: Record<string, string> = {}, functionAnswers: Record<string, string> = {}): ReviewedDocumentEquipment'),
    ('facts: structuredClone(proposal.interpretation.components), technologies:',
     "function_assignments: Object.fromEntries(proposal.interpretation.components.filter(fact => fact.kind === 'FUNCTION')\n        .map(fact => [documentFactIdentity(fact), functionAnswers[documentFactIdentity(fact)]?.trim() ?? '']).filter(([, host]) => host)),\n      facts: structuredClone(proposal.interpretation.components), technologies:"),
    ("    if (!Array.isArray(equipment.technologies)",
     "    if (equipment.function_assignments !== undefined && (!equipment.function_assignments || typeof equipment.function_assignments !== 'object' || Array.isArray(equipment.function_assignments)\n      || Object.entries(equipment.function_assignments).some(([id, host]) => typeof host !== 'string' || !host.trim() || !equipment.facts?.some(fact => fact.kind === 'FUNCTION' && documentFactIdentity(fact) === id)))) throw new Error('Unbelegte Funktionszuordnung.');\n    if (!Array.isArray(equipment.technologies)"),
    ('/** Equal labels in separate source systems remain separate participants. */',
     '''export function documentFactIdentity(fact: DocumentFact) {
  return JSON.stringify([fact.kind, fact.source_context ?? [], fact.source_quote, fact.name]);
}

/** Reuse only unique, literal responsibilities already scoped to real hosts. */
export function documentSourceFunctionAssignments(facts: DocumentFact[], owners: {
  name: string; source_context?: string[]; duties: { source_quote: string }[];
}[]) {
  const result: Record<string, string> = {};
  for (const fact of facts.filter(fact => fact.kind === 'FUNCTION')) {
    const candidates = owners.filter(owner => JSON.stringify((owner.source_context ?? []).slice(0, -1)) === JSON.stringify((fact.source_context ?? []).slice(0, -1))
      && owner.duties.some(duty => duty.source_quote.length >= 3 && fact.source_quote.includes(duty.source_quote)));
    const names = [...new Set(candidates.map(owner => owner.name))];
    if (names.length === 1) result[documentFactIdentity(fact)] = names[0];
  }
  return result;
}

/** Equal labels in separate source systems remain separate participants. */'''),
])

edit('frontend/src/features/agent/ui/agent-chat-core.tsx', [
    ('DOCUMENT_EQUIPMENT_MARKER, documentEvidenceCounts,', 'DOCUMENT_EQUIPMENT_MARKER, documentSourceFunctionAssignments, documentFactIdentity, documentEvidenceCounts,'),
    ('  const [documentMinimum, setDocumentMinimum] = useState(false);',
     "  const [documentMinimum, setDocumentMinimum] = useState(false);\n  const [documentFunctions, setDocumentFunctions] = useState<{ source: string; project: string; values: Record<string, string> }>({ source: '', project: '', values: {} });"),
    ('  function adoptDocumentEquipment() {',
     "  const activeDocumentFunctions = { ...(activeDocumentEquipment?.function_assignments ?? {}), ...(documentFunctions.source === documentSourceIdentity && documentFunctions.project === projectId ? documentFunctions.values : {}) };\n  function adoptDocumentEquipment() {"),
    ('documentMinimum, activeDocumentRoles)', 'documentMinimum, activeDocumentRoles, { ...documentScopedFunctionAssignments, ...activeDocumentFunctions })'),
    ('  const plannedInventory = new Map(',
     """  const documentControllerChains = plannedEquipment.chains.filter(chain => isEngineeringControllerDevice(chain.device_type));
  const documentFunctionHosts = [...new Set(documentControllerChains.map(chain => chain.hardware_name))];
  const documentFunctionFacts = activeDocumentEquipment?.facts?.filter(fact => fact.kind === 'FUNCTION') ?? [];
  const documentScopedFunctionAssignments = documentSourceFunctionAssignments(currentDocumentProposal?.interpretation.components ?? activeDocumentEquipment?.facts ?? [], documentControllerChains.map(chain => {
    const configuration = (chain.configuration ?? {}) as { source_scoped_functions?: { source_quote: string }[]; document_equipment_evidence?: { source_context?: string[] } };
    return { name: chain.hardware_name, source_context: configuration.document_equipment_evidence?.source_context, duties: configuration.source_scoped_functions ?? [] };
  }));
  const unresolvedDocumentFunctions = documentFunctionFacts.filter(fact => !documentFunctionHosts.includes(activeDocumentEquipment?.function_assignments?.[documentFactIdentity(fact)] ?? ''));
  const plannedInventory = new Map("""),
    ('          {documentQuestions.length > 0 && <section', '''          {documentFunctionFacts.length > 0 && <section className="agent-cluster-review" aria-label="Funktionen zuordnen">
            <h3>Ausführende Controller der Funktionen</h3>
            <p>Quellengebundene Aufgaben behalten ihren belegten Controller. Wähle bei offenen Zuordnungen den ausführenden Controller.</p>
            {documentFunctionFacts.map(fact => <label key={documentFactIdentity(fact)} className="agent-device-choice"><span>{fact.name}</span>
              {fact.source_context?.length ? <small>{fact.source_context.join(' / ')}</small> : null}
              <select aria-label={`Controller für Funktion ${fact.name}`} disabled={effectiveBusy}
                value={activeDocumentFunctions[documentFactIdentity(fact)] ?? activeDocumentEquipment?.function_assignments?.[documentFactIdentity(fact)] ?? ''}
                onChange={event => setDocumentFunctions({ source: documentSourceIdentity, project: projectId, values: { ...activeDocumentFunctions, [documentFactIdentity(fact)]: event.target.value } })}>
                <option value="">Zuordnung offen</option>{documentFunctionHosts.map(host => <option key={host} value={host}>{host}</option>)}
              </select>
            </label>)}
            <button className="button secondary" type="button" disabled={effectiveBusy} onClick={adoptDocumentEquipment}>Funktionszuordnungen übernehmen</button>
          </section>}
          {documentQuestions.length > 0 && <section'''),
    ('  const startBlockers = [', "  const startBlockers = [\n    ...(unresolvedDocumentFunctions.length ? [{ step: 'equipment', text: `Ausführenden Controller für ${unresolvedDocumentFunctions.length} Funktionsbefunde festlegen und übernehmen.` }] : []),"),
])

edit('backend/nis/agent/orchestration/project_intake.py', [
    ('def reviewed_document_evidence(prompt: str):', '''def document_fact_identity(fact: dict) -> str:
    """Cross-language identity of a literal typed source fact and its scope."""
    import json
    return json.dumps([fact['kind'], fact.get('source_context', []), fact['source_quote'], fact['name']],
                      ensure_ascii=False, separators=(',', ':'))


def reviewed_document_evidence(prompt: str):'''),
    ("    return {'source': 'reviewed_document'", """    assignments = value.get('function_assignments', {})
    function_ids = {document_fact_identity(fact) for fact in interpretation['components'] if fact['kind'] == 'FUNCTION'}
    if (not isinstance(assignments, dict) or any(key not in function_ids or not isinstance(host, str)
            or not host.strip() for key, host in assignments.items())):
        raise ValueError('Unbelegte Funktionszuordnung in den Dokumentbefunden.')
    return {'source': 'reviewed_document'"""),
    ("            'excluded_questions': value.get('excluded_questions', []),", "            'excluded_questions': value.get('excluded_questions', []), 'function_assignments': assignments,"),
])

edit('backend/nis/agent/tools/wizard_generation.py', [
    ("    # The selected cluster technology is the ECU/Gateway backbone.", '''    # Typed document duties have no inferred owner, even with a single host.
    # Source evidence remains complete; execution and dependencies remain open.
    for duty in _reviewed_document_functions(document_evidence, function_hosts, spec['chains']):
        host_ref = hardware_refs[duty['host']]
        linked = []
        for row in [*(change['data'] for change in changes if change['object_type'] == 'Function'), *existing['Function']]:
            configuration = row.get('configuration') or {}
            quote = (configuration.get('source_scoped_function') or {}).get('source_quote', '')
            if row.get('hardware_node_id') == host_ref and len(quote) >= 3 and quote in duty['source_quote']:
                linked.append(row)
        if linked:
            for row in linked:
                document_evidence.setdefault('function_bindings', []).append({
                    'fact_id': duty['fact_id'], 'function_name': row['name'], 'hardware_node_ref': host_ref})
                # Existing canonical functions stay linked through proposal
                # evidence. Newly proposed functions receive both provenances.
                if any(change['data'] is row for change in changes if change['object_type'] == 'Function'):
                    configuration = row.setdefault('configuration', {})
                    configuration.setdefault('reviewed_document_functions', []).append(duty)
            continue
        ensure('Function', duty['name'], {'hardware_node_id': hardware_refs[duty['host']],
            'domain': spec['domain'], 'description': duty['source_quote'],
            'configuration': {'reviewed_document_function': duty,
                              'source_scoped_function': {'name': duty['name'], 'source_quote': duty['source_quote'], 'source': 'reviewed_document'},
                              'processing_evidence': 'NONE', 'dependency_review': 'REQUIRED'}}, 'hardware_node_id')

    # The selected cluster technology is the ECU/Gateway backbone.'''),
    ('def generate(arguments: dict, *, source_evidence:', '''def _reviewed_document_functions(evidence: dict | None, hosts: list[str], chains: list[dict] | None = None) -> list[dict]:
    """Resolve only explicit source-fact assignments to real executable hosts."""
    from backend.nis.agent.orchestration.project_intake import document_fact_identity
    duties = [fact for fact in (evidence or {}).get('components', []) if fact['kind'] == 'FUNCTION']
    assignments = (evidence or {}).get('function_assignments', {})
    result = []
    for fact in duties:
        identity = document_fact_identity(fact)
        candidates = set()
        for chain in chains or []:
            if chain.get('device_type') not in _CONTROLLER_DEVICE_TYPES:
                continue
            configuration = chain.get('configuration') or {}
            context = (configuration.get('document_equipment_evidence') or {}).get('source_context', [])
            if context[:-1] != fact.get('source_context', [])[:-1]:
                continue
            if any(len(duty.get('source_quote', '')) >= 3 and duty['source_quote'] in fact['source_quote']
                   for duty in configuration.get('source_scoped_functions', [])):
                candidates.add(chain['hardware_name'].casefold())
        scoped_host = next(iter(candidates)) if len(candidates) == 1 else ''
        host = str(assignments.get(identity) or scoped_host).casefold()
        if not host or host not in hosts:
            raise ValueError(f"Funktionszuordnung fehlt oder ist ungültig für: {fact['name']}. Bitte den ausführenden Controller festlegen.")
        # The source identity disambiguates equal names in separate profiles.
        import hashlib
        suffix = hashlib.sha256(identity.encode('utf-8')).hexdigest()[:10]
        result.append({**fact, 'name': f"{fact['name']} [{suffix}]", 'host': host,
                       'fact_id': identity, 'source_sha256': evidence['source_sha256'],
                       'assignment_source': 'source_scoped_function' if host == scoped_host else 'explicit_user_statement'})
    return result


def generate(arguments: dict, *, source_evidence:'''),
])

relative = 'backend/tests/test_wizard_generation.py'
original = Path(relative)
before = OUT / 'before' / relative
if not before.exists():
    before.parent.mkdir(parents=True, exist_ok=True)
    before.write_bytes(original.read_bytes())
    work_path = OUT / 'workload.json'
    work = json.loads(work_path.read_text(encoding='utf-8'))
    work['revision_before'][relative] = hashlib.sha256(original.read_bytes()).hexdigest()
    work['repair']['affected_files'].append(relative)
    work_path.write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
text = before.read_text(encoding='utf-8') + '''

def test_reviewed_document_functions_require_explicit_real_hosts_and_keep_sources():
    from backend.nis.agent.orchestration.project_intake import document_fact_identity
    fact = {'name': 'Motion Control', 'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None,
            'source_quote': 'Motion Control und Kraftregelung', 'source_context': ['054 Roboter', 'Funktionen']}
    evidence = {'components': [fact], 'source_sha256': 'a' * 64}
    with pytest.raises(ValueError, match='Funktionszuordnung'):
        wizard_generation._reviewed_document_functions(evidence, ['hauptrechner'])
    evidence['function_assignments'] = {document_fact_identity(fact): 'Gateway'}
    with pytest.raises(ValueError, match='Funktionszuordnung'):
        wizard_generation._reviewed_document_functions(evidence, ['hauptrechner'])
    evidence['function_assignments'] = {document_fact_identity(fact): 'Hauptrechner'}
    result = wizard_generation._reviewed_document_functions(evidence, ['hauptrechner'])
    assert result[0]['host'] == 'hauptrechner'
    assert result[0]['source_quote'] == fact['source_quote']
    assert result[0]['source_context'] == fact['source_context']
    assert result[0]['fact_id'] == document_fact_identity(fact)
    assert result[0]['source_sha256'] == 'a' * 64
    other = {**fact, 'source_context': ['056 AMR', 'Funktionen']}
    evidence['components'].append(other)
    evidence['function_assignments'][document_fact_identity(other)] = 'Hauptrechner'
    result = wizard_generation._reviewed_document_functions(evidence, ['hauptrechner'])
    assert len({duty['name'] for duty in result}) == 2


def test_typed_function_preserves_unique_literal_controller_scope_without_sole_host_fallback():
    fact = {'name': 'Perception', 'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None,
            'source_quote': 'Perception (Objekte, Spuren)', 'source_context': ['Robot A', 'Functions']}
    evidence = {'components': [fact], 'source_sha256': 'a' * 64}
    chain = {'hardware_name': 'ADC', 'device_type': 'ECU', 'configuration': {
        'source_scoped_functions': [{'source_quote': fact['source_quote']}],
        'document_equipment_evidence': {'source_context': ['Robot A', 'Architecture']}}}
    result = wizard_generation._reviewed_document_functions(evidence, ['adc'], [chain])
    assert result[0]['host'] == 'adc'
    assert result[0]['assignment_source'] == 'source_scoped_function'
    chain['configuration']['document_equipment_evidence']['source_context'] = ['Robot B', 'Architecture']
    with pytest.raises(ValueError, match='Funktionszuordnung'):
        wizard_generation._reviewed_document_functions(evidence, ['adc'], [chain])
    chain['configuration']['document_equipment_evidence']['source_context'] = ['Robot A', 'Architecture']
    with pytest.raises(ValueError, match='Funktionszuordnung'):
        wizard_generation._reviewed_document_functions(evidence, ['adc', 'other'], [chain, {**chain, 'hardware_name': 'Other'}])


@pytest.mark.parametrize('with_scoped', [False, True])
def test_typed_document_duties_enter_model_proposal_with_complete_requirements(monkeypatch, with_scoped):
    import hashlib
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, resolve_document_references, document_fact_identity
    source = '# Robot\\n## Architecture\\nHauptrechner\\n## Functions\\nMotion Control\\n## Requirements\\nREQ-R-001: The controller shall detect sensor faults.'
    rows = document_source_references(source)
    units = document_component_sources(rows)
    facts = resolve_document_references({'components': [{'source_ref': unit['source_ref'], **unit['policy']} for unit in units], 'technologies': []}, rows)['components']
    function = next(fact for fact in facts if fact['kind'] == 'FUNCTION')
    envelope = {'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'source_chars': len(source), 'source_text': source,
                'facts': facts, 'technologies': [], 'questions': [], 'answers': [],
                'function_assignments': {document_fact_identity(function): 'Hauptrechner'}}
    prompt = source + '\\n- Dokument-Geräte: ' + json.dumps(envelope, ensure_ascii=False)
    chain = {'hardware_name': 'Hauptrechner', 'hardware_description': 'Hauptrechner', 'device_type': 'ECU', 'device_class': 4,
             'function_name': 'HauptrechnerStatus', 'function_description': 'Status', 'interface_name': 'Hauptrechner_Ethernet',
             'interface_type': 'Ethernet', 'transport_network_ref': None, 'message_name': 'HauptrechnerData',
             'message_id_hex': None, 'direction': 'tx', 'cycle_ms': 20, 'dlc': 1, 'signal_name': 'HauptrechnerValue',
             'start_bit': 0, 'length_bits': 8, 'byte_order': 'little_endian', 'data_type': 'unsigned', 'factor': 1, 'offset_value': 0}
    if with_scoped:
        chain['configuration'] = {'source_scoped_functions': [{'name': 'Motion Control', 'source_quote': 'Motion Control'}]}
    spec = {'domain': 'custom', 'modelType': 'custom', 'targetCounts': {'gateways': 0, 'ecus': 1, 'sensors': 0, 'actuators': 0},
            'communicationSystemCounts': {'ethernet': 1}, 'chains': [chain]}
    monkeypatch.setattr(wizard_generation.proposal_store, 'list_proposals', lambda limit: [])
    monkeypatch.setattr(wizard_generation.model, 'objects', lambda _kind: [])
    monkeypatch.setattr(wizard_generation, 'extract_specification', lambda _prompt: spec)
    captured = {}
    monkeypatch.setattr(wizard_generation.proposal_service, 'create',
                        lambda proposal_type, changes, summary, **metadata: captured.update(changes=changes, metadata=metadata) or captured)
    result = wizard_generation.generate({'prompt': prompt})
    duties = [row['data'] for row in result['changes'] if row['object_type'] == 'Function'
              and ((row['data'].get('configuration') or {}).get('reviewed_document_function')
                   or (row['data'].get('configuration') or {}).get('reviewed_document_functions'))]
    assert len(duties) == 1
    config = duties[0]['configuration']
    duty = config.get('reviewed_document_function') or config['reviewed_document_functions'][0]
    assert duty['source_quote'] == 'Motion Control'
    assert duty['source_context'] == ['Robot', 'Functions']
    assert duties[0]['configuration']['processing_evidence'] == 'NONE'
    assert duties[0]['configuration']['dependency_review'] == 'REQUIRED'
    assert duties[0]['configuration']['source_scoped_function']['source_quote'] == 'Motion Control'
    assert len([row for row in result['changes'] if row['object_type'] == 'Function']) == 2
    evidence = next(item for item in captured['metadata']['evidence'] if item.get('source') == 'reviewed_document')
    assert evidence['components'] == facts
    assert any(fact['source_quote'] == 'REQ-R-001: The controller shall detect sensor faults.' for fact in evidence['components'])
    if with_scoped:
        assert len(evidence['function_bindings']) == 1
'''
(OUT / 'staged' / relative).write_text(text, encoding='utf-8')

relative = 'frontend/src/features/agent/lib/engineering-specification.test.mjs'
target = OUT / 'staged' / relative
text = target.read_text(encoding='utf-8').replace('import { documentDeviceQuestions,', 'import { documentSourceFunctionAssignments, documentEvidenceCounts, documentFactIdentity, documentDeviceQuestions,', 1)
text += '''

test('function assignments retain exact fact identity and require a real source fact', () => {
  const source = '# Robot\\n## Functions\\nMotion Control';
  const fact = { name: 'Motion Control', kind: 'FUNCTION', role: 'OTHER', quantity: null,
    source_quote: 'Motion Control', source_context: ['Robot', 'Functions'] };
  const proposal = { interpretation: { components: [fact], technologies: [] } };
  const id = documentFactIdentity(fact);
  const equipment = reviewDocumentEquipment(source, proposal, {}, false, {}, { [id]: 'Hauptrechner' });
  assert.deepEqual(equipment.function_assignments, { [id]: 'Hauptrechner' });
  assert.deepEqual(readReviewedDocumentEquipment(`${source}\\n- Dokument-Geräte: ${JSON.stringify(equipment)}`).function_assignments, equipment.function_assignments);
  equipment.function_assignments = { forged: 'Hauptrechner' };
  assert.throws(() => readReviewedDocumentEquipment(`${source}\\n- Dokument-Geräte: ${JSON.stringify(equipment)}`), /Funktionszuordnung/);
});

test('explicitly excluding an untyped category does not fabricate a device role', () => {
  const source = 'Architecture: Optical unit';
  const proposal = { interpretation: { components: [{ name: 'Optical unit', kind: 'CATEGORY', role: 'OTHER', quantity: null, source_quote: 'Optical unit' }], technologies: [] } };
  const [question] = documentDeviceQuestions(source, proposal);
  const equipment = reviewDocumentEquipment(source, proposal, { [question.id]: '0' }, false);
  assert.deepEqual(equipment.answers, []);
  assert.deepEqual(equipment.excluded_questions, [question.id]);
  const spec = extractEngineeringSpecification(`${source}\\n- Dokument-Geräte: ${JSON.stringify(equipment)}`);
  assert.equal(spec.chains.length, 0);
  assert.equal(spec.unresolvedInventoryGroups.length, 0);
});

test('typed sensor groups retain their own profile and exclude functional sensor lists', () => {
  const quote = 'Sensorik (Kamera, Radar)';
  const source = `# A\\n${quote}\\n# B\\n${quote}\\n# Functions\\nSensorik: Diagnose`;
  const components = ['A', 'B'].map(scope => ({ name: 'Sensorik', kind: 'CATEGORY', role: 'SENSOR', quantity: null, source_quote: quote, source_context: [scope] }));
  components.push({ name: 'Diagnose', kind: 'FUNCTION', role: 'OTHER', quantity: null, source_quote: 'Sensorik: Diagnose', source_context: ['Functions'] });
  const questions = documentDeviceQuestions(source, { interpretation: { components } });
  assert.equal(questions.length, 4);
  assert.deepEqual(questions.map(question => question.source_context[0]).sort(), ['A', 'A', 'B', 'B']);
  assert.deepEqual(questions.map(question => question.label).sort(), ['Kamera', 'Kamera', 'Radar', 'Radar']);
});

test('requirement ID counts recognize Unicode hyphens without changing literal evidence', () => {
  const source = 'REQ‑ADC‑02: Objektliste Position/Geschwindigkeit/Klassifikation.\\nREQ-FUS-01: Fusion shall retain time.\\nREQ-ADC-02: Same ID with ASCII hyphens.';
  const facts = [{ name: 'Anforderungen', kind: 'REQUIREMENT', role: 'OTHER', quantity: null, source_quote: source }];
  const equipment = reviewDocumentEquipment(source, { interpretation: { components: facts, technologies: [] } }, {}, false);
  assert.equal(documentEvidenceCounts(equipment).requirementIds, 2);
  assert.equal(equipment.facts[0].source_quote, source);
});

test('document functions reuse only unique literal responsibilities in the same source system', () => {
  const fact = { name: 'Perception', kind: 'FUNCTION', role: 'OTHER', quantity: null, source_quote: 'Perception (Objekte, Spuren)', source_context: ['Robot A', 'Functions'] };
  const owner = { name: 'ADC', source_context: ['Robot A', 'Architecture'], duties: [{ source_quote: fact.source_quote }] };
  assert.deepEqual(documentSourceFunctionAssignments([fact], [owner]), { [documentFactIdentity(fact)]: 'ADC' });
  assert.deepEqual(documentSourceFunctionAssignments([fact], [{ ...owner, source_context: ['Robot B', 'Architecture'] }]), {});
  assert.deepEqual(documentSourceFunctionAssignments([fact], [owner, { ...owner, name: 'Other' }]), {});
  assert.deepEqual(documentSourceFunctionAssignments([fact], [{ ...owner, duties: [] }]), {});
});
'''
target.write_text(text, encoding='utf-8')
print('Explicit typed function handoff staged; original source freeze preserved.')

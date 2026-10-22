"""Refine only docs-staged source while the preceding release is frozen."""
from pathlib import Path
import json

ROOT = Path(__file__).parent
STAGED = ROOT / 'staged'


def edit(relative, transform):
    path = STAGED / relative
    before = path.read_text(encoding='utf-8')
    after = transform(before)
    if after == before:
        raise ValueError('No staged change: ' + relative)
    path.write_text(after, encoding='utf-8', newline='\n')


def drafts(text):
    text = text.replace("or record.get('revision') != request.revision or record.get('request_sha256') != request.request_sha256):",
        "or record.get('revision') not in ({request.revision, request.revision + 1} if record.get('status') == 'ACCEPTED' else {request.revision})\n"
        "            or record.get('request_sha256') != request.request_sha256):", 1)
    text = text.replace("'devices': [], 'issues': [], 'sources': [], 'removed_device_ids': [],",
        "'devices': [], 'issues': [], 'sources': [{'source': 'REVIEWED_DOCUMENT', 'text': prepared['source_evidence']['source_text'],\n"
        "            'source_sha256': prepared['source_sha256']}], 'removed_device_ids': [],", 1)
    text = text.replace("    existing = draft.get('reference_design')\n", """    pending = draft.get('reference_generation') or {}
    if pending.get('operation_id') == operation_id and pending.get('request_sha256') != prepared['request_sha256']:
        raise ConcurrentUpdateError('Dieselbe Referenzoperation darf nicht andere Quellen verwenden.')
    if pending.get('status') == 'RUNNING' and pending.get('request_sha256') == prepared['request_sha256']:
        raise ConcurrentUpdateError('Dieser Referenzauftrag läuft bereits. Den gespeicherten Stand abwarten.')
    existing = draft.get('reference_design')
""", 1)
    start = text.index('    async def infer():', text.index('def generate_reference_design'))
    end = text.index('\n\n\ndef accept_reference_design', start)
    body = text[start:end]
    # Commit the reservation before slow local inference. Runtime restores the
    # same project unit for dispatch and commits success/failure independently.
    text = text[:start] + "    from backend.nis.agent.tools.runtime import PostCommitAction\n    def dispatch():\n" + ''.join('    ' + line + '\n' for line in body.splitlines()) + "    return PostCommitAction(dispatch, lambda: None)" + text[end:]
    text = text.replace("    if marker.get('proposal') != record['proposal'] or marker.get('fact_id_map') != record['fact_id_map']:",
        "    if any(marker.get(key) != record.get(key) for key in ('proposal', 'fact_id_map', 'decision_evidence', 'protected_fields', 'source_sha256')):", 1)
    text = text.replace("    if evidence is None or evidence['source_sha256'] != record['source_sha256']:",
        "    original = reviewed_document_evidence(record['request']['prompt'])\n"
        "    if evidence is None or evidence != original or evidence['source_sha256'] != record['source_sha256']:", 1)
    text = text.replace("    old = migrate_draft(state.get('engineering_draft'))\n", "    old = migrate_draft(state.get('engineering_draft'))\n"
        "    if old and old.get('source_format') == 'REFERENCE_DOCUMENT':\n"
        "        raise ValueError('Den vollständigen Dokumententwurf über seine Referenzprüfung und den normalen Wizard bearbeiten; der kleine Inventarparser darf ihn nicht ersetzen.')\n", 1)
    text = text.replace('    if draft.get(\'source_format\') == \'WIZARD_V2\':\n',
        "    if draft.get('source_format') == 'REFERENCE_DOCUMENT':\n"
        "        raise ValueError('Den geprüften Referenzentwurf im vollständigen Wizard übernehmen.')\n"
        "    if draft.get('source_format') == 'WIZARD_V2':\n", 1)
    return text


edit('backend/nis/agent/tools/project_draft.py', drafts)


def capture(text):
    text = text.replace("    previous = state.get('engineering_draft')\n", "    previous = state.get('engineering_draft')\n"
        "    from backend.nis.agent.tools.project_draft import reference_design_for_prompt\n"
        "    reference_design = reference_design_for_prompt(descriptor['prompt'])\n", 1)
    text = text.replace("    state['engineering_draft'] = draft\n", "    if reference_design:\n"
        "        draft['reference_design'] = deepcopy(reference_design)\n"
        "        draft['reference_sources'] = deepcopy(reference_design['reference_sources'])\n"
        "    state['engineering_draft'] = draft\n", 1)
    return text


edit('backend/nis/agent/tools/structured_project_draft.py', capture)


def reasoner(text):
    start = text.index('    async def plan_reference_design(')
    end = text.index('\n    async def ', start + 10)
    block = text[start:end]
    block = block.replace("'communication', 'unresolved')", "'communication', 'functional_dependencies', 'unresolved')")
    block = block.replace("{'functions'})", "{'functions', 'functional_dependencies'})")
    block = block.replace("            prefix = json.dumps(profile, ensure_ascii=False)",
        "            prefix = json.dumps(profile, ensure_ascii=False)")
    block = block.replace("            for item in current['communication']:\n", "            for item in current['functional_dependencies']:\n"
        "                item['id'] = local_id('f', item['id'])\n"
        "                item['executor_device_id'] = devices.get(item['executor_device_id'], item['executor_device_id'])\n"
        "            for item in current['communication']:\n", 1)
    block = block.replace("            'Antworte ausschließlich im JSON-Schema.", "            'Gleich lokalisierte Funktionspartner werden durch functional_dependencies verbunden; keine physische Schleife erfinden. '\n            'Antworte ausschließlich im JSON-Schema.", 1)
    return text[:start] + block + text[end:]


edit('backend/nis/agent/orchestration/local_reasoner.py', reasoner)


def api(text):
    # One stream implementation for both native source interpretation and
    # reference planning. Approval remains a separate human-only route.
    start = text.index("@agent_api.post('/document-intake')")
    end = text.index("\n\n@agent_api.post('/project-draft/create-project')", start)
    old = text[start:end]
    body_start = old.index('    arguments = request.get_json')
    helper = old[body_start:]
    helper = helper.replace("'interpret_project_document'", 'tool_name').replace('arguments, interpret_project_document', 'arguments, handler').replace('                         interpret_project_document)', '                         handler)')
    helper = helper.replace("'Lokaler Qwen startet die vollständige Dokumentprüfung.'", 'initial_text')
    common = "def _local_document_response(tool_name, handler, initial_text):\n" + helper
    routes = '''@agent_api.post('/document-intake')
def document_intake():
    from backend.nis.agent.orchestration.project_intake import DOCUMENT_REQUEST_MAX_BYTES, interpret_project_document
    request.max_content_length = DOCUMENT_REQUEST_MAX_BYTES
    if not _human_intent():
        return jsonify({'error': 'Bitte die lokale Dokumentauswertung ausdrücklich starten.'}), 403
    return _local_document_response('interpret_project_document', interpret_project_document,
                                    'Lokaler Qwen startet die vollständige Dokumentprüfung.')


@agent_api.route('/document-reference-design', methods=['GET', 'POST'])
def document_reference_design():
    from backend.nis.agent.tools import project_draft as drafts
    from backend.nis.agent.context.limits import MAX_REQUIREMENT_REQUEST_BYTES
    request.max_content_length = MAX_REQUIREMENT_REQUEST_BYTES
    if request.method == 'GET':
        result = execute(ToolAuthority(_project(), 'local-human'), 'inspect_reference_design',
                         Permission.READ_MODEL, {}, lambda _: drafts.inspect_reference_design())
        response = jsonify(result.model_dump(mode='json'))
        response.headers['Cache-Control'] = 'no-store'
        return response, 200 if result.success else 409
    if not _human_intent():
        return jsonify({'error': 'Die Referenzplanung muss ausdrücklich als Beispielauftrag gestartet werden.'}), 403
    return _local_document_response('generate_reference_design', drafts.generate_reference_design,
                                    'Lokaler Qwen plant getrennte, prüfbare Referenzannahmen.')


@agent_api.post('/document-reference-design/accept')
def accept_document_reference_design():
    from backend.nis.agent.tools import project_draft as drafts
    if not _human_intent():
        return jsonify({'error': 'Referenzannahmen vor der Übernahme ausdrücklich prüfen.'}), 403
    result = execute(ToolAuthority(_project(), 'local-human'), 'accept_reference_design',
                     Permission.GENERATE_PROPOSAL, request.get_json(silent=True) or {}, drafts.accept_reference_design)
    response = jsonify(result.model_dump(mode='json'))
    response.headers['Cache-Control'] = 'no-store'
    return response, 200 if result.success else 409


'''
    return text[:start] + routes + common + text[end:]


edit('backend/nis/agent/tools/api.py', api)


def services(text):
    point = text.index("register('inspect_project_draft'")
    additions = '''from backend.nis.agent.orchestration.project_intake import ReferenceSource
from backend.nis.agent.context.limits import MAX_REQUIREMENT_LENGTH
register('generate_reference_design', 'Für ausdrücklich gewählte Beispielprojekte fehlende Auslegungsdaten mit lokalem Qwen als getrennte REFERENCE_ASSUMPTION planen. Quellen erhalten; keine kanonische Änderung oder Freigabe.',
         P.GENERATE_PROPOSAL, project_draft.generate_reference_design,
         mode=(str, Field(pattern='^EXAMPLE_PROJECT$')),
         prompt=(str, Field(min_length=1, max_length=MAX_REQUIREMENT_LENGTH)),
         reference_sources=(list[ReferenceSource], Field(default_factory=list, max_length=16)),
         source_request_id=(str | None, Field(default=None, min_length=8, max_length=120)))
register('inspect_reference_design', 'Aktuellen quellengebundenen Referenzentwurf im gemeinsamen Projektentwurf lesen.',
         P.READ_MODEL, lambda _: project_draft.inspect_reference_design())
'''
    return text[:point] + additions + text[point:]


edit('backend/nis/agent/tools/services.py', services)

workload = json.loads((ROOT / 'workload.json').read_text(encoding='utf-8'))
workload['human_authorization']['verbatim'] = 'Bitte behebt diese Lücken gemeinsam mit „NIS starten“, sodass NIS fehlende Beispieldaten als prüfbare Referenzannahmen ergänzt. Prüft danach beide Dateien vollständig bis zur Simulation und liefert die verifizierte Korrektur produktiv aus.'
(ROOT / 'workload.json').write_text(json.dumps(workload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

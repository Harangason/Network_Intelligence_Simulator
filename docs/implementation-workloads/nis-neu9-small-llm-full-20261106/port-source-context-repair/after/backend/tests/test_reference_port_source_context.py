"""Independent source-focus regressions; no native or Original acceptance claim."""
from copy import deepcopy
import json

import pytest

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.tests.test_reference_current_stage_context import authored_port_context
from backend.tests.test_reference_reasoner import effective_reference_context, reasoner_with_transport, run_reference


def source_fixture():
    devices = [
        {'id': 'C1', 'kind': 'CONTROLLER', 'source_fact_ids': ['count'], 'owner_device_id': None},
        {'id': 'C2', 'kind': 'CONTROLLER', 'source_fact_ids': ['count'], 'owner_device_id': None},
        {'id': 'S', 'kind': 'SENSOR', 'source_fact_ids': ['sensor'], 'owner_device_id': 'C2'},
    ]
    facts = {
        'count': {'kind': 'INSTANCE', 'source_quote': '2 Steuergeräte', 'quantity': 2},
        'sensor': {'kind': 'INSTANCE', 'source_quote': '1 Temperatursensor', 'quantity': 1},
        'all': {'kind': 'REQUIREMENT', 'source_quote': 'Jedes Steuergerät verarbeitet 5–20 Signale.\r\nµ', 'source_context': []},
        'phy': {'kind': 'REQUIREMENT', 'source_quote': 'Die physische Auslegung bleibt zu prüfen.', 'source_context': ['Maschine A']},
        'foreign': {'kind': 'REQUIREMENT', 'source_quote': 'Fremdes Profil verwendet einen anderen Transport.', 'source_context': ['Maschine B']},
    }
    return devices, facts


def test_port_focus_preserves_literal_shared_requirements_without_inventing_per_device_bindings():
    devices, facts = source_fixture()
    before = deepcopy((devices, facts))
    assert hasattr(reasoner, '_reference_port_source_context'), 'Missing literal source facts at port decision'
    view = reasoner._reference_port_source_context(devices, facts, ('C1', 'S'), ('count', 'sensor', 'all', 'phy'))
    assert view['requirements'] == {'all': facts['all'], 'phy': facts['phy']}
    assert 'foreign' not in view['requirements']
    assert view['device_sources'] == {
        'C1': {'count': facts['count']}, 'C2': {'count': facts['count']}, 'S': {'sensor': facts['sensor']}}
    assert all('all' not in bound for bound in view['device_sources'].values())
    view['requirements']['all']['source_quote'] = 'mutation'
    assert (devices, facts) == before


@pytest.mark.parametrize('transition', ['fresh', 'append', 'rebase'])
def test_port_source_focus_survives_context_transitions_without_overriding_unknowns(transition):
    current = authored_port_context()
    current['selected_port_source_context'] = {
        'device_sources': {'authored-device-024': {'F': {'source_quote': '50 Geräte'}}},
        'requirements': {'R': {'kind': 'REQUIREMENT', 'source_quote': 'Alle Geräte senden Status.\r\nPHY bleibt offen.'}}}
    early = deepcopy(current)
    early['selected_port_source_context']['requirements']['R']['source_quote'] = 'Earlier context'
    anchor_messages, _, _ = reasoner._reference_context_messages([], None, early, 'Authored', 131072)
    anchor = ([*anchor_messages, {'role': 'assistant', 'content': '{}'}], early)
    history = anchor[0] if transition != 'fresh' else []
    if transition == 'rebase':
        history = [*history, {'role': 'user', 'content': 'overflow' * 17000}]
    before = deepcopy(current)
    messages, _, rebased = reasoner._reference_context_messages(history, early if history else None,
        current, 'Authored', 131072, anchor=anchor if history else None)
    if transition == 'rebase':
        assert rebased
    assert json.loads(messages[-1]['content'])['nis_current_selection']['selected_port_source_context'] == current['selected_port_source_context']
    assert effective_reference_context(messages) == before
    assert current == before
    assert current['current_candidate']['unresolved'][0]['code'] == 'UNKNOWN_PHY'


def test_normal_port_stage_receives_original_quotes_from_prepared_source(monkeypatch):
    instance, prepared, observed = reasoner_with_transport(monkeypatch)
    run_reference(instance, prepared)
    demands = [row for row in observed if row.get('selected_port_function_context') is not None]
    assert demands
    expected = {key: fact for key, fact in prepared['facts'].items() if fact['kind'] == 'REQUIREMENT'}
    for request in demands:
        view = request['selected_port_source_context']
        assert view['requirements'] == expected
        for identity in request['device_ids_for_this_stage']:
            row = next(device for device in request['current_candidate']['devices'] if device['id'] == identity)
            assert view['device_sources'][identity] == {key: prepared['facts'][key] for key in row['source_fact_ids']}
        assert request['original_source'] == prepared['source_evidence']['source_text']


def test_port_planner_receives_authoritative_physical_profiles_without_selecting_a_phy(monkeypatch):
    from dataclasses import asdict
    import hashlib
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    from backend.tests.test_reference_design import fixture_request
    request = fixture_request()
    envelope = json.loads(request['prompt'].split('- Dokument-Geräte: ', 1)[1])
    for technology in ('can_fd', 'ethernet', 'mqtt'):
        quote = 'Transport: ' + technology
        envelope['source_text'] += '\n' + quote
        envelope['technologies'].append({'name': technology, 'kind': 'TRANSPORT', 'source_quote': quote})
    envelope['source_chars'] = len(envelope['source_text'])
    envelope['source_sha256'] = hashlib.sha256(envelope['source_text'].encode()).hexdigest()
    request['prompt'] = envelope['source_text'] + '\n- Dokument-Geräte: ' + json.dumps(envelope, ensure_ascii=False)
    instance, prepared, observed = reasoner_with_transport(monkeypatch, request=request)
    run_reference(instance, prepared)
    requests = [row for row in observed if row.get('selected_port_function_context') is not None]
    assert requests
    for request in requests:
        technologies = request['registered_catalogs']['source_technologies']
        assert technologies
        for identity, technology in technologies.items():
            profile = DEFAULT_TECHNOLOGY_REGISTRY.physical_profile(identity)
            expected = json.loads(json.dumps(asdict(profile))) if profile else None
            assert technology['physical_profile'] == expected
        messages, _, _ = reasoner._reference_context_messages([], None, request, 'Authored', 131072)
        view = json.loads(messages[-1]['content'])['nis_current_selection']
        assert view['source_technologies'] == technologies
        assert effective_reference_context(messages) == request


def test_terminal_rejection_preserves_exact_input_response_and_failure(monkeypatch, caplog, tmp_path):
    import hashlib
    monkeypatch.setenv('NIS_RUNTIME_DIR', str(tmp_path))
    def no_progress(candidate, content, payload, prepared):
        assert not list(tmp_path.rglob('*.json')), 'Only the terminal rejection should create evidence'
        candidate.update(devices=[], inventory_complete=False)
    instance, prepared, observed = reasoner_with_transport(monkeypatch, derivation_mutator=no_progress)
    with pytest.raises(ValueError, match='keine fehlende ursprüngliche Geräteabdeckung'):
        run_reference(instance, prepared)
    records = [json.loads(row.args[0]) for row in caplog.records
               if row.msg == 'Native reference validation failed: %s']
    assert [row['attempt'] for row in records] == [1, 2]
    assert records[0].get('terminal_input') is None
    diagnostic = records[-1]['terminal_input']
    assert diagnostic['status'] == 'SAVED'
    artifact = tmp_path / diagnostic['artifact']
    raw = artifact.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == diagnostic['sha256']
    saved = json.loads(raw)
    assert saved['context'] == observed[-1]
    assert effective_reference_context(saved['request']['messages']) == saved['context']
    assert saved['response'] == records[-1]['response']
    assert saved['error'] == records[-1]['error']
    assert len(list(tmp_path.rglob('*.json'))) == 1
    assert saved['context']['original_source'] not in caplog.text


def test_reference_artifact_limits_and_existing_hash_are_preserved(monkeypatch, tmp_path):
    import hashlib
    monkeypatch.setenv('NIS_RUNTIME_DIR', str(tmp_path))
    assert hasattr(reasoner, '_reference_context_artifact')
    original = {'literal': 'private source µ', 'typed': [False, None, 0, -0.0]}
    saved = reasoner._reference_context_artifact(original)
    assert saved['status'] == 'SAVED'
    path = tmp_path / saved['artifact']
    raw = path.read_bytes()
    assert json.loads(raw) == original
    assert hashlib.sha256(raw).hexdigest() == saved['sha256']
    for number in range(15):
        (path.parent / f'preserved-{number}.json').write_text('{}')
    assert reasoner._reference_context_artifact({'new': True})['status'] == 'COUNT_LIMIT'
    assert reasoner._reference_context_artifact(original) == saved
    assert reasoner._reference_context_artifact({'large': 'x' * (4 * 1024 * 1024)})['status'] == 'SIZE_LIMIT'
    path.write_text('external-corruption')
    mismatch = reasoner._reference_context_artifact(original)
    assert mismatch['status'] == 'HASH_MISMATCH' and mismatch['artifact'] is None
    assert path.read_text() == 'external-corruption', 'Never overwrite retained evidence'

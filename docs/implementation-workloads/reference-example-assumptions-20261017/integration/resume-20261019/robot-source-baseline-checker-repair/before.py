"""Compare saved canonical model exports with the full original robot source.

Read-only verification of actual application exports. Never supplies a design,
changes a project, runs SQL, calls inference, or grants model/simulation approval.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration.project_intake import document_fact_identity, document_source_contexts, document_system_scope

SOURCE_SHA = '8fc201a55e8b0afeb7b708ac70abd0c72a7b25eb17d90fceca71d80a291f3cef'
EXPECTED = ROOT / '.tool-checker/runs/20261017_src_original_documents_simulation/robotics/expected-source-manifest.json'
SOURCE = Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/INDUSTRIEPORTFOLIO_100_KATEGORIENPAKET/D_INDUSTRIAL_ROBOTICS_054_063.md')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def unwrap(value):
    if 'success' in value:
        assert value['success'] is True, 'Application read failed'
        return value['data']
    return value


def verify(model, reference, project):
    assert project and project != 'default'
    project = project.removeprefix('network-project-')
    assert model['project_id'].removeprefix('network-project-') == project
    assert reference['project_id'].removeprefix('network-project-') == project
    assert reference['status'] == 'ACCEPTED' and 'validation_scope' not in reference
    evidence = reference['source_evidence']
    source = evidence['source_text']
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA
    assert hashlib.sha256(source.encode('utf-8')).hexdigest() == SOURCE_SHA
    assert evidence['source_sha256'] == SOURCE_SHA and evidence['source_chars'] == 63705
    assert len(source) == 63705
    expected = read(EXPECTED)
    historical_file = Path(expected['prior_adopted_facts']['path'])
    assert hashlib.sha256(historical_file.read_bytes()).hexdigest() == expected['prior_adopted_facts']['sha256']
    _, contexts = document_source_contexts(source)
    context_map = {}
    for context in contexts:
        joined = ' / '.join(context)
        assert joined not in context_map or context_map[joined] == context
        context_map[joined] = context
    historical = [dict(name=row['name'], kind=row['kind'], role=row['role'], quantity=row['quantity'],
        source_quote=row['quote'], source_context=context_map[row['context']]) for row in read(historical_file)]
    facts = {document_fact_identity(row): row for row in evidence['components']}
    missing_original = [row for row in historical if document_fact_identity(row) not in facts]
    assert not missing_original, 'Previously preserved literal source facts missing or regrouped: ' + repr(missing_original[:4])
    hardware = model['hardware']
    functions = model['functions']
    by_id = {row['id']: row for row in hardware}
    assert len(by_id) == len(hardware), 'Saved model contains colliding hardware identities'
    bindings = {}
    function_bindings, requirement_bindings = set(), set()

    def bind(rows, target, kind):
        for row in rows:
            key = row.get('fact_id')
            assert key in facts, 'Unknown canonical source binding'
            fact = facts[key]
            assert fact['kind'] in kind, 'Source kind changed at canonical binding'
            assert row['source_sha256'] == SOURCE_SHA
            assert row['source_quote'] == fact['source_quote']
            assert row.get('source_context', []) == fact.get('source_context', [])
            bindings.setdefault(key, set()).add(target)

    requirement_quotes = []
    for node in hardware:
        identity = node.get('identity') or {}
        bind(identity.get('source_bindings', []), node['id'], {'INSTANCE', 'CATEGORY', 'FUNCTION', 'REQUIREMENT'})
        for context in identity.get('reference_context_memberships', []):
            assert context['kind'] == 'PHYSICAL_CONTEXT'
            bind(context['source_bindings'], node['id'], {'INSTANCE', 'CATEGORY', 'FUNCTION', 'REQUIREMENT'})
        requirements = identity.get('reference_source_requirements', [])
        node_scopes = {tuple(document_system_scope(row.get('source_context', []))) for row in identity.get('source_bindings', [])}
        for row in requirements:
            assert row['kind'] == 'REQUIREMENT' and row['source'] == 'ORIGINAL_DOCUMENT'
            assert row['allocation'] == 'UNALLOCATED_SOURCE_SCOPE' and row['assessment'] == 'UNASSESSED'
            assert row['processing_evidence'] == 'NONE' and row['timing_evidence'] == 'NONE'
            requirement_quotes.append(row['source_quote'])
            scope = tuple(document_system_scope(row.get('source_context', [])))
            assert not scope or scope in node_scopes, 'Requirement scope was copied into another source profile'
            requirement_bindings.add(row['fact_id'])
        bind(requirements, node['id'], {'REQUIREMENT'})
    atomic_hosts = {}
    for function in functions:
        config = function.get('configuration') or {}
        bind(config.get('reference_source_coverage', []), function['id'], {'FUNCTION'})
        function_bindings.update(row['fact_id'] for row in config.get('reference_source_coverage', []))
        original = config.get('reviewed_document_function')
        if original:
            atomic_hosts.setdefault(original['fact_id'], set()).add(function['hardware_node_id'])
            assert config.get('processing_evidence') == 'NONE'
    missing = [{'kind': row['kind'], 'name': row['name'], 'source_context': row.get('source_context', [])}
               for key, row in facts.items() if key not in bindings]
    assert not missing, 'Canonical model lost source facts: ' + repr(missing[:8])
    assert {key for key, fact in facts.items() if fact['kind'] == 'FUNCTION'} <= function_bindings, 'A source function has no canonical Function coverage'
    assert {key for key, fact in facts.items() if fact['kind'] == 'REQUIREMENT'} <= requirement_bindings, 'A source requirement is retained only as a hardware derivation'
    plan = reference['proposal']
    port_rows = [row for row in model['hardware-interfaces']
                 if str(row.get('physical_port_ref', '')).startswith('reference:' + reference['design_id'] + ':')]
    ports = {row['physical_port_ref']: row for row in port_rows}
    assert len(ports) == len(port_rows), 'Distinct saved ports share one physical identity'
    assert len(ports) == len(plan['ports']), 'Saved physical port count differs from the reviewed reference plan'
    device_refs = {}
    for port in plan['ports']:
        row = ports['reference:' + reference['design_id'] + ':' + port['id']]
        previous = device_refs.setdefault(port['device_id'], row['hardware_node_id'])
        assert previous == row['hardware_node_id'], 'Ports of one reference participant moved to different hardware'
        assert row['network_ref'] == port['network_scope']
    for device in plan['devices']:
        if device['kind'] == 'PHYSICAL_CONTEXT':
            continue
        assert device['quantity'] == 1
        if device['id'] not in device_refs:
            # A local compute participant may legitimately have no port. Use
            # canonical opaque identity when exported, otherwise require an
            # unambiguous exact set of source bindings among remaining nodes.
            expected = {reference['fact_id_map'][key] for key in device['source_fact_ids']}
            candidates = [row for row in hardware if row['id'] not in device_refs.values()
                and ((row.get('identity', {}).get('reference_design') or {}).get('reference_device_id') == device['id']
                     or {item['fact_id'] for item in row.get('identity', {}).get('source_bindings', [])} == expected)]
            assert len(candidates) == 1, 'No unique saved source identity for no-port participant: ' + device['id']
            device_refs[device['id']] = candidates[0]['id']
        node = by_id[device_refs[device['id']]]
        assert all(row['id'] == device['id'] or device_refs.get(row['id']) != node['id']
                   for row in plan['devices']), 'Different reference participants collapsed onto one hardware node'
        stamp = node['identity']['reference_design']
        assert stamp['source'] == 'REFERENCE_ASSUMPTION' and stamp['design_id'] == reference['design_id']
        assert stamp['processing_evidence'] == 'NONE' and stamp['timing_evidence'] == 'NONE'
    for function in plan['functions']:
        key = reference['fact_id_map'][function['source_fact_id']]
        if function['realization'] == 'ATOMIC':
            expected_hosts = {device_refs[executor] for executor in function['executor_device_ids']}
            assert atomic_hosts.get(key) == expected_hosts, 'Source function executor changed or was duplicated'
        else:
            assert not atomic_hosts.get(key), 'COMPOSITE became an extra executable algorithm'
    text = '\n'.join(requirement_quotes)
    missing_requirements = [row['id'] for row in expected['requirements'] if row['id'] not in text or row['text'] not in text]
    assert not missing_requirements, 'Complete requirement text missing: ' + repr(missing_requirements)
    assert len(device_refs) == len(hardware), 'Unplanned extra hardware was generated in the fresh verification project'
    return {'status': 'PASSED_SAVED_MODEL_SOURCE_COVERAGE', 'project_id': project,
        'source_sha256': SOURCE_SHA, 'source_chars': len(source),
        'source_facts_by_kind': dict(Counter(row['kind'] for row in facts.values())),
        'source_facts_with_saved_bindings': len(bindings), 'complete_formal_requirements': len(expected['requirements']),
        'planned_ports_retained': len(ports), 'hardware_nodes': len(hardware), 'canonical_functions': len(functions),
        'scope': 'Saved canonical model source coverage only; simulation execution and release evidence are separate.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--reference', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--project', required=True, help='Actual project ID verified in the selected application environment; never default.')
    args = parser.parse_args()
    result = verify(unwrap(read(args.model)), unwrap(read(args.reference)), args.project)
    result['inputs'] = [{'path': str(Path(path).resolve()), 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}
                       for path in (args.model, args.reference, EXPECTED)]
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))

"""Persist explicit field decisions; never infer a source review from enumeration."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry

folder = root / 'docs/implementation-workloads/technology-full-parameter-audit-20261001'


def record(technology, native, removed, sources, revisions, scope, validation, not_certified):
    inventory = json.loads((folder / 'inventory-before.json').read_text(encoding='utf-8'))
    original = next(item for item in inventory if item['technology'] == technology)
    before = {item['key']: item for item in original['form_parameters']}
    after = {item['key']: item for item in registry.parameter_fields(technology)}
    # Explicitly reviewed device-bound fields are first-class audit records.
    # Never mark a local evidence field reviewed just because it was enumerated.
    local_before = {f"local_timing_evidence.{item['key']}": item for item in original['profile'].get('local_timing_schema', [])}
    local_after = {f"local_timing_evidence.{item['key']}": item for item in registry.profile(technology).get('local_timing_schema', [])}
    reviewed_local = {key for key in native if key.startswith('local_timing_evidence.')}
    assert reviewed_local <= set(local_before) | set(local_after), (technology, reviewed_local)
    if reviewed_local:
        assert set(local_before) | set(local_after) <= reviewed_local, 'Review each declared local device field explicitly'
        before.update(local_before)
        after.update(local_after)
    baseline = {item['key']: item['meaning_and_applicability_review'] for item in
                json.loads((folder / 'individual/5g.json').read_text(encoding='utf-8'))['parameter_reviews']}
    assert set(before) - set(after) == set(removed)
    assert set(after) - set(before) <= set(native)
    records = []
    for key in sorted(set(before) | set(after)):
        item = after.get(key)
        if item is None:
            meaning, decision = removed[key], 'REMOVED_NOT_APPLICABLE'
        elif key in native:
            meaning, decision = native[key], 'NATIVE_OR_DECLARED_CONFIGURATION'
        else:
            assert item['parameter_origin'] == 'NIS_SCENARIO', (technology, key)
            assert key in baseline, (technology, key)
            meaning = baseline[key].split(';')[0].split(', kein')[0]
            meaning += f'; reviewed explicit NIS scenario/application requirement, not a {technology} standard or equipment guarantee.'
            decision = 'EXPLICIT_NIS_SCENARIO'
        records.append({'key': key, 'before': before.get(key), 'after': item,
                        'meaning_and_applicability_review': meaning, 'decision': decision,
                        'parameter_source_verified': True, 'runtime_capacity_verified': False})
    xml = folder / 'individual' / (technology + '-tests.xml')
    assert xml.exists(), xml
    data = {'technology': technology, 'status': 'SOURCE_AND_LOCAL_RULES_REVIEWED', 'scope': scope,
            'sources': sources + ['docs/COMMUNICATION_DESIGN_CONTRACT.md'],
            'source_revisions': revisions + ['NIS_SCENARIO_POLICY_V1'],
            'parameter_reviews': records,
            'remaining_runtime_status': registry.profile(technology)['capacity_evidence']['status'],
            'not_certified': not_certified + ['Production delivery'],
            'validation': {**validation, 'evidence': {'path': str(xml), 'sha256': hashlib.sha256(xml.read_bytes()).hexdigest()}}}
    (folder / 'individual' / (technology + '.json')).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    progress = []
    for profile in inventory:
        file = folder / 'individual' / (profile['technology'] + '.json')
        review = json.loads(file.read_text(encoding='utf-8')) if file.exists() else {}
        progress.append({'technology': profile['technology'], 'status': review.get('status', 'PENDING'),
                         'parameter_records': len(review.get('parameter_reviews', [])), 'production_delivered': False})
    count = sum(item['status'] == 'SOURCE_AND_LOCAL_RULES_REVIEWED' for item in progress)
    (folder / 'progress.json').write_text(json.dumps({'total_technologies': len(progress),
        'source_and_local_reviews': count, 'overall_status': 'IN_PROGRESS',
        'complete_release_gate': 'NOT_RUN', 'production_delivered': False, 'technologies': progress},
        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'technology': technology, 'records': len(records), 'reviews': count, 'total': len(progress)}))


if __name__ == '__main__':
    spec = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    record(**spec)

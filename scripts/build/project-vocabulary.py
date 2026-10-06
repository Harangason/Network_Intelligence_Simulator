"""Generate offline frontend projections from authoritative NIS owners."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]

def technology_projection(root=ROOT):
    technology_root = root / 'backend/nis/communication/technologies'
    technologies = []
    inputs = {}
    for source in sorted(technology_root.glob('*/profile.json')):
        profile = json.loads(source.read_text(encoding='utf-8'))
        identity_path, review_path = source.with_name('identity.json'), source.with_name('review.json')
        identity = json.loads(identity_path.read_text()) if identity_path.is_file() else {}
        review = json.loads(review_path.read_text(encoding='utf-8')) if review_path.is_file() else {}
        proposal = profile.get('parameter_proposals') or {}
        for path in [source, identity_path, review_path]:
            if path.is_file():
                inputs[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        technologies.append({'id': profile['id'], 'label': profile['label'],
            'aliases': list(dict.fromkeys([*identity.get('aliases', []), profile['label'], *profile.get('aliases', [])])),
            'max_payload_bytes': profile.get('max_payload_bytes'),
            'rate_proposal_bps': proposal.get('default_bps') or proposal.get('candidate'),
            'rate_proposal_status': 'REVIEW_REQUIRED', 'default_stack': profile.get('default_stack', [])})
    planning = root / 'backend/nis/engineering/network/planning-defaults.json'
    inputs[planning.relative_to(root).as_posix()] = hashlib.sha256(planning.read_bytes()).hexdigest()
    return {'schema_version': 1, 'source_sha256': hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
            'technologies': technologies, 'planning_limits': json.loads(planning.read_text())}

def project(root=ROOT):
    source = root / 'backend/nis/domain/inventory-vocabulary.json'
    (root / 'frontend/src/features/agent/lib/inventory-vocabulary.json').write_bytes(source.read_bytes())
    target = root / 'frontend/src/features/communication/lib/technology-projection.json'
    target.write_text(json.dumps(technology_projection(root), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

if __name__ == '__main__':
    project()

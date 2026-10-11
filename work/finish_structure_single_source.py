from finish_structure_owners import *
import importlib.util

path = 'backend/nis/communication/catalog.py'
source = read(path)
old = "    return loads(path.read_text(encoding='utf-8')) if path.is_file() else {}\n\nREVIEW_RATE_PROPOSALS"
new = "    review = loads(path.read_text(encoding='utf-8')) if path.is_file() else {}\n    profile_path = path.with_name('profile.json')\n    profile = loads(profile_path.read_text(encoding='utf-8')) if profile_path.is_file() else {}\n    if profile.get('parameter_proposals'):\n        review['rate_proposal'] = profile['parameter_proposals']\n    return review\n\nREVIEW_RATE_PROPOSALS"
assert old in source
write(path, source.replace(old, new))
for path in (ROOT / 'backend/nis/communication/technologies').glob('*/review.json'):
    value = json.loads(path.read_text(encoding='utf-8'))
    if 'rate_proposal' in value:
        del value['rate_proposal']
        write(path.relative_to(ROOT).as_posix(),json.dumps(value,ensure_ascii=False,indent=2) + '\n')
path = 'backend/tests/test_structure_completion.py'
source = read(path)
source += '''

def test_review_rates_are_projected_from_profile_without_copies():
    from backend.nis.communication.catalog import REVIEW_RATE_PROPOSALS
    for path in (ROOT / 'backend/nis/communication/technologies').glob('*/review.json'):
        review = json.loads(path.read_text(encoding='utf-8'))
        profile = json.loads(path.with_name('profile.json').read_text(encoding='utf-8'))
        assert 'rate_proposal' not in review
        if path.parent.name in REVIEW_RATE_PROPOSALS:
            assert REVIEW_RATE_PROPOSALS[path.parent.name] == profile['parameter_proposals']
'''
write(path,source)
apply('profile-rate-single-source')
WRITES.clear()
path = ROOT / 'scripts/build/project-vocabulary.py'
spec = importlib.util.spec_from_file_location('projection_generator',path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
write('frontend/src/features/communication/lib/technology-projection.json',json.dumps(module.technology_projection(ROOT),ensure_ascii=False,indent=2) + '\n')
apply('canonical-rate-projection')

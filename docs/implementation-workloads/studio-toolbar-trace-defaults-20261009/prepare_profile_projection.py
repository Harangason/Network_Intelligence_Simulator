import hashlib
import json
import shutil
from pathlib import Path
folder = Path(__file__).resolve().parent
root = folder.parents[2]
work = json.loads((folder / 'workload.json').read_text())
relative = 'backend/nis/engineering/capacity/dimensioning.py'
source, before = root / relative, folder / 'before' / relative
assert not before.exists()
before.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(source, before)
digest = hashlib.sha256(source.read_bytes()).hexdigest()
work['files_changed'].append(relative)
work['revision_before'][relative] = digest
(folder / 'workload.json').write_text(json.dumps(work, indent=2))
repair = json.loads((folder / 'performance-repair.json').read_text())
repair['revision_before'] = {relative: digest, 'backend/nis/engineering/routing/validation.py':
    hashlib.sha256((root / 'backend/nis/engineering/routing/validation.py').read_bytes()).hexdigest()}
repair['repair']['root_cause'] = 'Measured full TechnologyProfile copies consume 8.9 seconds in the adoption replay although routing only reads max_payload_bytes and rate planning only reads four named fields.'
repair['repair']['affected_files'] = list(repair['revision_before'])
evidence = folder / 'sizing-after-profile.txt'
repair['repair']['evidence'] = [{'path': str(evidence), 'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}]
(folder / 'profile-projection-repair.json').write_text(json.dumps(repair, indent=2))

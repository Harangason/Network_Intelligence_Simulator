"""Capture the guarded joint source snapshot; never changes application files."""
import difflib
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('I:/PycharmProjects/My_first_Network_Simulator')
OUT = Path(__file__).resolve().parent
BASE = OUT.parent
PEER = ROOT / 'docs/implementation-workloads/portfolio-parser-20261018'
original = json.loads((BASE / 'current-owned-manifest.json').read_text(encoding='utf-8'))
peer = {row['file']: row for row in json.loads((PEER / 'owned-manifest.json').read_text(encoding='utf-8'))}
rows = {}
diff = []
mapping_relative = 'docs/migrations/structure_mapping.csv'
for relative in sorted(original.keys() | peer.keys() | {mapping_relative}):
    current = (ROOT / relative).read_bytes()
    current_hash = hashlib.sha256(current).hexdigest()
    if relative == mapping_relative:
        expected = hashlib.sha256((OUT / 'structure-mapping-repair/after.csv').read_bytes()).hexdigest()
    elif relative in peer:
        expected = peer[relative]['after_sha256']
        if relative in original:
            assert peer[relative]['before_sha256'] == original[relative]['current'], ('Unexpected overlap baseline', relative)
        peer_before = (PEER / 'before' / relative).read_bytes()
        assert hashlib.sha256(peer_before).hexdigest() == peer[relative]['before_sha256'], ('Peer before evidence drift', relative)
    else:
        expected = original[relative]['current']
    assert current_hash == expected, ('PLAN_STALE', relative)
    before_path = BASE / 'combined-before' / relative
    if relative == mapping_relative:
        before_path = OUT / 'structure-mapping-repair/before.csv'
    elif relative not in original:
        before_path = PEER / 'before' / relative
    before = before_path.read_bytes() if before_path.exists() else b''
    if relative in original and original[relative].get('before'):
        assert hashlib.sha256(before).hexdigest() == original[relative]['before'], ('Original before evidence drift', relative)
    for folder, data in (('joint-before', before), ('joint-after', current)):
        target = OUT / folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    rows[relative] = {'before_sha256': hashlib.sha256(before).hexdigest() if before else None,
                      'current': current_hash, 'portfolio_change': relative in peer}
    diff.extend(difflib.unified_diff(before.decode('utf-8-sig').splitlines(True), current.decode('utf-8-sig').splitlines(True),
                                     fromfile='before/' + relative, tofile='after/' + relative))
(OUT / 'joint-owned-manifest.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
(OUT / 'joint-owned.diff').write_text(''.join(diff), encoding='utf-8')
record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'OWNED_SNAPSHOT_VERIFIED',
          'files': len(rows), 'application_mutations': 0, 'source_identity': 'Must be computed by the official release owner before prepare.'}
(OUT / 'joint-owned-state.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record), flush=True)

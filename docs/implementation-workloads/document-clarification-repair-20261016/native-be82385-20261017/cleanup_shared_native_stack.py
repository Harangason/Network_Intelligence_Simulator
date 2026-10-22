"""Reuse audited native cleanup only after BOTH original-file proofs and handoff."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
runtime = json.loads((OUT/'native-runtime-preparation.json').read_text(encoding='utf-8'))
peer = ROOT/'docs/implementation-workloads/robotics-document-handoff-20261016/joint-retest-20261017'
handoff = json.loads((OUT/'peer-native-slot-return.json').read_text(encoding='utf-8'))
assert handoff['qwen_active'] is False and handoff['native_tabs_closed'] is True
assert handoff['image_id'] == runtime['image_id']
for folder in [OUT, peer]:
    verification = json.loads((folder/'native-verification.json').read_text(encoding='utf-8'))
    audit = json.loads((folder/'native-tool-audit.json').read_text(encoding='utf-8'))
    assert verification['status'] == audit['status'] == 'PASSED'
    assert audit['image_id'] == runtime['image_id']
nonce = 'c79fead2a497'
assert all(runtime['containers'][kind].endswith(nonce) for kind in ('app','db','network','runtime'))
original = ROOT/'docs/implementation-workloads/robotics-document-handoff-20261016/native-attempt-2/cleanup_native_stack.py'
code = original.read_text(encoding='utf-8')
assert code.count('ba70268dda42') == 1
record = {'original_helper':str(original),'original_helper_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
          'adaptation':'Only pinned owned nonce updated; original ID, label, reference, production and image-retention guards preserved.',
          'both_native_proofs_secured':True,'both_native_audits_passed':True,'explicit_peer_slot_return':handoff}
(OUT/'cleanup-helper-provenance.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
exec(compile(code.replace('ba70268dda42',nonce),str(OUT/'reused_cleanup_native_stack.py'),'exec'),{'__file__':str(OUT/'reused_cleanup_native_stack.py')})

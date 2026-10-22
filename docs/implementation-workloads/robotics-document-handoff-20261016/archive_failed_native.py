"""Archive the completed failed native candidate, preserving immutable history."""
from pathlib import Path
import json
import runpy
OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
code = (OUT / 'archive_for_review.py').read_text(encoding='utf-8')
code = code.replace('candidate-043818af237b', 'candidate-911347665bea')
code = code.replace('sha256:e7167cb27aee4114b1d7eadf6fc3f5a315b37013ed9050969f76b5475f28f562', 'sha256:64020013cfb59eaa17acefa4484680bab1c7216ceb3ed54d96254e14288f355a')
code = code.replace("OUT/f'archived-receipt-{i}.json'", "OUT/f'native-failed-archived-receipt-{i}.json'")
code = code.replace("OUT/'archive-audit.json'", "OUT/'native-failed-archive-audit.json'")
code = code.replace("ROOT/'backend/test-output',ROOT/'work'", "ROOT/'backend/test-output',ROOT/'work',ROOT/'docs/implementation-workloads'")
code = code.replace("ARCHIVE_ONLY; candidate also has PREPARED receipts. Exact removal requires separate user authorization under AGENTS.md and release_storage.py.", "ARCHIVE_ONLY. Official FAIL and completed native FAILED with cleanup evidence resolve the historical own PREPARED use; no active release or native work remains. Removal evaluated separately against standing failed-candidate authorization.")
closed = json.loads((OUT / 'native-stack-cleanup.json').read_text(encoding='utf-8'))
assert closed['status'] == 'COMPLETED_NATIVE_STACK_REMOVED' and not closed['currently_active_native_work']
assert json.loads((OUT / 'native-verification.json').read_text(encoding='utf-8'))['status'] == 'FAILED'
exec(compile(code, str(OUT / 'archive_for_review.py'), 'exec'), {'__file__': str(OUT / 'archive_for_review.py'), '__name__': '__main__'})

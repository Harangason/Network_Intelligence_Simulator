"""Archive one unused PREPARED candidate for review; no removal authorization."""
import importlib.util
import json
from pathlib import Path

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent / 'archive-review-55794a287afa'
OUT.mkdir(exist_ok=False)
SOURCE = ROOT / 'docs/implementation-workloads/document-clarification-repair-20261016/archive_for_review.py'
spec = importlib.util.spec_from_file_location('existing_nis_archive_verifier', SOURCE)
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
owner.ROOT = ROOT
owner.OUT = OUT
owner.TAG = 'networkis:candidate-55794a287afa'
owner.IMAGE = 'sha256:dec19679fed8d27cdea1d921dd0a1ceda880404fe9fc4cfa7326493e4db4a12e'
owner.ARCHIVE = Path('F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c/nis-recoverable-archives-20261018/reference-example-assumptions-20261017/context-serialization-repair-55794a287afa/candidate-55794a287afa.tar')
owner.prepare()
p = OUT / 'archive-audit.json'
audit = json.loads(p.read_text(encoding='utf-8'))
assert audit['receipts'] and {r['status'] for r in audit['receipts']} == {'PREPARED'}
audit['archive_verifier_source'] = owner.ref(SOURCE)
audit['removal_authorized'] = False
audit['authorization'] = 'ARCHIVE ONLY. PREPARED without FAIL/PASS; no standing permission for deletion. Exact human approval required by AGENTS.md.'
p.write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')

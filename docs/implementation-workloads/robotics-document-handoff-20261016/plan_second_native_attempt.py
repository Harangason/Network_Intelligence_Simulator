"""Preserve the first native failure and prepare separate second-run evidence."""
from pathlib import Path
import hashlib
import json
OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
attempt = OUT / 'native-attempt-2'
attempt.mkdir(exist_ok=True)
source = (OUT / 'prepare_native_acceptance.py').read_text(encoding='utf-8')
source = source.replace('OUT = Path(__file__).parent.resolve()\nROOT = OUT.parents[2]', 'OUT = Path(__file__).parent.resolve()\nROOT = OUT.parents[3]')
source = source.replace("candidate['status'] in {'RUNNING', 'PASS'}", "candidate['status'] == 'PREPARED'")
start = source.index("stack_output = OUT / 'native-acceptance-stack'")
end = source.index("names = receipt['containers']", start)
source = source[:start] + "receipt_path = args.candidate_receipt.resolve()\nreceipt = candidate\n" + source[end:]
(attempt / 'prepare_native_acceptance.py').write_text(source, encoding='utf-8')
for name in ['capture_native_tool_audit.py', 'verify_robotics_dom.py', 'capture_source_units.py']:
    source = (OUT / name).read_text(encoding='utf-8')
    source = source.replace('ROOT = OUT.parents[2]', 'ROOT = OUT.parents[3]')
    (attempt / name).write_text(source, encoding='utf-8')
(attempt / 'plan.json').write_text(json.dumps({'state': 'AWAITING_TARGETED_TESTS_AND_PRODUCTION_CANDIDATE', 'previous_native_result': str(OUT / 'native-verification.json'), 'scope': 'Complete byte-identical original robotics file; individual functions, independent classification, complete structured handoff, unresolved inputs remain questions.', 'full_release_gate_after_native_success': True}, indent=2), encoding='utf-8')
print(str(attempt))

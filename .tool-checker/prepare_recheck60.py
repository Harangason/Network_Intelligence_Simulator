"""Prepare fresh evidence and reviewed adapter; preserve all previous audit runs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / '.tool-checker'
receipt = json.loads((ROOT / 'backend/test-output/industry60-recheck-stack/919f1a3730d4/receipt.json').read_text())
assert receipt['status'] == 'PREPARED', receipt['status']
base = receipt['base_url']
folder = HERE / 'recheck60'
folder.mkdir(exist_ok=True)
for name in ['industry60_adapter.py', 'run_industry60_jobs.py', 'industry60_fixtures.py', 'industry60_manual.py', 'seed60_s26.py', 'seed60_s27.py', 'seed60_s29.py', 'seed60_trace.py', 'run_industry60_canonical_jobs.py', 'test_industry60_mcp.py', 'test_industry60_trace.py']:
    text = (HERE / name).read_text(encoding='utf8')
    text = text.replace('parents[1]', 'parents[2]')
    text = text.replace('http://127.0.0.1:51576', base)
    text = text.replace('evidence/industry60', 'evidence/industry60-recheck')
    text = text.replace('industry60.normalized.json', 'industry60-recheck.normalized.json')
    text = text.replace("ROOT/'.tool-checker/industry60_adapter.py'", "ROOT/'.tool-checker/recheck60/industry60_adapter.py'")
    text = text.replace('f4a32bef96e8', '919f1a3730d4').replace('c16f447ee305', receipt['release']['build_id'])
    text = text.replace("'industry60-http'", "'industry60-recheck-http'")
    text = text.replace("'--id','industry60'", "'--id','industry60-recheck'")
    text = text.replace("'--task','industry60'", "'--task','industry60-recheck'")
    # The HTTP adapter cannot claim a browser observation or downstream execution.
    text = text.replace("'browser':{'observed_working':True}", "'browser':{'observed_working':False}")
    (folder / name).write_text(text, encoding='utf8')
(HERE / 'industry60-recheck.normalized.json').write_text((HERE / 'industry60.normalized.json').read_text(encoding='utf8'), encoding='utf8')
print(json.dumps({'base':base,'folder':str(folder),'image':receipt['image_id']}))
